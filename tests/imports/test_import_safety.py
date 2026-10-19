import importlib
import sys


def test_top_level_import_has_version_and_no_crash():
    mod = importlib.import_module("agentconnect")
    assert hasattr(mod, "__version__")


def test_top_level_import_does_not_call_metadata_version_until_accessed():
    script = (
        "import sys\n"
        "import importlib.metadata as metadata\n"
        "calls = []\n"
        "original = metadata.version\n"
        "def tracking_version(name):\n"
        "    calls.append(name)\n"
        "    return original(name)\n"
        "metadata.version = tracking_version\n"
        "sys.modules.pop('agentconnect', None)\n"
        "import agentconnect\n"
        "assert calls == [], calls\n"
        "version = agentconnect.__version__\n"
        "assert isinstance(version, str) and version\n"
        "assert calls == [agentconnect.__package__], calls\n"
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_top_level_package_does_not_lazy_export_core():
    script = (
        "import agentconnect\n"
        "import importlib\n"
        "assert 'core' not in agentconnect.__all__\n"
        "try:\n"
        "    agentconnect.core\n"
        "except AttributeError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('core must not be a top-level lazy export')\n"
        "core = importlib.import_module('agentconnect.core')\n"
        "assert core.__name__ == 'agentconnect.core'\n"
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_import_team_directory_without_torch_or_qdrant(monkeypatch):
    for name in [
        "torch",
        "sentence_transformers",
        "fastembed",
        "qdrant_client",
        "litellm",
        "tiktoken",
    ]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.team.directory")
    assert hasattr(mod, "HashedEmbedder")
    assert hasattr(mod, "Embedder")
    assert not hasattr(mod, "Directory")


def test_index_service_imports():
    module = importlib.import_module("agentconnect.index.service")
    assert module.app is not None
    assert hasattr(module, "create_index_app")


def test_human_agent_imports_without_aioconsole():
    sys.modules.pop("agentconnect.prebuilt.human_agent", None)
    sys.modules.pop("aioconsole", None)
    mod = importlib.import_module("agentconnect.prebuilt.human_agent")
    assert hasattr(mod, "HumanAgent")
    assert "aioconsole" not in sys.modules


def test_prebuilt_aiagent_imports_without_optional_helpers():
    for name in ["aiogram", "aioconsole", "litellm"]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.prebuilt")
    assert hasattr(mod, "AIAgent")


def test_embedded_team_import_does_not_load_serve_or_redis():
    script = (
        "from agentconnect.team import Team\n"
        "assert Team is not None\n"
        "mods = __import__('sys').modules\n"
        "assert 'fastapi' not in mods\n"
        "assert 'mcp' not in mods\n"
        "assert 'redis' not in mods\n"
        "assert 'typer' not in mods\n"
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
