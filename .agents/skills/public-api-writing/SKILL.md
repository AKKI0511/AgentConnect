---
name: public-api-writing
description: Write and review model-facing tool descriptions, parameter guidance, prompts, and public Python SDK docstrings. Use when changing these surfaces or behavior they describe; preserve tested wording and render Google-style API documentation correctly.
---

# Public API writing

Write for a person or model that sees only the public interface, with no source, architecture guide, project vocabulary, or development history.

## Preserve the interface

- Treat tool descriptions and parameter guidance as behavior-bearing interface text. Change them for changed behavior, a factual error, or demonstrated confusion—not to restyle nearby code.
- Read the current implementation, signatures, schemas, and relevant usage evidence first. Preserve accurate defaults, boundaries, recovery instructions, and tested distinctions. Never invent guarantees to make the copy simpler.
- Edit the authoritative source. Trace where docstrings and field descriptions become tool schemas or generated documentation; changing a short tool summary may leave old guidance elsewhere.
- Keep changes scoped. A feature edit is not permission to rewrite every prompt or audit the whole SDK.

## Write for the caller

- Lead with the action and useful outcome. Explain when to use the interface and what the caller must do next when that is not obvious.
- Use ordinary language. Keep exact callable names, argument keys, enum values, and identifiers the caller must use. Explain unfamiliar public concepts at first use; do not require readers to learn internal type or subsystem names.
- For parameters, explain purpose, meaningful defaults, units, bounds, omission versus null, and where required IDs come from. Include only distinctions that affect a valid call.
- Explain results, side effects, ownership/cleanup, and recoverable errors where relevant. Distinguish acceptance from completion and waiting from cancellation when the API does.
- Keep current limitations that affect correct use. Remove implementation history, bug narratives, issue IDs, abandoned alternatives, roadmap notes, and defensive commentary. Put maintenance rationale in internal comments or development records.
- Module docstrings explain the public purpose and entry points. Class docstrings explain what an instance represents, how to construct/use it, and relevant lifetime rules. Method/function docstrings explain the call itself. Do not repeat an architecture overview everywhere.

Tool copy example, assuming these are the actual semantics:

**Avoid:** “Hydrates a WorkView through the coordinator's lease machinery.”

**Use:** “Read the saved result of a request. Pass `request_id` returned by `submit`. If `state` is `pending`, call `get_result` again with the same ID; do not submit the work again.”

Keep model-facing tool text and parameter descriptions readable as plain text. Avoid documentation roles, large schema dumps, repeated glossary text, and instructions that depend on a separate manual. Put shared guidance in one maintained source; keep each tool's essential calling rules locally understandable.

## Render Python docstrings

Use Google-style sections with consistent indentation and blank lines: `Args:`, `Returns:` or `Yields:`, `Raises:`, `Attributes:`, and `Examples:` only where useful. Match actual parameter names. Let annotations supply types when the documentation configuration supports that; explain semantics rather than repeating type names.

Inspect the target site's parser and generator before choosing markup. For Mintlify with mdxify/Griffe, use Google sections, Markdown inline backticks, and fenced examples indented inside `Examples:`. Label fences `python` or `bash`; do not mix commands and Python. Do not introduce Sphinx roles or reStructuredText directives into this pipeline just because an older site used them.

````python
from pathlib import Path


def read_text(path: str, encoding: str = "utf-8") -> str:
    """Read a local text file and close it before returning.

    Args:
        path: File to read, relative to the current directory or absolute.
        encoding: Text encoding. Defaults to UTF-8.

    Returns:
        The complete file contents, including line endings as read.

    Raises:
        OSError: The file cannot be opened or read.
        UnicodeError: The contents cannot be decoded with the encoding.

    Examples:
        Read an existing UTF-8 file from the current directory:

        ```python
        text = read_text("notes.txt")
        print(text)
        ```
    """
    return Path(path).read_text(encoding=encoding)
````

Keep Python docstrings portable: let the generator create Mintlify `ParamField` and `ResponseField` components from parsed sections. Do not put site-specific JSX in SDK docstrings. Protect literal braces and angle brackets with inline code or fenced blocks so MDX does not interpret them as expressions or tags. Treat legacy-markup conversion as compatibility support, not the preferred authoring style.

Examples must state prerequisites and show real public calls. Include imports, setup, and cleanup when needed; use async syntax correctly. Keep commands in shell blocks and executable Python in Python blocks. Never present placeholders or expected output as runnable commands.

## Verify the delivered surface

- Read the final advertised tool catalog, including schema descriptions, as a caller. After server changes, refresh the native client and verify its loaded catalog before claiming model-visible behavior improved.
- Build documentation through the target site's generator. For Mintlify, inspect generated MDX, run the project's freshness/determinism checks and `mint validate` / `mint broken-links`, then inspect affected arguments, links, and code blocks in preview. A passing legacy-site build does not validate its replacement. Do not hand-edit generated pages or change the generator to compensate for malformed docstrings.
- Run relevant examples/checks when semantics or examples changed. Avoid brittle tests asserting entire prose strings. Repeat a native tool-use experiment only when the change warrants it; distinguish wording checks from behavioral evidence.
- Report what changed and what was actually checked. Do not claim rendering or native-client verification when unavailable.

References: [Griffe docstring parsing](https://mkdocstrings.github.io/griffe/guide/users/), [mdxify](https://github.com/zzstoatzz/mdxify), [Mintlify pages](https://www.mintlify.com/docs/pages).
