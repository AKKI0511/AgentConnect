#!/usr/bin/env python3
"""Generate the Sphinx website from API templates and source pages.

API RST under ``docs/source/api/`` is produced here, including ``index.rst``.
Templates live in ``docs/apidoc-templates/``, outside that output directory.
HTML is built with Sphinx warnings treated as errors.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DOCS_DIR = PROJECT_ROOT / "docs"
SOURCE_DIR = DOCS_DIR / "source"
API_DIR = SOURCE_DIR / "api"
BUILD_DIR = DOCS_DIR / "build"
HTML_DIR = BUILD_DIR / "html"
TEMPLATE_DIR = DOCS_DIR / "apidoc-templates"
INDEX_TEMPLATE = TEMPLATE_DIR / "index.rst"


def run_command(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("Running:", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def clean_api_docs() -> None:
    print("Cleaning generated API RST...")
    if API_DIR.exists():
        for path in API_DIR.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    API_DIR.mkdir(parents=True, exist_ok=True)


def clean_build() -> None:
    print("Cleaning HTML build directory...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)


def generate_api_docs() -> None:
    if not INDEX_TEMPLATE.is_file():
        raise SystemExit(f"missing API index template: {INDEX_TEMPLATE}")
    print("Generating API documentation...")
    API_DIR.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            sys.executable,
            "-m",
            "sphinx.ext.apidoc",
            "-f",
            "-e",
            "-M",
            "-T",
            "-t",
            str(TEMPLATE_DIR),
            "-o",
            str(API_DIR),
            str(PROJECT_ROOT / "agentconnect"),
        ]
    )
    shutil.copyfile(INDEX_TEMPLATE, API_DIR / "index.rst")
    if not (API_DIR / "agentconnect.rst").is_file():
        raise SystemExit("sphinx-apidoc did not write agentconnect.rst")


def build_html() -> None:
    print("Building HTML documentation...")
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    # -W: import failures, missing refs, and other Sphinx warnings fail the build.
    # --keep-going: report every warning before exiting.
    # -n: nit-picky internal references (same as nitpicky = True in conf.py).
    run_command(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "--keep-going",
            "-n",
            "-b",
            "html",
            str(SOURCE_DIR),
            str(HTML_DIR),
        ]
    )
    index = HTML_DIR / "index.html"
    api_index = HTML_DIR / "api" / "index.html"
    api_root = HTML_DIR / "api" / "agentconnect.html"
    missing = [str(path) for path in (index, api_index, api_root) if not path.is_file()]
    if missing:
        raise SystemExit("Sphinx HTML output is missing: " + ", ".join(missing))
    print(f"Documentation built. Open {index}")


def serve_preview(*, host: str, port: int) -> None:
    if not (HTML_DIR / "index.html").is_file():
        raise SystemExit("HTML docs are missing. Build them before previewing.")
    print(f"Serving documentation at http://{host}:{port}/")
    print("Press Ctrl+C to stop the local preview.")
    run_command(
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            host,
            "--directory",
            str(HTML_DIR),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate AgentConnect Sphinx documentation"
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Remove generated API RST and the HTML build directory, then exit",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Regenerate API RST only; do not build HTML",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Build HTML and serve it at 127.0.0.1",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Preview bind address")
    parser.add_argument("--port", type=int, default=8000, help="Preview port")
    args = parser.parse_args()

    if args.clean_only:
        clean_api_docs()
        clean_build()
        return

    clean_api_docs()
    generate_api_docs()
    if args.api_only:
        return
    clean_build()
    build_html()
    if args.preview:
        serve_preview(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
