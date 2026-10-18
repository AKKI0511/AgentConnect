"""Load a Team file for `agentconnect.toml` and `[tool.agentconnect]`.

A Team file names the Team, the store, the embedding choice, the Agents
this process constructs, and extra MCP tools. [`Team`][agentconnect.team.runtime.Team]
started in Python needs no file. Secrets stay in the environment.

`agents` maps canonical Agent names to
[`HostedAgentConfig`][agentconnect.config.models.HostedAgentConfig].
`entrypoint` is a [`BaseAgent`][agentconnect.agent.base.BaseAgent] subclass
or a synchronous factory. Both receive `name=<mapping key>` plus optional
`kwargs`. Independently deployed Agents join by URL and are not listed.

[`load_team_config`][agentconnect.config.loaders.load_team_config] chooses
the file.

Examples:
    From a directory that contains a Team file:

    ```python
    from agentconnect.config import load_team_config

    config = load_team_config()
    for name, spec in config.agents.items():
        print(name, spec.entrypoint)
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
