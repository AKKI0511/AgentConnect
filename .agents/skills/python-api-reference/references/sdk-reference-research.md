# SDK reference research

Reviewed 2026-10-11. These notes compare selected files and pages. The lessons are our writing recommendations, not company style policies.

Use this as author guidance. Public SDK pages should contain the resulting user instructions, not this research or its source-layout discussion.

## Prime Intellect Verifiers

Revision [bf2834c](https://github.com/PrimeIntellect-ai/verifiers/tree/bf2834cac27d882b6edc9388835791a395361954).

- **Root:** [`verifiers/__init__.py`](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/verifiers/__init__.py) points to `verifiers.v1`. It has no usage example. A separate [overview](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/docs/v1/overview.md) explains the main concepts.
- **Subpackage:** [`v1/__init__.py`](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/verifiers/v1/__init__.py) and [`envs/__init__.py`](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/verifiers/v1/envs/__init__.py) have no module docstrings.
- **Leaf:** [`agent.py`](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/verifiers/v1/agent.py) explains what an Agent represents, who owns resources and what happens when an interaction ends. Its terminology assumes some prior SDK knowledge.
- **Examples:** The [Agent guide](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/docs/v1/agent.md) uses short async fragments. They assume `vf`, an async context and configured services. The second also assumes `agent` and `task`. They show calls and result access, without printed sample output.
- **Complete example:** [`examples/agent.py`](https://github.com/PrimeIntellect-ai/verifiers/blob/bf2834cac27d882b6edc9388835791a395361954/examples/agent.py) adds imports, an async runner, cleanup and printed results. It states the API-key requirement.

**Lesson:** Use focused reference fragments with named setup. Explain ownership where it affects the call; keep complete application setup in guides. Leave internal organization out of user guidance.

## Anthropic Python client

Revision [b4b7916](https://github.com/anthropics/anthropic-sdk-python/tree/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f).

- **Root:** [`anthropic/__init__.py`](https://github.com/anthropics/anthropic-sdk-python/blob/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f/src/anthropic/__init__.py) exports names and has no module docstring or example.
- **Subpackage:** [Messages initializer](https://github.com/anthropics/anthropic-sdk-python/blob/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f/src/anthropic/resources/messages/__init__.py) also has no module overview. [`api.md`](https://github.com/anthropics/anthropic-sdk-python/blob/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f/api.md) supplies type and method lookup.
- **Leaf:** [`messages.py`](https://github.com/anthropics/anthropic-sdk-python/blob/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f/src/anthropic/resources/messages/messages.py) puts detailed argument prose on `create` overloads. JSON examples explain message roles and content shapes. The `stream` helper has only a short summary.
- **Examples:** The [README](https://github.com/anthropics/anthropic-sdk-python/blob/b4b7916deaf4e5570cd627b1ae7ee4394a4de39f/README.md) supplies imports, credentials, client creation, a request and printed content. The [Python guide](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python) covers async calls, streaming and errors. Later fragments reuse earlier setup.

**Lesson:** Put a small value example beside an ambiguous parameter. Keep full setup in the starting guide. Add local prerequisites when a method example will be read alone.

## OpenAI Python client

Revision [3c50399](https://github.com/openai/openai-python/tree/3c5039945fa0e1fc3bf41e970beb5274f6bdba96).

- **Root:** [`openai/__init__.py`](https://github.com/openai/openai-python/blob/3c5039945fa0e1fc3bf41e970beb5274f6bdba96/src/openai/__init__.py) has no module overview or usage example.
- **Subpackage:** [Responses initializer](https://github.com/openai/openai-python/blob/3c5039945fa0e1fc3bf41e970beb5274f6bdba96/src/openai/resources/responses/__init__.py) exports classes without an overview. [`api.md`](https://github.com/openai/openai-python/blob/3c5039945fa0e1fc3bf41e970beb5274f6bdba96/api.md) groups types and methods by resource.
- **Leaf:** [`responses.py`](https://github.com/openai/openai-python/blob/3c5039945fa0e1fc3bf41e970beb5274f6bdba96/src/openai/resources/responses/responses.py) has a short class summary. `create` overloads explain parameters and link feature guides, with no fenced usage examples. They cover user-visible effects such as instruction reuse.
- **Examples:** The [README](https://github.com/openai/openai-python/blob/3c5039945fa0e1fc3bf41e970beb5274f6bdba96/README.md) introduces a client, makes a request and reads output. Separate sections cover async use, streaming, pagination and errors. Later snippets assume earlier setup; a runner or loop appears when it teaches that feature.

**Lesson:** Explain parameter interactions beside the call. Link setup and extended workflows, while retaining advanced facts that change caller choices or results. Repeating long generated descriptions across overloads is not a writing goal.

## OpenAI Agents SDK

Revision [125efa0](https://github.com/openai/openai-agents-python/tree/125efa029b4bfd84238bd2c4fd69c3406f802663).

- **Root:** [`agents/__init__.py`](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/__init__.py) has no module overview. It exports names and defines configuration helpers.
- **Subpackage:** [MCP initializer](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/mcp/__init__.py) has no module docstring. The [MCP reference page source](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/ref/mcp/server.md) selects the defining module for rendering.
- **Leaf:** [`agent.py`](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/agent.py) explains the Agent on the class and documents fields individually. `clone` explains shared lists; `as_tool` explains how control differs from handoffs.
- **Examples:** `clone` has a one-call fragment that assumes an existing agent. Simple operations in [`mcp/server.py`](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/mcp/server.py) have short descriptions without examples. Construction and cleanup rules stay near the objects that require them.
- **Call constraints:** [`run.py`](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/run.py) explains results, termination and errors. `run_sync` states its event-loop restriction. The [published Agent reference](https://openai.github.io/openai-agents-python/ref/agent/) exposes the source docstrings as symbol documentation.

**Lesson:** Spend words on choices, shared state and required cleanup. Keep obvious calls short. Each method does not need a full application.

## LangChain Core

Revision [e4b1437](https://github.com/langchain-ai/langchain/tree/e4b143729ffb3c6307376909d3aa9921b360c1f5).

- **Root:** [`langchain_core/__init__.py`](https://github.com/langchain-ai/langchain/blob/e4b143729ffb3c6307376909d3aa9921b360c1f5/libs/core/langchain_core/__init__.py) explains the package's role and says integrations live elsewhere. It has no code example.
- **Subpackage:** [`language_models/__init__.py`](https://github.com/langchain-ai/langchain/blob/e4b143729ffb3c6307376909d3aa9921b360c1f5/libs/core/langchain_core/language_models/__init__.py) distinguishes chat models from text LLMs and links the relevant classes. It explains local terms without teaching Python. The [published page](https://reference.langchain.com/python/langchain-core/language_models) includes this overview.
- **Leaf:** [`chat_models.py`](https://github.com/langchain-ai/langchain/blob/e4b143729ffb3c6307376909d3aa9921b360c1f5/libs/core/langchain_core/language_models/chat_models.py) has a one-sentence module summary. `BaseChatModel` compares methods and separates calling from subclassing.
- **Examples:** `with_structured_output` shows schema variants and their output shapes. Its undefined `ChatModel` is a placeholder, so these snippets are not standalone programs. The [published method page](https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel/with_structured_output) preserves those examples.
- **Small working examples:** [`runnables/base.py`](https://github.com/langchain-ai/langchain/blob/e4b143729ffb3c6307376909d3aa9921b360c1f5/libs/core/langchain_core/runnables/base.py) uses arithmetic to show composition and expected results without provider setup. Async fragments assume an async context. Basic `invoke` has no separate example.

**Lesson:** Explain choices at the package or class level. Use examples where an input or result teaches useful behavior. Keep outputs small when possible, name assumed objects and async requirements, and avoid replacing a real integration with a toy merely to make it deterministic.

## Cursor Python SDK

Inspected [`cursor-sdk` 1.0.37](https://pypi.org/project/cursor-sdk/1.0.37/) from its Windows wheel without installing or running it. [Versioned metadata](https://pypi.org/pypi/cursor-sdk/1.0.37/json) identifies the archive.

- **Root:** `cursor_sdk/__init__.py` exports names without a module docstring.
- **Subpackage equivalent:** The package is mostly flat. `cursor_sdk/asyncio.py` is its public async namespace, rather than a nested initializer. It includes imports, an async runner, client cleanup, event iteration and result status. Credentials are placeholders.
- **Leaf:** `_agent.py` and `_run.py` mix user-relevant behavior with internal implementation notes. `Agent.create` and `Run.wait` lack docstrings in this wheel. `Run.text` explains that it can block.
- **Published examples:** The [Python SDK page](https://cursor.com/docs/sdk/python) explains runtime choices, setup and operations. Initial examples create objects; later snippets assume existing ones. Context managers show cleanup, and the async section explains client ownership.

**Lesson:** Borrow the user choices and cleanup examples. Omit internal implementation notes. Sparse source docstrings do not imply that the public reference should be sparse too.

Archive: `cursor_sdk-1.0.37-py3-none-win_amd64.whl`.
SHA-256: `90c03382c5193c7988d1b901d5c8415f0eb57d9017857b2997842b4f115a7ca9`.

## What to carry forward

| Reader need | Writing choice |
| --- | --- |
| Understand the SDK | One plain purpose sentence, essential local nouns and an optional focused integration fragment. |
| Use a subpackage | Self-contained purpose, prerequisites and how to use its entry point. |
| Choose between APIs | Explain the difference where the choice appears. |
| Make one call correctly | Name assumed objects locally; explain relevant inputs, result states and errors. |
| Understand a difficult value | Show a small input or output shape. |
| Handle state or resources | Explain the action the caller must take. |
| Look up a simple property | Give its meaning; skip an example that adds nothing. |

An empty initializer can mean another page owns the introduction. Check the published reference before copying that structure. Keep essential context beside methods that readers may find through search.

## Repeat the research

1. Pin an official source revision or distribution version.
2. Inspect the root, a subpackage and a defining module. Record any missing equivalent.
3. Compare a class, simple method, complex method and field with their published pages. Check inherited docs and overloads.
4. For each example, note imports, assumed objects, setup, cleanup and shown results. Decide whether it is a program, fragment or value shape.
5. Record useful patterns and gaps separately. Copy a pattern only if it helps a caller.

This was a sample, not a full audit. Provider-backed examples were not run. Published pages were read as served text/HTML; their versions may differ from pinned source. Prime's older hosted reference was unavailable, so its current v1 source guides supplied that evidence.
