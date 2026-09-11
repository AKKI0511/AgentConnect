# Quickstart

An editor sends a writing job to `writer` by Address. The writer asks
the researcher for notes, then returns a draft. AgentConnect delivers
the messages and records the Ticket. Ranking teammates with `find` is
covered in [`../recipes/discover.py`](../recipes/discover.py).

Each specialist runs a harness inside `handle`.

## Modes

**Deterministic** (default) uses `StubHarness` and hashed Directory
embeddings. It never calls a provider.

**Live** (`--live`) calls OpenAI Chat Completions from that same
`handle`. A missing key prints setup steps and exits. It does not
switch back to the stub.

## Setup

Python 3.11 or 3.12. [Install uv](https://docs.astral.sh/uv/getting-started/installation/).

From a clone of this repository:

```bash
cd examples/quickstart
uv sync
```

That installs this checkout of AgentConnect (editable) plus the
OpenAI client used only by `--live`.

## Run

Deterministic:

```bash
uv run python -m team_demo
```

Live. The environment file belongs in this folder:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

Set `OPENAI_API_KEY`, then:

```bash
uv run python -m team_demo --live
```

`OPENAI_MODEL` defaults to `gpt-4o-mini`. `OPENAI_BASE_URL` is optional
for a compatible endpoint.

## What happens

`collect="wait"` may return while accepted work is still `open`. That
hold is not the Ticket deadline. The demo keeps reading `get_result`
until a terminal state or that deadline, then prints the Ticket. Stopping
this embedded Team tears down the in-memory Runtime. An `open` Ticket
from this process does not resume after `team.stop()`.

If the researcher does not complete, the parent Ticket follows that
outcome:

- declined, the parent is declined
- failed, the parent fails with the child error
- expired, the parent fails because the researcher expired

## Sample output (deterministic)

```text
team: content-squad
joined: editor@content-squad writer@content-squad researcher@content-squad
ask writer@content-squad
writer asked researcher for notes
ticket state: completed
ticket response: Launch note: AgentConnect is a messaging runtime for independent agents.
Each specialist keeps its own models and tools.
Outstanding work is a Ticket the Team holds.
```

Open, failed, declined, or expired work is printed as that state, not as
success.

## What to change

| Piece | Where |
| --- | --- |
| Discovery card | `profile` on each class in `team_demo/agents.py` |
| Harness | `StubHarness` / `OpenAIHarness` in `team_demo/harness.py` |
| Instructions | `self.instructions` in `Writer` and `Researcher` |
| Incoming mail | `handle` on each class |
