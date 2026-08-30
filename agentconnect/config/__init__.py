"""Team file loading for AgentConnect.

``agentconnect.yaml`` describes a Team the CLI starts. Embedded
``Team("name").start()`` needs no file.

    from agentconnect.config import TeamConfig, load_team_config

    config = load_team_config()
    print(config.team, config.port)
"""

from agentconnect.config.loaders import (
    find_config_file,
    load_team_config,
    render_example_yaml,
    save_example_config,
    validate_config_file,
)
from agentconnect.config.models import (
    HostedAgentConfig,
    PaymentsSettings,
    TeamConfig,
    VectorSearchSettings,
)
from agentconnect.config.servers import RegistryAPISettings

__all__ = [
    "TeamConfig",
    "HostedAgentConfig",
    "PaymentsSettings",
    "VectorSearchSettings",
    "RegistryAPISettings",
    "load_team_config",
    "find_config_file",
    "render_example_yaml",
    "save_example_config",
    "validate_config_file",
]
