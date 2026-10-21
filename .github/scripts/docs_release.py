"""Validate durable release provenance, build a snapshot, then promote it locally.

The workflow pushes the resulting branch only after site validation succeeds.
Package identity and API extraction always follow the successful release CI SHA;
a docs-only correction may select a separate guide commit on main.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

import release_plan as release

IGNORE_NAMES = {".venv", "node_modules", ".mintlify", "__pycache__", ".pytest_cache"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def current_release() -> tuple[str | None, dict | None]:
    """Only a successful remote query with no branch proves first publication."""
    refs = git("ls-remote", "--heads", "origin", "refs/heads/docs-release")
    if not refs:
        return None, None
    if not re.fullmatch(r"[0-9a-f]{40}\s+refs/heads/docs-release", refs):
        release.fail("malformed docs-release remote ref")
    git("fetch", "origin", "+refs/heads/docs-release:refs/remotes/origin/docs-release")
    head = git("rev-parse", "refs/remotes/origin/docs-release")
    if head != refs.split()[0]:
        release.fail("docs-release changed during validation; retry")
    data = json.loads(git("show", f"{head}:docs-v2/provenance.json"))
    if (
        not isinstance(data, dict)
        or not re.fullmatch(r"\d+\.\d+\.\d+", data["version"])
        or not re.fullmatch(r"[0-9a-f]{40}", data["sha"])
        or not re.fullmatch(r"[0-9a-f]{40}", data["docs_source_sha"])
        or not isinstance(data["pypi_files"], dict)
    ):
        release.fail("malformed current docs provenance")
    return head, data


def copy_site(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(*IGNORE_NAMES, "*.pyc"))


def prepare(
    work: Path,
    *,
    version: str,
    sha: str,
    run_id: str,
    artifact_id: str,
    mode: str,
    docs_sha: str = "",
    fetch_json=None,
    fetch_asset=None,
    pypi_opener=None,
) -> dict:
    """Run the real early guard and materialize isolated package/guide worktrees."""
    if mode not in {"publish", "retry", "docs-only"}:
        release.fail("invalid promotion mode")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not re.fullmatch(
        r"[0-9a-f]{40}", sha
    ):
        release.fail("invalid release version or SHA")
    if not run_id.isdecimal() or not artifact_id.isdecimal():
        release.fail("CI run and artifact IDs must be numeric")
    docs_sha = docs_sha or sha
    if not re.fullmatch(r"[0-9a-f]{40}", docs_sha):
        release.fail("guide source must be a full commit SHA")
    if mode != "docs-only" and docs_sha != sha:
        release.fail("separate guide source requires docs-only")
    head, current = current_release()
    if current:
        old = tuple(map(int, current["version"].split(".")))
        new = tuple(map(int, version.split(".")))
        if new < old:
            release.fail("refusing to roll docs-release back")
        if new == old and current["sha"] != sha:
            release.fail("same version has a different package SHA")
    if mode == "docs-only" and (not current or current["version"] != version):
        release.fail("docs-only requires the currently published version")
    repository = os.environ["GITHUB_REPOSITORY"]
    fetch = fetch_json or release.gh
    read_asset = fetch_asset or release.asset_bytes
    run = fetch("api", f"repos/{repository}/actions/runs/{run_id}")
    release.validate_run(run, repository)
    published = fetch("api", f"repos/{repository}/releases/tags/v{version}")
    if (
        published["tag_name"] != f"v{version}"
        or published["draft"]
        or published["prerelease"]
    ):
        release.fail("requires a stable published GitHub release")
    assets = {item["name"]: item for item in published["assets"]}
    expected = {
        f"agentconnect-{version}-py3-none-any.whl",
        f"agentconnect-{version}.tar.gz",
        "release-intent.json",
    }
    if set(assets) != expected:
        release.fail("release assets differ from the immutable publication set")
    contents = {}
    for name, asset in assets.items():
        content = read_asset(repository, asset["id"])
        digest = hashlib.sha256(content).hexdigest()
        if asset.get("digest") != f"sha256:{digest}":
            release.fail("durable release asset digest mismatch")
        contents[name] = content
    intent = json.loads(contents.pop("release-intent.json"))
    if (
        intent.get("ci_run_id") != run_id
        or intent.get("artifact_id") != artifact_id
        or intent.get("version") != version
        or intent.get("sha") != sha
    ):
        release.fail("requested identity differs from durable release intent")
    files = {
        name: hashlib.sha256(content).hexdigest() for name, content in contents.items()
    }
    if not release.validate_intent(intent, run, files):
        release.fail("release intent did not authorize publication")
    if git("rev-parse", f"refs/tags/v{version}^{{commit}}") != sha:
        release.fail("published tag differs from package SHA")
    with (pypi_opener or urllib.request.urlopen)(
        f"https://pypi.org/pypi/agentconnect/{version}/json", timeout=30
    ) as response:
        payload = json.load(response)
    remote = {item["filename"]: item["digests"]["sha256"] for item in payload["urls"]}
    if release.missing_files(files, remote):
        release.fail("PyPI publication is incomplete")
    # A guide correction must be a main commit descended from the package.
    git("merge-base", "--is-ancestor", docs_sha, "refs/remotes/origin/main")
    git("merge-base", "--is-ancestor", sha, docs_sha)
    if current and current["version"] == version and mode == "docs-only":
        git("merge-base", "--is-ancestor", current["docs_source_sha"], docs_sha)
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    for name, ref in (("package", sha), ("guides", docs_sha)):
        git("worktree", "add", "--detach", str(work / name), ref)
    state = dict(
        version=version,
        sha=sha,
        docs_source_sha=docs_sha,
        ci_run_id=run_id,
        artifact_id=artifact_id,
        pypi_files=files,
    )
    plan = {
        "provenance": state,
        "previous_head": head,
        "current": current,
        "mode": mode,
    }
    (work / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return plan


def build(work: Path) -> None:
    """Generate package-bound API, then run the real site checker."""
    work = work.resolve()
    package, guides = work / "package", work / "guides" / "docs-v2"
    # Reference policy belongs to the published package, even when later guide
    # tooling knows about modules that do not exist in that package.
    package_docs = package / "docs-v2"
    shutil.copyfile(
        package_docs / "scripts/api_surface.py", guides / "scripts/api_surface.py"
    )
    config = json.loads((guides / "docs.json").read_text(encoding="utf-8"))
    published_config = json.loads(
        (package_docs / "docs.json").read_text(encoding="utf-8")
    )
    reference = next(
        tab
        for tab in published_config["navigation"]["tabs"]
        if tab["tab"] == "Reference"
    )
    tabs = config["navigation"]["tabs"]
    tabs[:] = [reference if tab["tab"] == "Reference" else tab for tab in tabs]
    if reference not in tabs:
        tabs.append(reference)
    (guides / "docs.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    subprocess.run(
        [
            sys.executable,
            str(guides / "scripts/generate_api.py"),
            "--root",
            str(package),
            "--output",
            str(guides),
        ],
        check=True,
        cwd=guides,
    )
    subprocess.run(
        [
            sys.executable,
            str(guides / "scripts/check.py"),
            "--skip-stale",
            "--source-root",
            str(package),
        ],
        check=True,
        cwd=guides,
    )


def promote(work: Path) -> bool:
    """Commit validated site bytes; identical reruns leave the branch unchanged."""
    work = work.resolve()
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    head, current = current_release()
    if head != plan["previous_head"]:
        release.fail("docs-release changed after validation; retry")
    source = work / "guides" / "docs-v2"
    (source / "provenance.json").write_text(
        json.dumps(plan["provenance"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target = work / "promotion"
    git("worktree", "add", "--detach", str(target), head or plan["provenance"]["sha"])

    def target_git(*args):
        return subprocess.check_output(
            ["git", "-C", str(target), *args], text=True
        ).strip()

    if not head:
        target_git("checkout", "--orphan", "docs-release")
        target_git("rm", "-rf", "--ignore-unmatch", ".")
    copy_site(source, target / "docs-v2")
    target_git("add", "docs-v2")
    tree = target_git("write-tree")
    if head:
        previous_tree = git("rev-parse", f"{head}^{{tree}}")
        if tree == previous_tree:
            git("update-ref", "refs/heads/docs-release", head)
            return False
        if (
            current["version"] == plan["provenance"]["version"]
            and plan["mode"] != "docs-only"
        ):
            release.fail(
                "same-version snapshot content conflicts; use a docs-only correction"
            )
    target_git(
        "-c",
        "user.name=agentconnect-docs",
        "-c",
        "user.email=docs@users.noreply.github.com",
        "commit",
        "-m",
        f"Docs snapshot for v{plan['provenance']['version']}",
    )
    commit = target_git("rev-parse", "HEAD")
    # The final ordinary push rejects concurrent remote changes (no force push).
    if head:
        git("update-ref", "refs/heads/docs-release", commit)
    return True


def main() -> None:
    command = sys.argv[1]
    work = Path(os.environ["DOCS_WORK"])
    if command == "prepare":
        prepare(
            work,
            version=os.environ["VERSION"],
            sha=os.environ["SHA"],
            run_id=os.environ["CI_RUN_ID"],
            artifact_id=os.environ["ARTIFACT_ID"],
            mode=os.environ["DOCS_MODE"],
            docs_sha=os.environ.get("DOCS_SOURCE_SHA", ""),
        )
    elif command == "build":
        build(work)
    elif command == "promote":
        print("snapshot changed" if promote(work) else "identical snapshot; no-op")
    else:
        release.fail("usage: docs_release.py [prepare|build|promote]")


if __name__ == "__main__":
    main()
