"""Team file loading for `agentconnect.toml` and `[tool.agentconnect]`.

A Team file names the Team, the store, the embedding choice, the Agents
this process constructs, and extra MCP tools. `Team("name").start()`
needs no file. Secrets stay in the environment.

`class` is a `BaseAgent` subclass or `create(name) -> BaseAgent` that
returns an unjoined Agent. `agentconnect up` constructs the listed
Agents. Agents in other processes join by URL and are not listed.

[`load_team_config`][agentconnect.config.loaders.load_team_config] chooses
the file.

Examples:
    From a directory that contains a Team file:

    ```python
    from agentconnect.config import load_team_config

    config = load_team_config()
    for spec in config.agents:
        print(spec.name, spec.class_path)
    ```
"""

from agentconnect.config.loaders import (
    find_config_file,
    load_selected_team,
    load_team_config,
    render_example_toml,
)
from agentconnect.config.models import HostedAgentConfig, TeamConfig

__all__ = [
    "TeamConfig",
    "HostedAgentConfig",
    "load_team_config",
    "load_selected_team",
    "find_config_file",
    "render_example_toml",
]
