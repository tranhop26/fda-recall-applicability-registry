# Architecture

The registry is one intentionally frozen Intelligent Contract. It stores canonical case and assessment JSON in two `TreeMap` collections. Deterministic code owns validation, state transitions, timestamps, hashing, evidence shape/freshness, mask arithmetic, and verdict derivation. One bounded nondeterministic block owns the openFDA request and semantic LLM classification.

## Data flow

1. Anyone opens a unique case with an exact recall number and canonical product subject.
2. The contract stores the subject hash, registrar, transaction timestamp, 48-hour deadline, source identity, and replay domain.
3. Anyone resolves before the deadline; the method has no outcome argument.
4. Leader and validators independently fetch the contract-built openFDA URL.
5. Code requires HTTP 200, bounded UTF-8 JSON, one exact record, stable string fields, and a fresh `meta.last_updated`.
6. The LLM classifies five dimensions as `MATCH`, `CONFLICT`, or `UNAVAILABLE`.
7. Validators compare normalized masks and source identity/version. Explanation wording is ignored.
8. Code derives the verdict and stores one immutable assessment.
9. Consumers read `read_effective_status`; stale results fail closed while `read_assessment` retains history.

No caller-provided URL, model prompt, mask, verdict, owner role, or financial state exists.
