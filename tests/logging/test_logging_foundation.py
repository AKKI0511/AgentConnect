import logging


def test_import_adds_nullhandler_and_no_root_handlers():
    root_logger = logging.getLogger()
    before = len(root_logger.handlers)
    import agentconnect  # noqa: F401

    after = len(root_logger.handlers)
    assert before == after
    pkg_logger = logging.getLogger("agentconnect")
    assert any(isinstance(h, logging.NullHandler) for h in pkg_logger.handlers)


def test_importing_server_and_mcp_adds_no_handlers():
    root_logger = logging.getLogger()
    before = len(root_logger.handlers)
    import agentconnect.servers.registry_api_server  # noqa: F401
    import agentconnect.mcp.registry_mcp_server  # noqa: F401

    after = len(root_logger.handlers)
    assert before == after
