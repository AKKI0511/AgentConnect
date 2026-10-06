# Legacy CLI baseline (not a native MCP run)

This report preserves useful findings from the first ship-desk pass
before that experiment framework was removed. It is not a native
harness MCP judgment.

## Run metadata

- **Date:** 2026-10-02
- **Harness / model:** Cursor agent session driving a custom
  `release-review mcp` CLI (generic MCP Python client). Native Cursor
  MCP was not connected and was not used.
- **Caller role:** `release-lead@ship-desk` with a Bearer Session token,
  plus a short operator smoke. That membership is gone in the simplified
  workspace. The URL-only local flow now uses trusted-loopback
  **operator** (no mailbox, no Profile).
- **Team:** `ship-desk` at `http://127.0.0.1:63715/mcp` (memory store,
  hashed embeddings).
- **Scope of this artifact:** a custom client, control HTTP server,
  detached process manager, JSONL evidence files, and generated
  connection files. Those pieces are deleted. Do not treat this file as
  proof that native MCP rendering or token cost was measured.

## What this run actually was

The judge never called Team tools through the editor's native MCP
binding. Every call went through `uv run release-review mcp …`. That
wrapper:

- printed pretty JSON in `content[].text` and also kept
  `structured_content`
- added its own envelope fields, including `ok` vs MCP `is_error`
- wrote `runs/current/evidence/judge.jsonl` and related snapshots

Native token duplication was **not measured**. Byte counts below count
the custom client's recorded payload sizes, not harness token usage.
Do not cite them as native MCP cost.

The custom wrapper introduced the `ok` / `is_error` ambiguity. MCP
`is_error: true` could still appear as CLI `ok: true`. That disagreement
is not a Team Runtime contract.

## Assignment outcome

The canary reconstruction, SLO numbers, changelog, overlapping
discovery, pending forensic work, expired heap dump, declined payroll
ask, failed dump decode, empty SEV0 list, zero additional-canary
percent, idempotent retry, idempotency conflict, `tell` outside a
Thread, and a memory reset all completed through that CLI.

A rollback/hold recommendation was produced from specialist replies.
That is a task success for the old lab, not a native-tooling result.

## Fixture distortions that inflated findings

Recursive fixture replies echoed complete Thread history as
`prior_turns`. Nested copies made `get_history` with `limit=3` record
about 48850 output bytes. That size is a fixture problem, not evidence
that Team history is inherently that large.

`intake-clerk` with `max_in_flight=1` still accepted a second `ask` as
another open Ticket. Occupied handling capacity does not itself imply
admission rejection. MCP never returned `busy`. Two open Tickets is
what the tools showed.

`find` ranked overlapping specialists (for example incident-triage
ahead of metrics-analyst on a canary reconstruction query). Rankings
do not guarantee a suitable specialist exists. A payroll query still
returned ranked names; the correct action was to read Profiles and
decline out-of-scope work, not to treat rank one as qualified.

Padded `docs-librarian` Profile text was loaded so roster dumps looked
expensive. That padding is not kept.

## What still looks like Team-tool behavior

These observations came from live `Team.serve()` MCP and remain worth
retesting through native tools:

1. **Duplicate MCP text and structured content.** Successful tools
   returned pretty-printed JSON in `content[].text` plus the same object
   as `structured_content`. The custom CLI displayed both. Native
   rendering may show one, the other, or both; that was not measured
   here.

2. **Roster vs find.** `agentconnect://team/roster` embeds full
   Profiles. `find` summary cards omit `description` and scores, so
   choosing among overlapping specialists still wanted `get_profile` or
   `detail=full`.

3. **Error wrapping.** Runtime failures arrived as
   `Error executing tool ask: {"error":{...}}` with null
   `structured_content`. Missing `recipient` and a bad Bearer both
   raised JSON-RPC `-32602`. Declined Tickets are not that shape:
   `state=declined`, `status_message="The recipient declined."`, no
   reason field.

4. **`ttl_ms` after completion.** A completed Ticket whose original
   deadline had passed still returned `state=completed` with
   `ttl_ms: 0`. `ttl_ms` alone is a poor expired detector.

5. **`get_history` cursor.** The page is `{messages, has_more}`. The
   schema argument is `before`. The body does not echo `thread_id` or
   name a next cursor. `before=messages[0].id` walked older pages.

6. **`tell` and Thread participants.** `tell` onto another agent's
   request `thread_id` failed with `forbidden` / outside the
   participant set. `tell` without `thread_id` succeeded.

7. **Wait hold vs work deadline.** `collect=wait` returned `state=open`
   for forensic work that outlasted the lab's 2s wait hold, with
   `poll_interval_ms=1000`. `get_result` later collected the reply.
   Ending the wait did not cancel the Ticket.

8. **Operator vs member.** Loopback calls without Authorization ran as
   operator. Operator `find` worked; operator has no mailbox. Foreign
   Tickets returned `not_found` across members. Memory reset made old
   Ticket ids `not_found`. This simplified workspace no longer claims
   to test member Session recovery over a URL.

## Candidate improvements (untested natively)

Priority is user cost from the CLI pass, not wording taste. Retest
through native MCP before treating any item as confirmed.

1. Avoid duplicating Ticket/Find JSON as MCP text when structured
   content exists, or keep a short text summary. Retest with `find`
   `limit=2` and a small `get_history` page in the native renderer.
2. Return Runtime errors as structured MCP errors instead of a prefixed
   JSON string. Retest unknown recipient and foreign Ticket.
3. Distinguish auth failure from invalid params at the JSON-RPC layer.
   Member Bearer cases are outside the URL-only operator flow.
4. Put `thread_id` and the `before` cursor on the history page body.
5. Surface a decline reason on declined Tickets.
6. Stop using `ttl_ms: 0` as the only signal on a completed Ticket.

Do not claim token savings from (1) without a native measurement.

## What this file is not

It is not coverage of native Cursor MCP, member Session replacement,
process crashes, Redis durability, or production tool changes. The
simplified workspace expects a new report under `reports/` from a
native-tool run.
