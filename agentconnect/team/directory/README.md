# Team Directory

Local discovery for one Team. ``find`` ranks every member except the caller
from a natural-language query. Vectors are stored next to Memberships. A
vector database is not used.

Search works on a fresh Team. No configuration, no extra package, and no API
key are required. Hosted or local neural embeddings are used when they are
already available.

## What a caller writes

```python
from agentconnect.agent import BaseAgent
from agentconnect.team import Team

class Reviewer(BaseAgent):
    profile = {
        "summary": "Reviews contracts for risk and missing terms.",
        "skills": [
            {
                "name": "contract_review",
                "description": "Read a contract and list risks and missing clauses.",
                "examples": ["Check this MSA for indemnity gaps."],
            }
        ],
        "tags": ["legal", "contracts"],
    }

    async def process_message(self, msg, ctx):
        return "reviewed"

team = await Team("content-squad").start()
await Reviewer(name="reviewer").join(team)
await Researcher(name="researcher").join(team)

found = await researcher.find("someone who can verify a contract")
found["matches"][0]["address"]  # reviewer@content-squad

entry = await researcher.get_profile("reviewer")
entry["profile"]["summary"]
```

Omit ``limit`` to receive every other member, ordered, up to 100. Pass
``limit=3`` when you want a shortlist. ``detail="full"`` adds ``agent_did``
and the complete Profile to each match.

The Runtime never injects a Profile into handler input. Call ``find`` or
``get_profile`` when the Agent should read one.

## Embedding backends

Set on the Team, not on each Agent.

| ``embeddings=`` | When to use it |
|---|---|
| ``"auto"`` (default) | Hosted API if ``OPENAI_API_KEY`` or ``AZURE_OPENAI_API_KEY`` is set, else ``fastembed`` if installed, else hashed n-grams |
| ``"none"`` | Hashed n-grams only. No network, no extra package |
| ``"fastembed"`` | Local ONNX model (``pip install agentconnect[embeddings]``) |
| ``"openai"`` | OpenAI ``text-embedding-3-small`` at 384 dimensions |
| ``"litellm"`` or ``"litellm:<model>"`` | LiteLLM, when that package is installed |
| a callable | ``(list[str]) -> list[list[float]]``, sync or async |

```python
async def embed(texts: list[str]) -> list[list[float]]:
    return await my_model.encode(texts)

team = await Team("content-squad", embeddings=embed).start()
```

Profiles are embedded when an Agent joins and again when the Profile changes.
``find`` embeds the query and ranks with a dot product.

``pip install agentconnect`` does not pull torch. The ``[embeddings]`` extra
installs [fastembed](https://qdrant.github.io/fastembed/), which uses ONNX.

## Index vs Directory

This package answers "who is on my Team". The optional Index service under
``agentconnect.index`` answers "who is out there" across published Teams.
