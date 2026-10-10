# RAG retrieval quality and scale

Reproduce: `pytest apps/api/tests/test_rag_retrieval_metrics.py -s` (quality) and
`python apps/api/scripts/rag_scale_benchmark.py --sizes 1000 10000 50000` (scale).
Both use the deterministic local hashing embedder and SQLite; nothing calls a provider.

## Quality baseline (31 documents, 56 queries: 46 positive, 10 negative)

| mode | R@1 | R@3 | R@5 | P@3* | MRR | nDCG@5 | negative FP | p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|
| hybrid (0.7 vector) | 0.79 | 0.83 | 0.85 | 0.29 | 0.84 | 0.83 | 0.20 | 3 / 6 |
| vector only | 0.74 | 0.82 | 0.86 | 0.28 | 0.81 | 0.81 | 0.10 | 3 / 5 |
| keyword only | 0.76-0.78 | 0.85 | 0.85-0.86 | 0.30 | 0.82-0.83 | 0.82-0.83 | 0.20 | 3 / 5 |

\*P@3 has a ceiling of about 0.33 because most queries have one relevant document. Ties break on random
public ids, so values move by about 0.02 between runs.

By bucket, hybrid Recall@3: **lexical 1.00**, **semantic (paraphrase) 0.33**.

Findings:
- The first baseline showed 50% of off-topic queries returning results. Cause: two-letter function words
  (`to`, `in`, `of`) were not stopwords. Fixed in `retrieval.py`; false positives fell to 20%.
  Remaining ones are real lexical overlap (e.g. "treatment").
- Hybrid is not better than keyword-only here, because the local embedder is itself lexical. Paraphrase
  recall (0.33) measures that embedder, not the retriever. Re-run with a real embedding model before
  drawing conclusions about hybrid weighting. Not run: the configured OpenAI key was rejected (401).
- Regression floors (set below observed values with margin): R@3 >= 0.75, R@5 >= 0.78, MRR >= 0.75,
  lexical R@3 >= 0.95, negative FP <= 0.30, p95 < 250 ms. Semantic recall is intentionally not gated.

Filters, tenant isolation, visibility, versions and deletion are covered by `test_knowledge_rag.py`
and re-checked on the golden corpus in `test_rag_retrieval_metrics.py`.

## Scale (SQLite stand-in for MariaDB; timings indicative)

Targets are scattered across insertion order and queried by unique markers, so this is a worst case for
the cap, not an average case.

| chunks | candidate cap | recall@5 | SQL p50 | scoring p50 | total p50 / p95 |
|---|---|---|---|---|---|
| 1k | 400 (default) | 0.20 | 17 ms | 13 ms | 30 / 43 ms |
| 1k | all | 1.00 | 48 ms | 39 ms | 86 / 109 ms |
| 10k | 400 (default) | 0.00 | 18 ms | 15 ms | 33 / 37 ms |
| 10k | 5000 (config max) | 0.45 | 256 ms | 193 ms | 442 / 479 ms |
| 10k | all | 1.00 | 517 ms | 409 ms | 932 / 1027 ms |
| 50k | 400 (default) | 0.00 | 18 ms | 15 ms | 33 / 39 ms |
| 50k | 5000 (config max) | 0.00 | 243 ms | 201 ms | 435 / 486 ms |
| 50k | all | 0.95 | 2474 ms | 1913 ms | 4315 / 4717 ms |

## Decision

1. **The candidate cap is the real problem, not cosine.** Candidates are the newest N chunks
   (`ORDER BY id DESC LIMIT cap`), chosen by recency, not relevance. Beyond ~400 chunks, older knowledge
   silently becomes unreachable (recall 0.20 at 1k, 0.00 at 10k). The 400 default is only safe for a
   workspace under a few hundred chunks.
2. **Python cosine is acceptable only up to about 5-10k chunks, and only if candidates are chosen by
   relevance first.** A full scan is ~0.9 s at 10k and ~4.3 s at 50k, which is too slow for an agent tool.
3. **Decision rule for a vector backend:** do not add pgvector or a vector DB while workspaces stay below
   ~5k chunks. Before that, replace recency selection with a relevance pre-filter (MariaDB FULLTEXT or
   token-index candidate selection), then re-run this benchmark. Move to a vector index only if, with a
   relevance pre-filter, recall@5 at the target corpus size stays below the golden-set floor or p95 exceeds
   ~500 ms. pgvector is not justified by current evidence; a relevance-based candidate stage is.

Not implemented in this pass (out of scope, needs a schema/index decision): the relevance pre-filter.
