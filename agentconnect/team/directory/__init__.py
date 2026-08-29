"""This Team's member Directory.

Semantic ``find`` ranks every Membership except the caller. Vectors live in
the Team Store. There is no vector database and no setting to turn search on.

    team = await Team("content-squad").start()
    found = await agent.find("someone who can review a contract")
    found["matches"][0]["address"]
    entry = await agent.get_profile("reviewer")

Pass ``embeddings=`` to :class:`~agentconnect.team.runtime.Team` only when you
want a specific backend. ``"auto"`` is the default.
"""

from agentconnect.team.directory.directory import (
    Directory,
    MAX_FIND_LIMIT,
    profile_text,
)
from agentconnect.team.directory.embedder import (
    Embedder,
    EmbeddingsArg,
    HashedEmbedder,
    resolve_embedder,
)

__all__ = [
    "Directory",
    "Embedder",
    "EmbeddingsArg",
    "HashedEmbedder",
    "MAX_FIND_LIMIT",
    "profile_text",
    "resolve_embedder",
]
