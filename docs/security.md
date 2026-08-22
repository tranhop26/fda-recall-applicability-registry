# Security model

## Trust boundaries

- Registrar input is untrusted and immutable after canonical validation. A malicious registrar can lie about a physical item, but cannot choose the decision for the subject it submitted.
- FDA data is an external dependency and may be wrong, corrected, unavailable, stale, duplicated, or structurally changed.
- Web content is untrusted quoted evidence, never prompt instructions.
- A leader may hallucinate or manipulate classifications; validators independently fetch and classify.
- Downstream users may cache a favorable result; only `read_effective_status` is authoritative.

## Fail-closed behavior

HTTP errors, response overflow, invalid UTF-8/JSON, unexpected shape, zero or duplicate results, recall mismatch, missing stable fields, future or stale source dates, malformed model output, incomplete/overlapping masks, and accepted unavailable evidence derive `UNRESOLVED`. Consensus failure does not mutate state. Expiry makes the effective read `UNRESOLVED/STALE` without deleting history.

## Replay and authorization

Case IDs are single-use. The replay domain binds chain, contract, case, registrar, source identity, subject hash, and predecessor. `resolve_case` and `close_unresolved` accept no result and terminal cases reject repeat writes. Permissionless calls remove caller-based outcome control.

## Frozen and custody posture

There is no owner, admin, upgrader, override, pause, arbitrary source, stake, escrow, payout, refund, or balance accounting. Deployment is therefore the only code-selection authority, and exact source verification is mandatory.

## Remaining limitations

- Declared subject attributes are not physical-product authentication.
- One exact recall is checked; the contract is not recall discovery.
- Only openFDA enforcement endpoints for food, drug, and device are supported.
- Semantic classification can remain unresolved despite valid evidence.
- Cross-deployment lineage is documented externally, not authenticated by this contract.
