"""Failure-focused tests for the publication boundary; no network or uploads."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_plan", Path(__file__).with_name("release_plan.py")
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_successful_main_push_only(self):
        run = {
            "conclusion": "success",
            "status": "completed",
            "event": "push",
            "head_branch": "main",
            "path": ".github/workflows/main.yml",
            "head_repository": {"full_name": "owner/repo"},
        }
        release.validate_run(run, "owner/repo")
        for field, value in (
            ("event", "pull_request"),
            ("head_branch", "fork"),
            ("path", ".github/workflows/other.yml"),
            ("conclusion", "failure"),
            ("status", "in_progress"),
            ("head_repository", {"full_name": "fork/repo"}),
        ):
            with self.subTest(field=field), self.assertRaises(SystemExit):
                release.validate_run({**run, field: value}, "owner/repo")

    def test_plan_pins_artifact_id_before_later_same_name_upload(self):
        run = {"run_attempt": 2}
        artifacts = {
            "artifacts": [
                {"id": 10, "name": "distributions", "expired": False},
                {"id": 20, "name": "distributions", "expired": False},
                {"id": 30, "name": "other", "expired": False},
            ]
        }
        with (
            patch.dict(os.environ, CI_RUN_ID="1", GITHUB_REPOSITORY="owner/repo"),
            patch.object(release, "gh", side_effect=[run, artifacts]),
            patch.object(release, "validate_run"),
            patch.object(release, "output") as output,
        ):
            release.plan()
        output.assert_called_once_with(run_id="1", artifact_id="20")

    def test_local_dists_ignores_non_distribution_files(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / "dist"
            dist.mkdir()
            (dist / "pkg-1.0.0-py3-none-any.whl").write_bytes(b"wheel")
            (dist / "pkg-1.0.0.tar.gz").write_bytes(b"sdist")
            (dist / ".gitignore").write_text("*\n")
            original = Path.cwd()
            try:
                os.chdir(directory)
                files = release.local_dists()
            finally:
                os.chdir(original)
            self.assertEqual(
                set(files), {"pkg-1.0.0-py3-none-any.whl", "pkg-1.0.0.tar.gz"}
            )

    def test_source_toml_decodes_bytes(self):
        with patch.object(
            release.subprocess,
            "check_output",
            return_value=b'[project]\nversion = "1.2.3"\n',
        ):
            self.assertEqual(release.version_at("sha"), "1.2.3")

    def test_matching_partial_upload_recovers(self):
        self.assertEqual(
            release.missing_files({"wheel": "a", "sdist": "b"}, {"wheel": "a"}),
            ["sdist"],
        )
        self.assertEqual(release.missing_files({"wheel": "a"}, {"wheel": "a"}), [])
        for remote in ({"wheel": "wrong"}, {"unknown": "a"}):
            with self.assertRaises(SystemExit):
                release.missing_files({"wheel": "a"}, remote)

    def test_artifact_identity_and_hashes_fail_closed(self):
        run = {"head_sha": "a"}
        for data in (
            {"sha": "b", "files": {"wheel": "x"}},
            {"sha": "a", "files": {"wheel": "changed"}},
        ):
            with tempfile.TemporaryDirectory() as directory:
                marker = Path(directory) / "release-intent.json"
                marker.write_text(json.dumps(data))
                original = Path.cwd()
                try:
                    os.chdir(directory)
                    with (
                        patch.dict(
                            os.environ, GITHUB_REPOSITORY="owner/repo", CI_RUN_ID="1"
                        ),
                        patch.object(release, "gh", return_value=run),
                        patch.object(release, "validate_run"),
                        patch.object(
                            release, "local_dists", return_value={"wheel": "x"}
                        ),
                        self.assertRaises(SystemExit),
                    ):
                        release.verify()
                finally:
                    os.chdir(original)

    def test_non_main_push_does_not_read_unreachable_before(self):
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            original = Path.cwd()
            try:
                os.chdir(directory)
                with (
                    patch.dict(
                        os.environ,
                        GITHUB_SHA=sha,
                        BEFORE="unreachable",
                        GITHUB_EVENT_NAME="push",
                        GITHUB_REF="refs/heads/team-restructure",
                    ),
                    patch.object(
                        release.subprocess, "check_output", return_value=f"{sha} parent"
                    ),
                    patch.object(
                        release, "version_at", return_value="1.0.0"
                    ) as version,
                    patch.object(release, "local_dists", return_value={}),
                ):
                    release.record()
                version.assert_called_once_with(sha)
                self.assertFalse(
                    json.loads(Path("release-intent.json").read_text())["publish"]
                )
            finally:
                os.chdir(original)

    def test_push_hash_without_zero_is_valid_baseline(self):
        sha, before = "a" * 40, "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            original = Path.cwd()
            try:
                os.chdir(directory)
                with (
                    patch.dict(
                        os.environ,
                        GITHUB_SHA=sha,
                        BEFORE=before,
                        GITHUB_EVENT_NAME="push",
                        GITHUB_REF="refs/heads/main",
                    ),
                    patch.object(
                        release.subprocess,
                        "check_output",
                        return_value=f"{sha} {'c' * 40}",
                    ),
                    patch.object(
                        release,
                        "version_at",
                        side_effect=lambda value: (
                            "1.0.0" if value == before else "1.1.0"
                        ),
                    ),
                    patch.object(release, "local_dists", return_value={}),
                ):
                    release.record()
                self.assertTrue(
                    json.loads(Path("release-intent.json").read_text())["publish"]
                )
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
