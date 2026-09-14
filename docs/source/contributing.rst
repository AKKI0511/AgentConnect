Contributing
============

Development setup
-----------------

Install `uv <https://docs.astral.sh/uv/getting-started/installation/>`_
and use Python 3.11 through 3.14.

.. code-block:: bash

   git clone https://github.com/AKKI0511/AgentConnect.git
   cd AgentConnect
   uv sync --extra serve --extra cli --extra index

Use your fork's URL if contributing through a fork. Pull requests
target ``main``.

Tests and code style
--------------------

.. code-block:: bash

   uv run --extra serve --extra cli --extra index pytest tests/ -q
   uvx ruff@latest check agentconnect tests examples docs/generate_docs.py
   uvx ruff@latest format agentconnect tests examples docs/generate_docs.py

A test file or directory can replace ``tests/``. Routine tests do not
need provider API keys. Optional Ruff commit hooks are available with
``uvx pre-commit@latest install``.

Public API
----------

The public schema is in
`spec/schema/schema.ts <https://github.com/AKKI0511/AgentConnect/blob/main/spec/schema/schema.ts>`_;
its Python models are in
`agentconnect/core/ <https://github.com/AKKI0511/AgentConnect/tree/main/agentconnect/core>`_.
Changes to public fields need matching definitions. With Node LTS installed:

.. code-block:: bash

   npm --prefix spec/schema ci
   npm --prefix spec/schema run generate
   npm --prefix spec/schema run check

Package boundaries and generated-file locations are listed in
`AGENTS.md <https://github.com/AKKI0511/AgentConnect/blob/main/AGENTS.md>`_.

Documentation
-------------

For a complete website preview, run from the repository root:

.. code-block:: bash

   uv run --group docs --extra serve --extra cli python docs/generate_docs.py --preview

Open http://127.0.0.1:8000/ and stop the server with Ctrl+C.
``make docs-preview`` is a shortcut. Without ``--preview``, the command
builds HTML without serving it.

SDK docstrings use Google-style sections. Under ``Examples:``, an
indented ``.. code-block:: python`` followed by a blank line and further
indented code produces a highlighted Python example. All API RST,
including its index, is generated. Edit SDK docstrings or templates
rather than the generated files.

The `docs README <https://github.com/AKKI0511/AgentConnect/blob/main/docs/README.md>`_
contains a complete docstring example and the documentation folder map.
The :doc:`changelog` includes the root
`CHANGELOG.md <https://github.com/AKKI0511/AgentConnect/blob/main/CHANGELOG.md>`_,
so release notes only need one edit. Website publishing is limited to
``main``; previews run locally.

Pull requests
-------------

* Describe the problem and the change.
* Include tests for changed behavior and note what you ran.
* Update affected documentation and user-facing release notes.
* Keep unrelated changes in separate pull requests.

An issue is useful for discussing substantial features before
implementation. Small fixes can go straight to a pull request.
AI-assisted contributions follow the same review process.

Code of conduct
---------------

The :doc:`code_of_conduct` applies to contributions and discussions.

License
-------

Contributions are distributed under the project's
`Apache 2.0 license <https://github.com/AKKI0511/AgentConnect/blob/main/LICENSE>`_.
