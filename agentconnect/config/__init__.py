"""Team file loading for AgentConnect.

``agentconnect.toml`` or ``[tool.agentconnect]`` in ``pyproject.toml``
describes a Team the CLI starts. Discovery is nearest-directory first.
Embedded ``Team("name").start()`` needs no file.

    from agentconnect.config import TeamConfig, load_team_config

    config = load_team_config()
    print(config.team, config.port)
"""

from agentconnect.config.loaders import (
    find_config_file,
    load_selected_team,
    load_team_config,
    render_example_toml,
    save_example_config,
    validate_config_file,
)
from agentconnect.config.models import HostedAgentConfig, TeamConfig
from agentconnect.config.servers import RegistryAPISettings

__all__ = [
    "TeamConfig",
    "HostedAgentConfig",
    "RegistryAPISettings",
    "load_team_config",
    "load_selected_team",
    "find_config_file",
    "render_example_toml",
    "save_example_config",
    "validate_config_file",
]
