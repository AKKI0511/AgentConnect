---
name: agent-tool-design
description: Design and review model-facing tool and MCP instructions, tool descriptions, parameter guidance and result guidance. Use for the interface an agent receives when calling tools, not Python SDK reference documentation.
---

# Agent tool and MCP design

Write for a model that sees only its tool catalog and server instructions, with no source, architecture guide, project vocabulary or development history. Cover tool selection, valid arguments, result interpretation and recovery.

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

Tool copy example, assuming these are the actual semantics:

**Avoid:** “Hydrates a WorkView through the coordinator's lease machinery.”

**Use:** “Read the saved result of a request. Pass `request_id` returned by `submit`. If `state` is `pending`, call `get_result` again with the same ID; do not submit the work again.”

Keep model-facing tool text and parameter descriptions readable as plain text. Avoid documentation roles, large schema dumps, repeated glossary text, and instructions that depend on a separate manual. Put shared guidance in one maintained source; keep each tool's essential calling rules locally understandable.

## Scope boundary

For package/module overviews, Python docstrings and their examples, use [python-api-reference](../python-api-reference/SKILL.md). Keep this skill focused on the interface text models receive as tools.

Keep repository paths, site commands and deployment policy in project-local guidance. This skill supplies reusable writing rules. Human READMEs stay self-contained; agent instructions may link skills.

## Verify the delivered tools

Read the advertised catalog, including schema descriptions, as a caller. After descriptor changes, refresh the native client and verify its loaded catalog before claiming the model sees the new guidance. Repeat a real tool-use experiment when changed behavior or evidence warrants it; distinguish wording checks from behavioral evidence. Report only checks actually run.
