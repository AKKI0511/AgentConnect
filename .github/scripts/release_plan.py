"""Publish only distributions built and installed by a successful main CI run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


def gh(*args: str) -> dict:
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def fail(message: str) -> None:
    raise SystemExit(message)


def output(**values: str) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def version_at(sha: str) -> str:
    raw = subprocess.check_output(["git", "show", f"{sha}:pyproject.toml"])
    return tomllib.loads(raw.decode("utf-8"))["project"]["version"]


def record() -> None:
    sha = os.environ["GITHUB_SHA"]
    parents = subprocess.check_output(
        ["git", "rev-list", "--parents", "-n", "1", sha], text=True
    ).split()
    version = version_at(sha)
    publish = False
    if (
        os.environ["GITHUB_EVENT_NAME"] == "push"
        and os.environ["GITHUB_REF"] == "refs/heads/main"
    ):
        before = os.environ.get("BEFORE", "")
        baseline = (
            before
            if before and set(before) != {"0"}
            else (parents[1] if len(parents) > 1 else None)
        )
        publish = baseline is not None and version_at(baseline) != version
    data = {
        "publish": publish,
        "sha": sha,
        "version": version,
        "files": local_dists(),
    }
    Path("release-intent.json").write_text(json.dumps(data) + "\n", encoding="utf-8")


def validate_run(run: dict, repository: str) -> None:
    if not (
        run.get("conclusion") == "success"
        and run.get("status") == "completed"
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("path") == ".github/workflows/main.yml"
        and run.get("head_repository", {}).get("full_name") == repository
    ):
        fail("publication requires a successful push CI run on this repository's main")


def plan() -> None:
    run_id = os.environ["CI_RUN_ID"]
    if not run_id.isdecimal():
        fail("CI run ID must be numeric")
    repository = os.environ["GITHUB_REPOSITORY"]
    run = gh("api", f"repos/{repository}/actions/runs/{run_id}")
    validate_run(run, repository)
    payload = gh(
        "api", f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"
    )
    artifacts = [
        item
        for item in payload["artifacts"]
        if item["name"] == "distributions" and not item["expired"]
    ]
    if not artifacts:
        fail("successful CI run has no unexpired distribution artifact")
    # Resolve once while CI is successful. All jobs download this immutable ID,
    # even if a later CI attempt creates another artifact with the same name.
    artifact = max(artifacts, key=lambda item: int(item["id"]))
    output(run_id=run_id, artifact_id=str(artifact["id"]))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_dists() -> dict[str, str]:
    files = {
        path.name: digest(path)
        for path in Path("dist").iterdir()
        if path.is_file()
        and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    }
    wheels = [name for name in files if name.endswith(".whl")]
    sdists = [name for name in files if name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        fail("expected exactly one wheel and one sdist")
    return files


def verify() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    run = gh("api", f"repos/{repository}/actions/runs/{os.environ['CI_RUN_ID']}")
    validate_run(run, repository)
    data = json.loads(Path("release-intent.json").read_text(encoding="utf-8"))
    if validate_intent(data, run, local_dists()):
        output(publish="true", version=data["version"], sha=data["sha"])
    else:
        output(publish="false")


def validate_intent(data: dict, run: dict, files: dict[str, str]) -> bool:
    """Shared CI and durable-release verification of the tested package identity."""
    if data.get("sha") != run["head_sha"]:
        fail("artifact commit differs from successful CI commit")
    if data.get("files") != files:
        fail("distribution hashes differ from tested CI artifacts")
    if data.get("publish") is not True:
        return False
    version = data["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail("only stable major.minor.patch versions can be published")
    if version_at(data["sha"]) != version:
        fail("artifact version differs from source metadata")
    expected = {
        f"agentconnect-{version}.tar.gz",
        f"agentconnect-{version}-py3-none-any.whl",
    }
    if set(files) != expected:
        fail("distribution filenames differ from release version")
    check_tag(version, data["sha"])
    return True


def check_tag(version: str, sha: str) -> None:
    ref = f"refs/tags/v{version}"
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref])
    if exists.returncode == 1:
        return
    exists.check_returncode()
    tagged = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], text=True
    ).strip()
    if tagged != sha:
        fail("existing release tag points to a different commit")


def asset_bytes(repository: str, asset_id: int) -> bytes:
    return subprocess.check_output(
        [
            "gh",
            "api",
            f"repos/{repository}/releases/assets/{asset_id}",
            "--header",
            "Accept: application/octet-stream",
        ]
    )


def missing_files(local: dict[str, str], remote: dict[str, str]) -> list[str]:
    if set(remote) - set(local) or any(
        local[name] != value for name, value in remote.items()
    ):
        fail(
            "published distribution filenames or hashes conflict with verified artifacts"
        )
    return sorted(set(local) - set(remote))


def pypi_status() -> None:
    local = local_dists()
    url = f"https://pypi.org/pypi/agentconnect/{os.environ['VERSION']}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        payload = {"urls": []}
    remote = {item["filename"]: item["digests"]["sha256"] for item in payload["urls"]}
    output(skip_pypi=str(not missing_files(local, remote)).lower())


def github_release() -> None:
    version, sha = os.environ["VERSION"], os.environ["SHA"]
    repository = os.environ["GITHUB_REPOSITORY"]
    run_id, artifact_id = os.environ["CI_RUN_ID"], os.environ["ARTIFACT_ID"]
    run = gh("api", f"repos/{repository}/actions/runs/{run_id}")
    validate_run(run, repository)
    intent_path = Path("release-intent.json")
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    if not validate_intent(intent, run, local_dists()):
        fail("release intent does not authorize publication")
    if intent["version"] != version or intent["sha"] != sha:
        fail("release identity differs from verified intent")
    artifact = gh("api", f"repos/{repository}/actions/artifacts/{artifact_id}")
    if (
        str(artifact["id"]) != artifact_id
        or artifact["name"] != "distributions"
        or str(artifact["workflow_run"]["id"]) != run_id
        or artifact["workflow_run"]["head_sha"] != sha
    ):
        fail("artifact does not belong to the verified CI run")
    intent.update(ci_run_id=run_id, artifact_id=artifact_id)
    intent_path.write_text(json.dumps(intent, sort_keys=True) + "\n", encoding="utf-8")
    local = {**local_dists(), "release-intent.json": digest(intent_path)}
    paths = {name: str(Path("dist") / name) for name in local_dists()}
    paths["release-intent.json"] = str(intent_path)
    tag = f"v{version}"
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/releases/tags/{tag}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        if "HTTP 404" not in result.stderr:
            fail(result.stderr)
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--target",
                sha,
                "--generate-notes",
                *[paths[name] for name in sorted(local)],
            ],
            check=True,
        )
        return
    payload = json.loads(result.stdout)
    if payload["tag_name"] != tag or payload["draft"] or payload["prerelease"]:
        fail("existing release is not a stable published release")
    remote = {}
    for asset in payload["assets"]:
        value = asset.get("digest") or ""
        if not value.startswith("sha256:"):
            fail("existing GitHub asset has no comparable SHA256 digest")
        remote[asset["name"]] = value.removeprefix("sha256:")
    missing = missing_files(local, remote)
    if missing:
        subprocess.run(
            [
                "gh",
                "release",
                "upload",
                tag,
                *[paths[name] for name in missing],
            ],
            check=True,
        )


if __name__ == "__main__":
    commands = {
        "record": record,
        "plan": plan,
        "verify": verify,
        "pypi-status": pypi_status,
        "github-release": github_release,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        fail("usage: release_plan.py [record|plan|verify|pypi-status|github-release]")
    commands[sys.argv[1]]()
