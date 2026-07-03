SDK YAML & CLI
==============

.. _sdk_configuration:

``agentconnect.yaml`` is the optional project-level configuration file for the SDK.
All settings have safe defaults — nothing breaks without it. You need it when you want to
persist non-default behavior across your project: point the SDK at a remote registry,
switch vector storage, tune client timeouts, or give your whole team a consistent baseline
without repeating constructor arguments everywhere.

Quickstart
----------

.. code-block:: bash

    agentconnect config init

Creates ``agentconnect.yaml`` in the current directory from a bundled template.
The first thing most developers change:

.. code-block:: yaml

    clients:
      registry:
        base_url: "http://your-registry-host:8000"   # default: http://localhost:8000

Everything else works fine with its default for local development.

How it works
------------

**Three-tier precedence** (highest to lowest):

1. Runtime kwargs — passed to :func:`~agentconnect.config.load_settings`
2. ``agentconnect.yaml`` — discovered automatically at startup
3. Hard-coded defaults — used when no file is found

The SDK never reads environment variables for general configuration. Environment variables
are reserved for secrets and consumed directly by the subsystems that need them (provider
SDKs, Qdrant auth, payment keys). See `Secrets`_ below.

.. admonition:: Servers are separate
   :class: note

   Standalone servers are configured exclusively via environment variables — they do not
   read ``agentconnect.yaml``. See :doc:`../core/discovery/discovery_registry_remote` for
   the full ``AGENTCONNECT_REGISTRY_*`` variable list.

CLI reference
-------------

.. code-block:: bash

    agentconnect config init             # create agentconnect.yaml in the current directory
    agentconnect config init --force     # overwrite an existing file

    agentconnect config show             # print effective settings (secrets redacted)

    agentconnect config validate agentconnect.yaml   # exits 0 = valid, 1 = invalid; CI-friendly

``show`` outputs YAML if PyYAML is installed, otherwise JSON.

YAML reference
--------------

.. code-block:: yaml

    project_name: "AgentConnect"

    registry:
      vector_search:
        model_name: "sentence-transformers/all-mpnet-base-v2"
        cache_folder: "./.cache/huggingface/embeddings"
        vector_store_path: "./.cache/vector_stores"
        deployment:
          type: "in_memory"           # dev default; change for staging/prod
          # type: "local_file"
          #   path: "./local_qdrant_db"
          # type: "remote"
          #   url: "http://localhost:6333"   # QDRANT_API_KEY read from env if set
        # advanced: timeout, grpc_port, prefer_grpc, use_quantization,
        #           vectors_on_disk, index_on_disk, batch_size

    communication:
      enable_message_history: true    # set false for high-throughput workloads

    clients:
      registry:
        base_url: "http://localhost:8000"
        default_timeout: 30.0
        connect_timeout: 10.0
        read_timeout: 30.0
        pool_timeout: 10.0
        max_connections: 10
        max_keepalive_connections: 5
        # retries: max_retries, retry_backoff_factor, retryable_status_codes

    mcp:
      agent_discovery:
        enabled: true
        top_k: 5
        strictness: 0.2               # similarity threshold 0.0–1.0
        output_detail: "summary"      # minimal | summary | capabilities | full

    payments:
      default_token_symbol: "USDC"
      wallet_data_dir: "data/agent_wallets"

See the `full example file <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/config/agentconnect.example.yaml>`_
or :mod:`agentconnect.config.models` for field-level descriptions and constraints.

Using settings in code
-----------------------

Most SDK components consume the global ``settings`` singleton automatically — you rarely
need to touch it. When you do, there are four patterns depending on your situation.

.. rubric:: Which pattern do I need?

- **Just have a YAML file** and instantiate components normally → `Automatic (zero code)`_
- **Read a config value** in your own code → `Read typed settings`_
- **Override for a test or script** without editing files → `Runtime override with load_settings`_
- **Bypass YAML entirely** and build config programmatically → `Build from scratch`_

Automatic (zero code)
~~~~~~~~~~~~~~~~~~~~~

The global :data:`~agentconnect.config.settings` singleton is loaded at import time and
consumed internally by every SDK component:

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - Component
     - Settings path it reads
   * - :class:`~agentconnect.clients.registry_client.RegistryAPIClient`
     - ``settings.clients.registry``
   * - :class:`~agentconnect.core.registry.AgentRegistry`
     - ``settings.registry.vector_search``
   * - :class:`~agentconnect.communication.hub.CommunicationHub`
     - ``settings.communication.enable_message_history``
   * - MCP registry server
     - ``settings.mcp.agent_discovery``
   * - Wallet manager
     - ``settings.payments.wallet_data_dir``

Just have a valid ``agentconnect.yaml`` and construct these components normally — they
pick up the configuration with no extra code.

Read typed settings
~~~~~~~~~~~~~~~~~~~

Every value in the settings tree is a typed Pydantic field. Your IDE will autocomplete
and type-check all of it:

.. code-block:: python

    from agentconnect.config import settings

    # Client settings
    url: str           = settings.clients.registry.base_url
    timeout: float     = settings.clients.registry.default_timeout
    pool_size: int     = settings.clients.registry.max_connections

    # Registry / vector search
    vs = settings.registry.vector_search          # VectorSearchSettings
    deployment_type    = vs.deployment.type       # "in_memory" | "local_file" | "remote"
    model_name: str    = vs.model_name
    use_quant: bool    = vs.advanced.use_quantization

    # MCP discovery
    mcp = settings.mcp.agent_discovery            # MCPAgentDiscoverySettings
    top_k: int         = mcp.top_k
    strictness: float  = mcp.strictness

    # Payments
    symbol: str        = settings.payments.default_token_symbol
    wallet_dir: str    = settings.payments.wallet_data_dir

    # Communication
    history: bool      = settings.communication.enable_message_history

If you need to access a deployment-specific field (e.g., the ``path`` for ``local_file``),
check the ``type`` discriminator first:

.. code-block:: python

    from agentconnect.config.models import LocalFileConfig

    dep = settings.registry.vector_search.deployment
    if isinstance(dep, LocalFileConfig):
        print(dep.path)   # only available on LocalFileConfig

Runtime override with load_settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:func:`~agentconnect.config.load_settings` merges keyword arguments on top of the YAML
and returns a **new** :class:`~agentconnect.config.models.AgentConnectSettings` instance.
It does **not** mutate the global ``settings`` object.

.. code-block:: python

    from agentconnect.config import load_settings

    cfg = load_settings(
        clients={"registry": {"base_url": "http://staging:8000", "default_timeout": 15.0}},
        registry={"vector_search": {"deployment": {"type": "in_memory"}}},
    )

    # Access is identical to the global singleton — fully typed
    url: str   = cfg.clients.registry.base_url
    timeout    = cfg.clients.registry.default_timeout

Use the resulting object to pass explicit values to constructors, or extract individual
fields and pass them as constructor arguments.

Build from scratch
~~~~~~~~~~~~~~~~~~

Use the model classes directly to construct a settings object programmatically — no YAML
file needed. Pydantic validates all values at construction time.

.. code-block:: python

    from agentconnect.config.models import (
        AgentConnectSettings,
        ClientSettings,
        RegistryClientSettings,
        RegistrySettings,
        VectorSearchSettings,
        RemoteConfig,
    )

    cfg = AgentConnectSettings(
        clients=ClientSettings(
            registry=RegistryClientSettings(
                base_url="http://prod-registry:8000",
                default_timeout=60.0,
                max_connections=20,
            )
        ),
        registry=RegistrySettings(
            vector_search=VectorSearchSettings(
                deployment=RemoteConfig(url="http://qdrant-prod:6333")
            )
        ),
    )

    url = cfg.clients.registry.base_url          # "http://prod-registry:8000"
    dep = cfg.registry.vector_search.deployment  # RemoteConfig instance

This is also the cleanest pattern for dependency injection in tests — construct a
``AgentConnectSettings`` with controlled values and pass extracted fields directly to
the components under test.

Type hints in your own functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Import specific model classes when you want typed parameters in your own code:

.. code-block:: python

    from agentconnect.config.models import RegistryClientSettings, MCPAgentDiscoverySettings

    def build_client(cfg: RegistryClientSettings) -> None:
        print(cfg.base_url, cfg.default_timeout)

    # Pass the subsection directly from the singleton
    build_client(settings.clients.registry)

All available model classes: :mod:`agentconnect.config.models`.

File discovery & multiple environments
---------------------------------------

The loader searches in this order at startup:

1. Current working directory (``./agentconnect.yaml``)
2. Nearest ancestor directory containing ``pyproject.toml``
3. Up to 5 parent directories

**Recommended**: place ``agentconnect.yaml`` at your project root and commit it. Every
developer and CI run gets the same baseline without any setup step.

**Multi-service or multi-environment** — several options:

- Run each service from its own working directory, each with its own ``agentconnect.yaml``.
- Keep a single file at the project root and use :func:`~agentconnect.config.load_settings`
  overrides in any process that needs different values (e.g., staging URL in integration tests).
- Bypass file discovery entirely by constructing
  :class:`~agentconnect.config.models.AgentConnectSettings` from a dict or model kwargs.

Secrets
-------

``agentconnect.yaml`` is for non-secret developer defaults only.

**Belongs in YAML**: registry URL, vector store type and paths, client timeouts,
MCP search defaults, wallet data directory, token symbol.

**Never in YAML**: API keys, private keys, passwords, tokens — these go in environment
variables and are read directly by the subsystems that need them
(``OPENAI_API_KEY``, ``QDRANT_API_KEY``, ``CDP_API_KEY_*``, etc.).

Troubleshooting
---------------

- **YAML not found**: run ``agentconnect config init`` in your project root, or run
  ``agentconnect config show`` to confirm what defaults are in effect.
- **YAML syntax error**: run ``agentconnect config validate agentconnect.yaml``.
- **Client using wrong URL**: check ``clients.registry.base_url`` in YAML; settings
  load at import time so restart the process after editing.
- **PyYAML not installed**: ``agentconnect config show`` falls back to JSON; install
  ``pyyaml`` to restore YAML output.

Next steps
----------

- :doc:`../core/discovery/discovery_registry_remote` — run the Registry server; full
  ``AGENTCONNECT_REGISTRY_*`` environment variable reference.
- :doc:`../integrations/mcp/discovery_mcp` — configure the MCP discovery tool
  (``mcp.agent_discovery`` section).
- :mod:`agentconnect.config.models` — complete API reference for all settings models.
