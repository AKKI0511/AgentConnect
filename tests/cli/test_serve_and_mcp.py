from unittest import mock

import types


def test_serve_registry_constructs_uvicorn_run():
    # Patch importlib.import_module used by the CLI to supply stubs
    run_mock = mock.Mock()

    uvicorn_stub = types.SimpleNamespace(run=run_mock)

    class RegistryAPISettings:  # minimal stub
        def __init__(self):
            self.host = "localhost"
            self.port = 8000
            self.reload = False
            self.log_level = "INFO"

    cfg_stub = types.SimpleNamespace(RegistryAPISettings=RegistryAPISettings)

    def create_registry_api_app(settings):  # pragma: no cover - trivial stub
        return object()

    srv_stub = types.SimpleNamespace(create_registry_api_app=create_registry_api_app)

    def importer(name: str):
        if name == "uvicorn":
            return uvicorn_stub
        if name == "agentconnect.config.servers":
            return cfg_stub
        if name == "agentconnect.index.service":
            return srv_stub
        raise ImportError(name)

    with mock.patch(
        "agentconnect.cli.serve.importlib.import_module", side_effect=importer
    ):
        from agentconnect.cli import serve as serve_mod

        serve_mod.registry(host="127.0.0.1", port=8001)
        assert run_mock.called
