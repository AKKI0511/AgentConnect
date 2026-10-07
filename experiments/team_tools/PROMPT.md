# Ship-desk experiment prompt

You are judging AgentConnect Team MCP tools. Use only this harness's
native Team MCP connection.

If those tools are not connected, stop. Tell the user to start
`uv run python team.py` from `experiments/team_tools/` and add the
printed MCP URL with native MCP support. Do not build a fallback client,
call `curl`, run SDK scripts, or claim a native run occurred.

Shell and file tools may save the final report. Do not read
`teammates.py`, `team.py`, earlier reports, or other fixture source to
answer the assignment.

## Caller

Loopback MCP calls act as the Team operator. Operator has no mailbox
and no Profile. This is not an authenticated member Session.

## Assignment

The payments-api 2.4.1 canary is at 10% in us-east-1. Checkout looks
bad. Produce a hold-or-ship recommendation by discovering teammates,
choosing who to involve, and coordinating their work through Team tools.

Specialists may overlap. Decide from the connected tools, their
descriptions, and the results they return.

## Report

Write exactly one self-contained Markdown file:

`experiments/team_tools/reports/<YYYY-MM-DD>-<harness>.md`

If that path already exists, choose a new unique suffix instead of
overwriting.

Include:

- Commit SHA and whether the checkout is dirty.
- Harness and model when known, date, and caller role (operator).
- Evidence of the loaded catalog: tool names and a short excerpt of the
  advertised descriptions you were given.
- What you attempted and whether it succeeded.
- Concrete examples of confusing arguments, defaults, results, or errors.
- Selected actual tool arguments and results for each important finding.
- Unnecessary calls, or information you struggled to recover.
- Fixture limitations versus Team-tool limitations.
- Untested cases and connection or rendering limitations.
- Response or context size where you can measure it; otherwise say
  unknown. Include find cards, bulk `get_profiles` versus one-at-a-time
  Profile reads, tell, saved request results, history with `parent_id`,
  call counts, and token counts if shown.

Do not write a transcript dump, metrics file, or report index. Do not
claim token savings without measurement.
