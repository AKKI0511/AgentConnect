"""Team file loading for `agentconnect.toml` and `[tool.agentconnect]`.

A Team file describes a Team the CLI starts: name, store, embeddings,
hosted Agents, and extra MCP tools. Embedded `Team("name").start()`
needs no file. Secrets stay in the environment.

Discovery is nearest-directory first and never merged. In each directory,
`agentconnect.toml` beats `[tool.agentconnect]` in `pyproject.toml`.
YAML is last-resort compatibility after no ancestor TOML Team file
exists. `load_team_config(path)` loads that path and does not fall back.

`TeamConfig` and `HostedAgentConfig` are the file models. `class` is a
`BaseAgent` subclass or a function `create(name) -> BaseAgent` that
returns an unjoined Agent. Agents listed here are hosted by this process.
Independently deployed Agents join by URL and are not listed.

`RegistryAPISettings` (and Index vector settings in
`agentconnect.config.vector`) configure the optional Index process from
the environment, not the Team file.

Examples:
    From a directory that contains a Team file:

    ```python
    from agentconnect.config import TeamConfig, load_team_config

    config: TeamConfig = load_team_config()
    print(config.team, config.port)
    for spec in config.agents:
        print(spec.name, spec.class_path)
    ```
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
