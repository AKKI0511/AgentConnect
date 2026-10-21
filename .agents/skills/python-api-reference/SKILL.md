---
name: python-api-reference
description: Write and review public Python SDK references, docstrings and examples. Use for clear package overviews, API contracts and generated reference pages for developers and coding agents, not tool catalogs or runtime prompts.
---

# Python API reference writing

Help callers choose an API, use it and understand the result. Assume Python and relevant domain knowledge, but no product vocabulary. Read [writing examples](references/writing-examples.md) when editing overviews or examples; read the relevant [source comparison](references/sdk-reference-research.md) when choosing a structure.

## Keep what changes a caller's decision

For each sentence, name the action or expectation it changes. Retain inputs, results, prerequisites, errors and relevant ownership, timeout, persistence or subclass contracts. Describe observable outcomes: “Closing the client leaves accepted jobs running,” rather than its internal shutdown sequence. State guarantees at the documented boundary: an internal store's rollback is not an HTTP client's rollback.

Remove internal call chains, import tricks, storage algorithms, development history and maintainer instructions. Do not replace them with lists of what the API does not do. Report weak APIs as design findings; a reference edit does not authorize redesign. Distinguish everyday APIs, extension contracts and internal plumbing, and trace callers before proposing removal.

Every public symbol must work for a direct-arrival reader. Usually a purpose sentence plus essential prerequisites and consequences is enough; self-contained does not mean a tutorial or glossary. Review overview, module, class and methods together. Give each fact one primary owner, repeating only what prevents misuse when a method is read alone. Preserve meaningful history isolation, data loss, authority limits and failure behavior.

Use the site's explicit symbol syntax, such as ``[`Record`][package.models.Record]``, and verify rendered targets. Plain backticks are literal code. Use verified absolute Markdown URLs for portable links. Prefer the relevant public class/method over an internal module or “example on page X.” Links supplement local prerequisites; they do not replace them. Website links do not prove IDE hover support.

## Give each level a job

| Level | Reader's question |
| --- | --- |
| Root / landing page | What is this SDK for, and which local concepts do I need? |
| Subpackage initializer | What is this area for, what does it need, and how do I use it? |
| Leaf module | What does this file provide? |
| Class / constructor | What does this object represent, and how do I obtain or subclass it? |
| Method / function | What is the call's contract? |
| Field / property | What does this value mean? |

Check which source owns each rendered page: some initializers only export names. Start the root with a plain purpose sentence and essential local nouns; an integration fragment is optional. Avoid feature catalogs and generated symbol inventories. Subpackage introductions explain purpose, prerequisites and entry points without enumerating methods. Leaf modules can be one specific sentence. Classes explain acquisition and relevant lifecycle/subclass obligations; factory- or handler-supplied objects rarely need constructor internals.

## Write for lookup

- Lead with the useful action or result, using everyday words and exact API names. Keep one idea per paragraph.
- Treat the signature as read. Omit Args/Returns entries that repeat types, defaults, obvious names or the return annotation. Explain domain meaning, constraints, authority, ownership, side effects and special values; retain units/bounds when names and types are insufficient.
- Explain non-obvious omission consequences, such as an inherited deadline, without repeating the default value.
- Keep scope exact: another process is not necessarily another host; stopping a listener is not restarting clients. Preserve reachability and resource-ownership conditions when shortening.
- Use lists for alternatives/steps and tables for useful comparisons. CLI tables show copyable commands and outcomes; put shared selection rules/flags once and link `--help` for complete options.
- Keep extended workflows in guides, retaining advanced facts beside calls when they change choices or results. Remove marketing, meta prose, contrived contrasts and Python tutorials.

Do not repeat async/property/classmethod/staticmethod labels in prose or headings when the renderer supplies metadata. Keep authoring policy and research out of public pages; repository commands and publishing policy belong in project-local guidance.

## Choose examples by need

Use examples for a practical choice, difficult input or meaningful result. Simple accessors and obvious calls often need none.

| Form | Required context |
| --- | --- |
| Complete program | Imports, setup, real calls, useful result and cleanup. |
| Focused fragment | Caption naming the existing client/resource and async context. |
| Input/output shape | Relevant value, labelled as input or output. |

Prefer focused fragments. Provider authentication, startup, polling and scheduling usually belong in guides, unless they teach the API itself; async code and loops are not inherently excessive.

- Import newly introduced types and use real public calls. Prefer canonical caller-owned models/snapshots over reconstructing identity or registration shapes.
- For adapters, assume a configured harness when useful. Verify its real API and result access; a connection does not necessarily install tools into a model.
- Do not invent response schemas, helpers or toy harnesses to make examples executable. Keep test doubles/setup in tests and disclose verification limits.
- Check result states before reading optional fields; distinguish returned failures from exceptions. Label variable/model output as illustrative and show it only when informative.
- Illustrative configuration must parse: do not extend a TOML inline table with a later header or invent unsupported aliases.

## Verify the delivered reference

1. Read signatures, behavior, inherited docs and overloads. Preserve runtime behavior, exports and tested tool/schema text. Compare annotations with implementations: prose naming a model does not repair an `Any`/`dict` contract. Report mismatches separately. Inspect schema descriptions when model docstrings feed tools.
2. Edit authoritative sources using the configured docstring/link format. Avoid duplicating constructor parameters when the renderer merges them into the class.
3. Preview and release workflows generate pages before checking. Locally run `npm run api` in `docs-v2` after docstring edits, then inspect whole pages, including unchanged members. Check signatures, links, code blocks, results, empty attribute sections and accidental internal helpers. Keep site markup out of Python snippets; distinguish existing surface problems from new defects. Do not edit generated MDX.
4. Follow the user's verification scope. For prose-only edits, inspect source and output; do not add or run tests by habit. Exercise representative executable behavior when testing is authorized; compilation alone does not verify a fragment. Distinguish observed results from reported checks.
5. Read the main journey and one method alone. Review all public symbols in scope, retaining good text and supported extension contracts. Preserve tool catalogs/prompts during reference-only work.

To refresh the source comparison, pin official revisions, compare source levels with published pages, record example setup and verification gaps, and separate observed practice from recommendations.
