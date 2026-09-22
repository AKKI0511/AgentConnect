# Discovery retrieval

- Corpus revision: `discovery-v1`
- Preprocessing revision: `profile-units-v1`
- BM25 revision: `okapi-k1-1.5-b-0.75-alnum`
- Shuffle seed: `20260922`
- Neural model: `BAAI/bge-small-en-v1.5`

Gates apply to held-out shuffled needs whose acceptable set is non-empty: coverage@10 ≥ 0.9 and MRR ≥ 0.5. Coverage@1 and coverage@5 are reported, not gated. A roster no larger than k cannot show a coverage@k miss.

## hashed — held-out shuffled

Directory backend: `hashed`. Fallback: False.

Denominator: 47 needs with an acceptable recipient.

| Metric | Value | Gate |
| --- | --- | --- |
| coverage@1 | 0.8723 |  |
| coverage@5 | 1.0000 |  |
| coverage@10 | 1.0000 | 0.9 (pass) |
| MRR | 0.9238 | 0.5 (pass) |

| Slice | Denominator | coverage@10 | MRR |
| --- | --- | --- | --- |
| broad_or_misleading | 1 | 1.0000 | 1.0000 |
| contract_substance_vs_formatting | 5 | 1.0000 | 1.0000 |
| generalist_vs_specialist | 11 | 1.0000 | 1.0000 |
| jurisdiction_or_dataset | 11 | 1.0000 | 0.8939 |
| late_capability | 2 | 1.0000 | 1.0000 |
| multilingual | 2 | 1.0000 | 0.6250 |
| multiple_acceptable | 3 | 1.0000 | 0.7778 |
| negated_capability | 1 | 1.0000 | 1.0000 |
| paraphrase | 6 | 1.0000 | 1.0000 |
| refunds_vs_chargeback | 4 | 1.0000 | 1.0000 |
| repeated_boilerplate | 3 | 1.0000 | 1.0000 |
| staging_vs_production | 9 | 1.0000 | 0.9444 |
| translation_direction | 5 | 1.0000 | 0.6167 |

Roster sizes: roster_commerce=10, roster_legal=8, roster_platform=24, roster_research=26

## bm25 — held-out shuffled

Denominator: 47 needs with an acceptable recipient.

| Metric | Value | Gate |
| --- | --- | --- |
| coverage@1 | 0.9362 |  |
| coverage@5 | 1.0000 |  |
| coverage@10 | 1.0000 | 0.9 (pass) |
| MRR | 0.9610 | 0.5 (pass) |

| Slice | Denominator | coverage@10 | MRR |
| --- | --- | --- | --- |
| broad_or_misleading | 1 | 1.0000 | 1.0000 |
| contract_substance_vs_formatting | 5 | 1.0000 | 1.0000 |
| generalist_vs_specialist | 11 | 1.0000 | 1.0000 |
| jurisdiction_or_dataset | 11 | 1.0000 | 1.0000 |
| late_capability | 2 | 1.0000 | 1.0000 |
| multilingual | 2 | 1.0000 | 0.6667 |
| multiple_acceptable | 3 | 1.0000 | 0.8333 |
| negated_capability | 1 | 1.0000 | 1.0000 |
| paraphrase | 6 | 1.0000 | 1.0000 |
| refunds_vs_chargeback | 4 | 1.0000 | 1.0000 |
| repeated_boilerplate | 3 | 1.0000 | 1.0000 |
| staging_vs_production | 9 | 1.0000 | 1.0000 |
| translation_direction | 5 | 1.0000 | 0.6333 |

Roster sizes: roster_commerce=10, roster_legal=8, roster_platform=24, roster_research=26

## neural — held-out shuffled

Directory backend: `fastembed:BAAI/bge-small-en-v1.5`. Fallback: False.

Denominator: 47 needs with an acceptable recipient.

| Metric | Value | Gate |
| --- | --- | --- |
| coverage@1 | 0.9574 |  |
| coverage@5 | 1.0000 |  |
| coverage@10 | 1.0000 | 0.9 (pass) |
| MRR | 0.9787 | 0.5 (pass) |

| Slice | Denominator | coverage@10 | MRR |
| --- | --- | --- | --- |
| broad_or_misleading | 1 | 1.0000 | 1.0000 |
| contract_substance_vs_formatting | 5 | 1.0000 | 1.0000 |
| generalist_vs_specialist | 11 | 1.0000 | 1.0000 |
| jurisdiction_or_dataset | 11 | 1.0000 | 1.0000 |
| late_capability | 2 | 1.0000 | 1.0000 |
| multilingual | 2 | 1.0000 | 1.0000 |
| multiple_acceptable | 3 | 1.0000 | 0.8333 |
| negated_capability | 1 | 1.0000 | 1.0000 |
| paraphrase | 6 | 1.0000 | 1.0000 |
| refunds_vs_chargeback | 4 | 1.0000 | 1.0000 |
| repeated_boilerplate | 3 | 1.0000 | 1.0000 |
| staging_vs_production | 9 | 1.0000 | 0.9444 |
| translation_direction | 5 | 1.0000 | 0.9000 |

Roster sizes: roster_commerce=10, roster_legal=8, roster_platform=24, roster_research=26

Coverage@10 misses: 0. Coverage@1 misses: 11. Both are listed in `results.json`. Only coverage@10 misses fail the gate.

## Field diagnostic

Held-out shuffled coverage@10 and MRR for the full Profile text versus summary plus skill names. Not a gate and not a field change.

| Backend | Representation | Denominator | coverage@10 | MRR |
| --- | --- | --- | --- | --- |
| hashed | full_profile_text | 47 | 1.0000 | 0.9238 |
| hashed | summary_and_skill_names | 47 | 0.9787 | 0.7739 |
| neural | full_profile_text | 47 | 1.0000 | 0.9787 |
| neural | summary_and_skill_names | 47 | 1.0000 | 0.8865 |

