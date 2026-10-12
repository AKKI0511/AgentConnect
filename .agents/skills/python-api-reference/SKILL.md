---
name: python-api-reference
description: Write and review Python SDK API references from package, module, class and function docstrings, including usage examples and generated reference rendering. Use for human and coding-agent readers of SDK documentation, not MCP tool descriptions or runtime prompts.
---

# Python API reference writing

Write for a caller who can see the reference but has never read the repository. Explain what they can accomplish and the conditions for using it correctly. Read the actual signature and behavior first; do not invent a simpler API.

This skill owns reference content and its rendering. Tool catalogs, parameter instructions delivered to models and MCP server prompts belong to agent-tool design; preserve that text during documentation edits.

## Put information at its owning level

| Surface | Content | Examples |
| --- | --- | --- |
| Package `__init__.py` | Purpose, capabilities, main entry points and which to choose. If this becomes a landing page, link to the relevant API references. | Optional compact orientation example. Link to a complete quickstart when setup dominates. |
| Individual module | Its specific capability and how related public objects fit together. Do not repeat the package overview. | Only when composing those objects teaches something the object references do not. |
| Class / constructor | What an instance represents, construction choices, owned resources and lifetime. Let the generator merge constructor parameters when supported. | A small construction/use example if the shape is not obvious. |
| Function / method | Action and result; meaningful parameter semantics, side effects and recoverable errors. | One focused call or a useful variation. No example required for an obvious accessor. |
| Property / field / alias | Meaning, valid values and relevant mutability, units or omission rules. | Only to clarify a non-obvious value or distinction. |

## Keep examples focused and honest

- A reference snippet need not be an executable application. State its prerequisites locally: an existing configured client, joined participant, open resource or async context. Never leave a prerequisite implicit or pretend a fragment is standalone.
- Show the SDK operation and a meaningful result. Include imports when introducing a type. Prefer ordinary sample inputs over invented business frameworks or large dummy implementations.
- Keep startup, authentication setup, subclass scaffolding, polling, retry loops and `asyncio.run()` in one complete example. Repeat them only when that mechanism is the subject. A streaming example may need a loop; a method reference usually does not need its own application runner.
- Never shorten away correctness: distinguish pending from completed results before accessing state-specific fields; show ownership/cleanup where resources are created. Do not invent a convenience helper to hide required SDK calls.
- Test snippets with setup in the verification harness. Publish only the relevant snippet; tests can carry the scaffolding. Full runnable examples must include their own setup and cleanup.

For example, a method example can say “For an existing `httpx.Client` with `base_url` configured:” and show:

```python
response = client.get("/items", params={"limit": 10})
response.raise_for_status()
print(response.json())
```

## Write and render

Lead with a concrete action or capability. Delete architecture tours, storage algorithms, bug histories and repeated glossary prose. Keep caller-relevant facts such as authentication requirements, persistence limits, timeout semantics and secret handling. Explain an unfamiliar public term once; use exact API names when needed.

Use Google-style `Args:`, `Returns:` / `Yields:`, `Raises:`, `Attributes:` and `Examples:` only where useful. Annotations supply types and defaults; prose explains meaning. Use Markdown inline code and language-labelled fences indented within `Examples:`. Keep captions outside fences. No site JSX, Sphinx roles or HTML entities inside code for a Griffe-to-MDX pipeline.

Edit source, not generated pages. Let maintained extraction own signatures, fields and canonical references. Check the configured renderer before assuming cross-reference syntax or constructor merging. Preserve tested tool/schema descriptions that happen to feed documentation; a prose cleanup is not permission to restyle them.

Regenerate and inspect the affected reference. Verify signatures, links, literal code and representative example outcomes. A passing build proves neither correct behavior nor useful writing. Keep authoring instructions in skills, not published SDK reference pages.

Keep repository paths, site commands and deployment policy in project-local guidance. This skill supplies reusable writing rules. Human READMEs stay self-contained; agent instructions may link skills.

## Reference patterns

- [Anthropic reference index](https://github.com/anthropics/anthropic-sdk-python/blob/main/api.md) separates callable/type lookup from its [getting-started example](https://github.com/anthropics/anthropic-sdk-python/blob/main/README.md). Borrow the separation, not every generated paragraph.
- [Prime's Agent guide](https://github.com/PrimeIntellect-ai/verifiers/blob/main/docs/v1/agent.md) shows focused capability snippets; its [package root](https://github.com/PrimeIntellect-ai/verifiers/blob/main/verifiers/__init__.py) is only a short pointer. An empty or tiny upstream initializer is not a template for a generated landing page.
- [HTTPX API reference](https://www.python-httpx.org/api/) distinguishes client construction, methods and parameters. Examples are selective rather than mandatory on every symbol.
- [Griffe Google parsing](https://mkdocstrings.github.io/griffe/reference/docstrings/) and [griffe2md](https://mkdocstrings.github.io/griffe2md/) define parsing/rendering capabilities; verify the project's configuration instead of adding prose-repair heuristics.
