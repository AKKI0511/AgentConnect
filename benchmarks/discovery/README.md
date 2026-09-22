# Discovery retrieval

Versioned specialist Profiles and separately authored needs. The runner
measures whether an acceptable recipient appears in the ranked list. It
does not call a chat model and does not decide who should be hired.

## Run

No API key and no Redis. The neural backend downloads
`BAAI/bge-small-en-v1.5` on first use through the embeddings extra.

```powershell
uv sync --locked --extra embeddings
uv run --no-sync python -m benchmarks.discovery.check
uv run --no-sync python -m benchmarks.discovery.score
```

`check` only validates corpus shape. `score` ranks with the production
Directory (hashed and FastEmbed) and a small BM25 baseline over the same
Profile text.

## Results

Artifacts land in `artifacts/discovery-v1/`:

| File | Contents |
| --- | --- |
| `RESULTS.md` | Held-out shuffled coverage@1/5/10, MRR, denominators, and slices |
| `results.json` | The same figures, plus every coverage@10 miss |

Corpus revision is `discovery-v1`. The shuffle seed, preprocessing
revision, BM25 settings, and neural model id are in both files. Do not
edit `criteria.py` after a run to make a backend pass. A failed neural
load or a Directory fallback is written under `failed/` and is not
labeled as neural ranks. A later successful run leaves that file in
place. `score` exits non-zero when a required backend or a ranking gate
fails.

## How to read a failure

Coverage@k is the fraction of needs with a non-empty acceptable set whose
best acceptable address is at rank k or better. MRR uses that same best
rank. The denominator is the count of those needs, not the roster size.

The held-out shuffled gates are coverage@10 ≥ 0.90 and MRR ≥ 0.50.
Coverage@1 and coverage@5 are reported beside them and are not gates.
When a roster has no more members than k, coverage@k cannot miss a member
who is on that roster; use a larger roster before treating that figure as
evidence. Slices show the same rates for one label at a time. A miss lists
the need id, backend, best rank, acceptable addresses, and the top 10.

Ranked output is a candidate list. It is not proof that a member can do
the work, and needs with an empty acceptable set are not an abstention
score. The field table compares full Profile text with summary plus skill
names. It is not a change to Profile fields.

Runtime latency, Redis, and FastEmbed throughput belong to
[the Runtime benchmarks](../runtime/README.md), not this run.
