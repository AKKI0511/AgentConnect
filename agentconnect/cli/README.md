# AgentConnect CLI

The ``agentconnect`` program is a person talking to a Team. Every verb an
Agent has, a person has. ``up`` starts the Runtime from
``agentconnect.yaml``. The other commands call that Runtime over loopback
HTTP as the reserved ``operator`` Membership.

```bash
agentconnect init
agentconnect up
```

In another terminal:

```bash
agentconnect status
agentconnect find "someone who can draft a summary"
agentconnect ask assistant "What can you do?"
agentconnect trace <trace-id>
```

## Commands

- ``init`` — write ``agentconnect.yaml`` and ``agents/assistant.py``
- ``up`` / ``down`` — start or stop the Team and hosted Agents
- ``status`` — members, kind, online state, Agent mailbox depths, open tickets
- ``token issue`` / ``token revoke`` — join credentials
- ``find`` — Directory search
- ``ask`` — send reply-expected work and wait
- ``trace`` — print the timeline for one causal operation
- ``watch`` — print new Trace events
- ``doctor`` — Team file, keys, and whether the Runtime is reachable
- ``version`` — package version

``up --detach`` starts in the background. ``down`` stops that process.
State lives in ``.agentconnect/state.json``.

``--url`` points any command at a Runtime that is already serving.
Without it, the CLI uses the saved origin, then host and port from the
Team file, then ``http://127.0.0.1:9000``.

``--json`` prints machine-readable output on ``status``, ``find``,
``ask``, ``trace``, and ``token issue``.
