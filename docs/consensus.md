# Consensus and semantic equivalence

The Equivalence Principle is applied to business meaning, not string formatting. Each validator independently refetches and evaluates the same case. Agreement is the normalized evaluation object: disjoint complete semantic masks, source-valid flag, canonical stable-record hash, and source update date. The non-authoritative `reason` text is discarded before comparison.

| Stored decision input | Source | Downstream effect | Validator check | Comparison | Differential test |
|---|---|---|---|---|---|
| `match_mask` | Five LLM classifications | Enables `AFFECTED` only at `31` | Independently classifies every dimension | Exact normalized integer mask | Different reason/same masks accepted |
| `conflict_mask` | Explicit source contradiction | Any nonzero bit derives `NOT_AFFECTED` | Requires conflict evidence, never absence | Exact normalized integer mask | Changed lot meaning rejected |
| `unavailable_mask` | Missing or ambiguous evidence | Any remaining bit prevents `AFFECTED` | Missing text is unavailable | Exact normalized integer mask | Partial date produces `UNRESOLVED` |
| `source_hash` | Canonical stable FDA fields | Binds result to record version/content | Independently fetches and hashes | Exact SHA-256 | Wrong/malformed/duplicate record fails closed |
| `source_last_updated` | `meta.last_updated` | Enforces source age | Parses UTC calendar date, rejects future/>10 days | Exact date | Stale, future, malformed, 10-day boundary tests |

Mask bits are manufacturer `1`, product identity `2`, lot/code `4`, territory `8`, and relevant date `16`; the complete known mask is `31`. Masks must be non-boolean integers, within range, disjoint, and cover `31` exactly.

Verdict derivation is deterministic:

```text
invalid source -> UNRESOLVED
any explicit conflict -> NOT_AFFECTED
all dimensions match -> AFFECTED
otherwise -> UNRESOLVED
```

If validators do not agree, consensus rejects the write. The case remains `PENDING`, and its effective status remains `UNRESOLVED`.
