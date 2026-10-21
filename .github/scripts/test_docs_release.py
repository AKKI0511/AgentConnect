"""Promotion integration tests: real Git/worktrees and fake HTTP external services."""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location(
    "docs_release", Path(__file__).with_name("docs_release.py")
)
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)

GENERATOR = """import argparse
from pathlib import Path
from api_surface import PUBLIC_MODULES
p=argparse.ArgumentParser(); p.add_argument("--root"); p.add_argument("--output")
a=p.parse_args()
r=Path(a.root); o=Path(a.output)
assert PUBLIC_MODULES == {(r/"package.txt").read_text()}
(o/"api.mdx").write_text((r/"package.txt").read_text())
"""
CHECKER = """import argparse
import json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument("--source-root"); p.add_argument("--skip-stale", action="store_true")
a=p.parse_args()
assert Path("api.mdx").read_text()==(Path(a.source_root)/"package.txt").read_text()
tabs = json.loads(Path("docs.json").read_text())["navigation"]["tabs"]
assert tabs[-1]["pages"] == [Path("api.mdx").read_text()]
assert Path("guide.mdx").read_text() != "broken"
"""


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.previous = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.previous)
        self.run_git("init", "--initial-branch=main")
        self.run_git("config", "user.email", "tests@example.invalid")
        self.run_git("config", "user.name", "Integration test")
        self.run_git("init", "--bare", str(self.root / "origin.git"))
        self.run_git("remote", "add", "origin", str(self.root / "origin.git"))
        self.sha = self.commit("1.0.0", "published API", "original guide")
        self.run_git("tag", "v1.0.0", self.sha)
        self.run_git("push", "origin", "main", "--tags")
        self.run_git("fetch", "origin")
        self.routes = {}
        self.fail_routes = set()
        routes, fail_routes = self.routes, self.fail_routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in fail_routes:
                    self.send_error(503)
                    return
                if self.path not in routes:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(routes[self.path])

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.env = patch.dict(os.environ, GITHUB_REPOSITORY="owner/repo")
        self.env.start()
        self.addCleanup(self.env.stop)
        self.install_release("1.0.0", self.sha)
        self.sequence = 0

    def run_git(self, *args):
        return subprocess.check_output(
            ["git", *args], text=True, stderr=subprocess.PIPE
        ).strip()

    def commit(self, version, api, guide):
        Path("pyproject.toml").write_text(f'[project]\nversion="{version}"\n')
        Path("package.txt").write_text(api)
        site = Path("docs-v2")
        (site / "scripts").mkdir(parents=True, exist_ok=True)
        (site / "scripts/generate_api.py").write_text(GENERATOR)
        (site / "scripts/check.py").write_text(CHECKER)
        (site / "scripts/api_surface.py").write_text(f"PUBLIC_MODULES = {{{api!r}}}\n")
        (site / "docs.json").write_text(
            json.dumps(
                {
                    "navigation": {
                        "tabs": [
                            {"tab": "Docs", "pages": [guide]},
                            {"tab": "Reference", "pages": [api]},
                        ]
                    }
                }
            )
        )
        (site / "guide.mdx").write_text(guide)
        self.run_git("add", ".")
        self.run_git("commit", "-m", f"source {version} {guide}")
        return self.run_git("rev-parse", "HEAD")

    def put_json(self, path, value):
        self.routes["/" + path] = json.dumps(value).encode()

    def install_release(self, version, sha):
        run = dict(
            conclusion="success",
            status="completed",
            event="push",
            head_branch="main",
            path=".github/workflows/main.yml",
            head_repository={"full_name": "owner/repo"},
            head_sha=sha,
        )
        self.put_json("repos/owner/repo/actions/runs/100", run)
        # Artifact endpoint deliberately unavailable: expired CI artifacts are irrelevant.
        self.fail_routes.add("/repos/owner/repo/actions/artifacts/200")
        contents = {
            f"agentconnect-{version}-py3-none-any.whl": b"immutable wheel",
            f"agentconnect-{version}.tar.gz": b"immutable sdist",
        }
        self.files = {
            name: hashlib.sha256(value).hexdigest() for name, value in contents.items()
        }
        self.intent = dict(
            publish=True,
            version=version,
            sha=sha,
            ci_run_id="100",
            artifact_id="200",
            files=self.files,
        )
        contents["release-intent.json"] = json.dumps(self.intent).encode()
        assets = []
        for i, (name, value) in enumerate(contents.items(), 1):
            self.routes[f"/repos/owner/repo/releases/assets/{i}"] = value
            assets.append(
                dict(
                    id=i,
                    name=name,
                    digest="sha256:" + hashlib.sha256(value).hexdigest(),
                )
            )
        self.published = dict(
            tag_name=f"v{version}", draft=False, prerelease=False, assets=assets
        )
        self.put_json(f"repos/owner/repo/releases/tags/v{version}", self.published)
        self.put_json(
            "pypi",
            {
                "urls": [
                    dict(filename=n, digests={"sha256": d})
                    for n, d in self.files.items()
                ]
            },
        )

    def fetch(self, command, path):
        self.assertEqual(command, "api")
        with urllib.request.urlopen(self.endpoint + "/" + path) as response:
            return json.load(response)

    def asset(self, repository, asset_id):
        with urllib.request.urlopen(
            self.endpoint + f"/repos/{repository}/releases/assets/{asset_id}"
        ) as response:
            return response.read()

    def pypi(self, url, timeout):
        return urllib.request.urlopen(self.endpoint + "/pypi", timeout=timeout)

    def prepare(self, **changes):
        self.sequence += 1
        work = self.root / f"work-{self.sequence}"
        args = dict(
            version="1.0.0",
            sha=self.sha,
            run_id="100",
            artifact_id="200",
            mode="publish",
        )
        args.update(changes)
        docs.prepare(
            work,
            **args,
            fetch_json=self.fetch,
            fetch_asset=self.asset,
            pypi_opener=self.pypi,
        )
        return work

    def flow(self, **changes):
        work = self.prepare(**changes)
        docs.build(work)
        changed = docs.promote(work)
        self.run_git("push", "origin", "docs-release")
        return work, changed

    def test_first_publication_and_identical_reruns(self):
        _, changed = self.flow()
        self.assertTrue(changed)
        head = self.run_git("rev-parse", "docs-release")
        for mode in ("publish", "retry"):
            _, changed = self.flow(mode=mode)
            self.assertFalse(changed)
            self.assertEqual(head, self.run_git("rev-parse", "docs-release"))
        data = json.loads(self.run_git("show", "docs-release:docs-v2/provenance.json"))
        self.assertEqual(data["artifact_id"], "200")
        self.assertEqual(data["sha"], self.sha)

    def test_requested_provenance_mismatches(self):
        for changes in (
            dict(run_id="101"),
            dict(artifact_id="201"),
            dict(sha="a" * 40),
            dict(version="1.0.1"),
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((SystemExit, urllib.error.HTTPError)),
            ):
                self.prepare(**changes)
        self.assertFalse(self.run_git("ls-remote", "--heads", "origin", "docs-release"))

    def test_invalid_ci_and_unavailable_provenance(self):
        path = "repos/owner/repo/actions/runs/100"
        run = json.loads(self.routes["/" + path])
        for field, value in (
            ("conclusion", "failure"),
            ("head_sha", "b" * 40),
            ("event", "pull_request"),
        ):
            self.put_json(path, {**run, field: value})
            with self.subTest(field=field), self.assertRaises(SystemExit):
                self.prepare()
        self.put_json(path, run)
        self.fail_routes.add("/repos/owner/repo/releases/tags/v1.0.0")
        with self.assertRaises(urllib.error.HTTPError):
            self.prepare()

    def test_distribution_or_intent_tampering(self):
        self.routes["/repos/owner/repo/releases/assets/1"] = b"tampered"
        with self.assertRaises(SystemExit):
            self.prepare()
        self.install_release("1.0.0", self.sha)
        self.intent["files"] = {"wrong": "digest"}
        raw = json.dumps(self.intent).encode()
        self.routes["/repos/owner/repo/releases/assets/3"] = raw
        self.published["assets"][2]["digest"] = (
            "sha256:" + hashlib.sha256(raw).hexdigest()
        )
        self.put_json("repos/owner/repo/releases/tags/v1.0.0", self.published)
        with self.assertRaises(SystemExit):
            self.prepare()

    def test_expired_artifact_uses_durable_assets(self):
        # The only artifact endpoint returns 503. Promotion still uses the
        # published Release bytes and original pinned identity without rebuilding.
        work, changed = self.flow(mode="retry")
        self.assertTrue(changed)
        plan = json.loads((work / "plan.json").read_text())
        self.assertEqual(plan["provenance"]["pypi_files"], self.files)
        self.assertEqual(plan["provenance"]["ci_run_id"], "100")

    def test_pypi_mismatch(self):
        self.put_json("pypi", {"urls": []})
        with self.assertRaises(SystemExit):
            self.prepare()

    def test_same_version_conflicting_snapshot(self):
        self.flow()
        head = self.run_git("rev-parse", "docs-release")
        work = self.prepare(mode="retry")
        docs.build(work)
        (work / "guides/docs-v2/guide.mdx").write_text("conflicting bytes")
        with self.assertRaises(SystemExit):
            docs.promote(work)
        self.assertEqual(self.run_git("rev-parse", "docs-release"), head)

    def test_docs_only_correction_keeps_published_api(self):
        self.flow()
        self.commit("1.1.0", "unreleased API", "corrected guide")
        generator = Path("docs-v2/scripts/generate_api.py")
        generator.write_text(
            GENERATOR
            + '\n(o.parent/"generator-source.txt").write_text("corrected-guide-generator")\n'
        )
        self.run_git("add", str(generator))
        self.run_git("commit", "-m", "correction generator")
        guide_sha = self.run_git("rev-parse", "HEAD")
        self.run_git("push", "origin", "main")
        self.run_git("fetch", "origin")
        work, changed = self.flow(mode="docs-only", docs_sha=guide_sha)
        self.assertEqual(
            (work / "guides/generator-source.txt").read_text(),
            "corrected-guide-generator",
        )
        self.assertTrue(changed)
        self.assertEqual(
            self.run_git("show", "docs-release:docs-v2/guide.mdx"), "corrected guide"
        )
        self.assertEqual(
            self.run_git("show", "docs-release:docs-v2/api.mdx"), "published API"
        )
        data = json.loads(self.run_git("show", "docs-release:docs-v2/provenance.json"))
        self.assertEqual((data["sha"], data["docs_source_sha"]), (self.sha, guide_sha))
        config = json.loads(self.run_git("show", "docs-release:docs-v2/docs.json"))
        self.assertEqual(config["navigation"]["tabs"][0]["pages"], ["corrected guide"])
        self.assertEqual(config["navigation"]["tabs"][1]["pages"], ["published API"])
        # An old correction retry must not replace a newer published guide.
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare(mode="docs-only", docs_sha=self.sha)

    def test_older_retry_rejected_before_network(self):
        self.flow()
        newer = self.commit("1.1.0", "next API", "next guide")
        self.run_git("tag", "v1.1.0", newer)
        self.run_git("push", "origin", "main", "--tags")
        self.run_git("fetch", "origin")
        self.install_release("1.1.0", newer)
        self.flow(version="1.1.0", sha=newer)
        self.server.shutdown()
        with self.assertRaisesRegex(SystemExit, "roll"):
            self.prepare(mode="retry")

    def test_release_creation_uploads_durable_verified_intent(self):
        dist = Path("dist")
        dist.mkdir()
        (dist / "agentconnect-1.0.0-py3-none-any.whl").write_bytes(b"immutable wheel")
        (dist / "agentconnect-1.0.0.tar.gz").write_bytes(b"immutable sdist")
        Path("release-intent.json").write_text(
            json.dumps(
                {
                    key: value
                    for key, value in self.intent.items()
                    if key not in {"ci_run_id", "artifact_id"}
                }
            )
        )
        self.fail_routes.remove("/repos/owner/repo/actions/artifacts/200")
        self.put_json(
            "repos/owner/repo/actions/artifacts/200",
            {
                "id": 200,
                "name": "distributions",
                "workflow_run": {"id": 100, "head_sha": self.sha},
            },
        )
        actual_run = subprocess.run
        uploads = []

        def external_command(args, **kwargs):
            if args[:2] == ["gh", "api"]:
                return subprocess.CompletedProcess(args, 1, "", "HTTP 404")
            if args[:3] == ["gh", "release", "create"]:
                uploads.extend(args[7:])
                return subprocess.CompletedProcess(args, 0)
            return actual_run(args, **kwargs)

        with (
            patch.dict(
                os.environ,
                VERSION="1.0.0",
                SHA=self.sha,
                CI_RUN_ID="100",
                ARTIFACT_ID="200",
            ),
            patch.object(docs.release, "gh", side_effect=self.fetch),
            patch.object(docs.release.subprocess, "run", side_effect=external_command),
        ):
            docs.release.github_release()
        self.assertEqual(
            set(uploads),
            {str(dist / name) for name in self.files} | {"release-intent.json"},
        )
        persisted = json.loads(Path("release-intent.json").read_text())
        self.assertEqual(
            (persisted["ci_run_id"], persisted["artifact_id"]), ("100", "200")
        )
        self.assertEqual(persisted["files"], self.files)

    def test_fetch_failure_is_not_first_publication(self):
        self.flow()
        real_git = docs.git

        def broken_fetch(*args):
            if args[0] == "fetch":
                raise subprocess.CalledProcessError(128, ["git", *args])
            return real_git(*args)

        with (
            patch.object(docs, "git", side_effect=broken_fetch),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            self.prepare()

    def test_git_errors_do_not_become_first_publication(self):
        self.run_git("remote", "set-url", "origin", str(self.root / "missing.git"))
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare()

    def test_missing_and_malformed_current_provenance_fail_closed(self):
        self.flow()
        work = self.root / "corrupt"
        self.run_git("worktree", "add", "--detach", str(work), "docs-release")
        for content in (None, "{broken", "{}"):
            marker = work / "docs-v2/provenance.json"
            if content is None:
                marker.unlink()
            else:
                marker.write_text(content)
            subprocess.check_call(["git", "-C", str(work), "add", "-A"])
            subprocess.check_call(
                ["git", "-C", str(work), "commit", "-m", "bad provenance"],
                stdout=subprocess.DEVNULL,
            )
            self.run_git(
                "push",
                "origin",
                f"{subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD'], text=True).strip()}:refs/heads/docs-release",
            )
            with self.assertRaises(
                (
                    json.JSONDecodeError,
                    KeyError,
                    subprocess.CalledProcessError,
                    SystemExit,
                )
            ):
                self.prepare()

    def test_failed_site_check_cannot_reach_promotion(self):
        work = self.prepare()
        (work / "guides/docs-v2/guide.mdx").write_text("broken")
        with self.assertRaises(subprocess.CalledProcessError):
            docs.build(work)
        self.assertFalse(self.run_git("ls-remote", "--heads", "origin", "docs-release"))


if __name__ == "__main__":
    unittest.main()
