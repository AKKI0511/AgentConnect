---
name: agent-tool-design
description: Design and review model-facing tool and MCP instructions, tool descriptions, parameter guidance and result guidance. Use for the interface an agent receives when calling tools, not Python SDK reference documentation.
---

# Agent tool and MCP design

Assume the model sees only its tool catalog and server instructions. Cover selection, valid arguments, result interpretation and recovery without relying on source code or project vocabulary.

## Preserve the interface

- Treat descriptions and parameter guidance as interface behavior. Change them for changed behavior, factual errors or demonstrated confusion, not nearby restyling.
- Read implementation, signatures, schemas and usage evidence. Preserve accurate defaults, boundaries, recovery instructions and tested distinctions; never invent guarantees to simplify copy.
- Edit the authoritative source and trace generated schemas/documentation for stale guidance.
- Keep scope: a feature edit does not authorize rewriting every prompt or auditing the SDK.

## Write for the caller

- Lead with the action and outcome; explain selection and next steps when non-obvious.
- Use ordinary language with exact callable names, argument keys, enum values and identifiers. Explain unfamiliar public concepts, not internal subsystem names.
- For parameters, explain purpose, meaningful defaults, units, bounds, omission versus null, and where required IDs come from. Include only distinctions that affect a valid call.
- Explain results, side effects, ownership/cleanup and recoverable errors. Preserve acceptance/completion and waiting/cancellation distinctions.
- Retain limitations affecting use. Keep implementation history, bug/issue narratives, abandoned alternatives, roadmap notes and maintenance rationale in development records.

Tool copy example, assuming these are the actual semantics:

**Avoid:** “Hydrates a WorkView through the coordinator's lease machinery.”

**Use:** “Read the saved result of a request. Pass `request_id` returned by `submit`. If `state` is `pending`, call `get_result` again with the same ID; do not submit the work again.”

Use plain text, without documentation roles, large schema dumps or repeated glossaries. Maintain shared guidance once while keeping each tool's essential calling rules understandable without a separate manual.

## Scope boundary

For package/module overviews, Python docstrings and their examples, use [python-api-reference](../python-api-reference/SKILL.md). Keep this skill focused on the interface text models receive as tools.

Keep site commands and deployment policy in project-local guidance. Human READMEs stay self-contained; agent instructions may link skills.

## Verify the delivered tools

Inspect the advertised catalog, including schema descriptions. After descriptor changes, refresh the native client and verify its loaded catalog before claiming the model sees the new text. Repeat real tool use when behavior or evidence warrants it; distinguish wording inspection from behavioral verification and report only checks run.
