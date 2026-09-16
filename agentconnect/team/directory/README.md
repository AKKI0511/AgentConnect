# Team Directory

Local discovery for one Team. ``find`` ranks every member except the caller
from a natural-language query. Vectors are stored next to Memberships. A
vector database is not used.

Search works on a fresh Team. No configuration, no extra package, and no API
key are required. Hosted embeddings are used only when the Team selects them
explicitly.

## What a caller writes

```python
from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Reviewer(BaseAgent):
    profile = {
        "summary": "Reviews contracts for risk and missing terms.",
        "description": "Use for MSAs and similar commercial contracts.",
        "skills": [
            {
                "name": "contract_review",
                "description": "Read a contract and list risks and missing clauses.",
                "examples": ["Check this MSA for indemnity gaps."],
                "tags": ["msa"],
            }
        ],
        "tags": ["legal", "contracts"],
    }

    async def handle(self, msg, ctx):
        return "reviewed"


team = await Team("content-squad").start()
await Reviewer(name="reviewer").join(team)
await Researcher(name="researcher").join(team)

found = await researcher.find("someone who can verify a contract")
found.matches[0].address  # reviewer@content-squad
found.matches[0].summary
found.matches[0].tags  # Profile tags ["legal", "contracts"]

entry = await researcher.get_entry("reviewer")
entry.profile.description
entry.profile.skills[0].tags  # Skill tags ["msa"], not on the light card
```

Omit ``limit`` to receive every other member, ordered, up to 100. Pass
``limit=3`` when you want a shortlist. ``detail="full"`` adds ``agent_did``
and the complete Profile to each match.

The Runtime never injects a Profile into handler input. Call ``find`` or
``get_entry`` when the Agent should read one. Ranking does not choose who
``ask`` or ``tell`` send to.

## Embedding backends

Set on the Team, not on each Agent.

| ``embeddings=`` | When to use it |
|---|---|
| ``"auto"`` (default) | Local ONNX if ``agentconnect[embeddings]`` is installed, else hashed n-grams. Ambient API keys are ignored |
| ``"none"`` | Hashed n-grams only. No network, no extra package |
| ``"fastembed"`` | Local ONNX model (``pip install agentconnect[embeddings]``). May download model files to this host; that is not Profile or query egress |
| ``"openai"`` | Explicit hosted OpenAI ``text-embedding-3-small`` at 384 dimensions. Requires ``pip install agentconnect[openai]`` (tiktoken). Missing tiktoken is a setup error, not hashed fallback |
| ``"litellm"`` or ``"litellm:<model>"`` | Explicit hosted LiteLLM embeddings for OpenAI and Azure models only. Requires ``pip install agentconnect[aiagent,openai]``. Other providers are refused because LiteLLM's tokenizer is a generic tiktoken fallback, not the hosted model's tokenizer |
| a callable | ``(list[str]) -> list[list[float]]``: sync, async, or a sync function that returns an awaitable |

```python
async def embed(texts: list[str]) -> list[list[float]]:
    return await my_model.encode(texts)


team = await Team("content-squad", embeddings=embed).start()
```

Profiles are embedded when an Agent joins and again when the Profile changes.
``find`` embeds the query and ranks with a dot product in one embedding space.
A backend change or an embedding failure rebuilds that index. Store errors
do not change the configured space. Hashed n-grams keep search available;
backend failures are logged for the operator and are not added to caller
results.

``pip install agentconnect`` does not pull torch. The ``[embeddings]`` extra
installs [fastembed](https://qdrant.github.io/fastembed/), which uses ONNX.
A local model download stays on this machine. ``openai`` and ``litellm``
are the selections that transmit Profile and query text. Hosted OpenAI
needs the ``openai`` extra so tiktoken can split to the model's limit.
LiteLLM hosted embeddings also need the ``aiagent`` extra and only
support OpenAI and Azure embedding models.

## Index vs Directory

This package answers "who is on my Team". The optional Index service under
``agentconnect.index`` answers "who is out there" across published Teams.
