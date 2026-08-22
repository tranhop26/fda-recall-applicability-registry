# FDA Recall Applicability Registry — Design Specification

## 1. Purpose and scope

The project is an independent GenLayer Intelligent Contract that decides whether one immutable description of an FDA-regulated product falls within one specific FDA recall enforcement record.

The contract is the authoritative source of the decision and its on-chain status. It does not authenticate a physical product, give medical advice, search for every possible recall, transfer value, or replace the FDA. The primary reusable consumer is a marketplace, inventory registry, compliance workflow, or product-safety application that needs a shared decision without trusting one party's backend.

The initial source supports the structurally compatible openFDA enforcement endpoints for `food`, `drug`, and `device`. No caller-supplied URL is fetched.

## 2. Alternatives considered

### 2.1 Open-web recall discovery

Search arbitrary web pages for a recall matching a product. This is flexible but exposes source selection, search-ranking, prompt-injection, freshness, and SSRF risks. It also makes a negative result difficult to interpret safely.

### 2.2 Multi-source recall adjudication

Compare several regulators, manufacturer notices, and press reports. This can cover more jurisdictions but introduces source-priority and contradiction policies beyond the requested single workflow.

### 2.3 Notice-specific FDA applicability — selected

The caller identifies one FDA recall number and an immutable product subject. The contract constructs a fixed openFDA query, verifies the record mechanically, and uses LLM reasoning only for semantic applicability. This provides a bounded decision, a stable provenance model, and a meaningful fail-closed result.

## 3. Trust model

### 3.1 Parties that cannot trust each other

A seller or manufacturer may want a product declared outside a recall. A buyer, marketplace, or safety reviewer may want it declared affected. Neither side should control the evidence interpretation. The transaction caller, registrar, deployer, and any off-chain service must not be able to submit or override the verdict.

### 3.2 Trust matrix

| Actor | Cannot trust | Can manipulate | Contract defense | Test or evidence |
|---|---|---|---|---|
| Case registrar | Seller, buyer, manufacturer, marketplace | Subject description, recall number, timing | Canonical immutable subject; decision is explicitly scoped to the submitted subject; fixed source construction; case ID uniqueness | Canonicalization, mutation rejection, bounds, duplicate case tests |
| Resolver | Disputing parties | Trigger timing, repeated calls | Permissionless trigger; no verdict argument; single-use transition; fixed source and rubric | Replay and invalid-transition tests |
| Deployer | Contract users | Code or decision after deployment | `INTENTIONALLY_FROZEN`; no upgrader, admin verdict, pause, or storage-rewrite method | Schema/source inspection and frozen-classification tests |
| openFDA/FDA publisher | Registrar and integrators | Source data may be corrected, delayed, unavailable, or structurally changed | Exact recall binding, bounded stable fields, source update timestamp, freshness policy, `UNRESOLVED` on failures | Missing, stale, future, duplicate, mismatch, malformed, and HTTP failure tests |
| Leader validator | Other validators and users | Hallucinated classification, malformed masks, selective interpretation | Independent refetch and semantic re-evaluation; masks must form a valid partition; deterministic verdict derivation | Validator dissent and differential mask tests |
| Downstream integrator | Registrar and resolver | Display or cache a favorable stale result | Authoritative `read_effective_status`; pending, closed, stale, and failed states read as `UNRESOLVED` | TTL and readback tests |

### 3.3 Explicit limitation

The contract decides applicability to a declared subject. It does not prove that a physical item actually has the declared manufacturer, model, lot, territory, or date. A downstream system requiring that guarantee must bind the subject hash to separate authenticated product identity evidence.

## 4. Decision and consequence

### 4.1 Decision statement

For a case-bound product subject and one exact FDA recall number, GenLayer establishes whether the stable fields in the live openFDA enforcement record semantically include or explicitly exclude the subject.

### 4.2 Result meanings

- `AFFECTED`: all required semantic dimensions match and none is conflicting or unavailable.
- `NOT_AFFECTED`: at least one required distinguishing dimension is explicitly conflicting with the FDA record.
- `UNRESOLVED`: the record, source, freshness, schema, subject detail, semantic evidence, or consensus is insufficient.

Absence of evidence never becomes `NOT_AFFECTED`. That verdict requires an explicit, validator-agreed conflict.

### 4.3 On-chain consequence

The contract stores the terminal case state, derived verdict, semantic masks, hashes, FDA source update date, assessment transaction time, validity deadline, and predecessor link. `read_effective_status` is the integration oracle. It returns `UNRESOLVED` for pending, closed-unresolved, or expired decisions even if an old stored verdict remains available for audit.

No stake, escrow, payout, fee, refund, or custody mechanism is included because the core use case does not require value transfer.

## 5. Evidence model

### 5.1 Subject schema

The registrar submits canonical compact JSON with exactly these fields:

```json
{
  "date_type": "manufacture|best_by|expiry|purchase|unknown",
  "date_value": "YYYY-MM-DD or empty",
  "lot_or_code": "string",
  "manufacturer": "string",
  "model_or_sku": "string",
  "product_name": "string",
  "territory": "string"
}
```

Strings are bounded. Unknown or missing real-world attributes are represented explicitly and normally produce an unavailable semantic dimension rather than a favorable verdict. The exact canonical bytes and SHA-256 subject hash are stored.

### 5.2 Fixed source

The contract accepts only `product_type` values `food`, `drug`, or `device` and a bounded recall-number character set. It constructs:

```text
https://api.fda.gov/{product_type}/enforcement.json?search=recall_number:%22{recall_number}%22&limit=2
```

The caller cannot provide a hostname, URL, query field, API key, redirect target, or model prompt.

### 5.3 Stable FDA fields

The nondeterministic block parses the response and extracts only:

- `recall_number`
- `recalling_firm`
- `product_description`
- `code_info`
- `distribution_pattern`
- `recall_initiation_date`
- `report_date`
- `status`
- `termination_date`
- `classification`
- `meta.last_updated`

The query must return exactly one record whose normalized recall number equals the case value. Zero results, duplicates, an unexpected root, oversized content, wrong types, or a mismatch resolve to unavailable evidence.

### 5.4 Version, identity, time, and freshness

- Provenance: FDA Recall Enterprise System exposed by `api.fda.gov`.
- Subject identity: canonical subject SHA-256.
- Source identity: product type plus exact recall number.
- Schema version: `openfda-enforcement-v1`.
- Observation time: deterministic GenLayer transaction timestamp.
- Source version time: `meta.last_updated` parsed from the response.
- Freshness rule: `meta.last_updated` must not be in the future and must be no more than ten days older than the assessment transaction. openFDA documents a weekly update schedule; ten days permits normal weekly timing while failing closed on a missed update.
- Decision validity: ten days from assessment. After that, the effective read is `UNRESOLVED` and a refresh case is required.
- Integrity: SHA-256 of canonical stable FDA fields, canonical subject, and the final assessment payload.

### 5.5 Replay domain

Every case stores a domain hash over:

```text
schema version | chain ID | contract address | case ID | registrar |
product type | recall number | subject hash | predecessor reference
```

The resolution action additionally binds `RESOLVE` and the stored domain hash in the validator prompt. Case IDs are globally single-use within the contract, and a case can be resolved once.

### 5.6 Failure policy

Unavailable web data, non-200 responses, stale or future metadata, malformed JSON, excessive size, recall mismatch, duplicate records, missing required source fields, semantic ambiguity, malformed LLM output, or an invalid mask returns an all-unavailable evaluation and derives `UNRESOLVED` when consensus accepts that failure classification.

If validators do not reach consensus, the transaction does not mutate state. The case remains `PENDING`, whose effective status is `UNRESOLVED`. It may be retried until the deterministic resolution deadline.

## 6. Semantic evaluation and Equivalence Principle

### 6.1 Required semantic dimensions

| Bit | Dimension | FDA evidence |
|---:|---|---|
| 1 | Manufacturer | `recalling_firm`, `product_description` |
| 2 | Product identity | `product_description` |
| 4 | Lot, serial, code, model, or SKU | `code_info`, `product_description` |
| 8 | Territory or distribution | `distribution_pattern` |
| 16 | Relevant product date | `code_info`, recall and report dates where semantically applicable |

The LLM must classify every dimension as exactly one of `MATCH`, `CONFLICT`, or `UNAVAILABLE`. The contract converts these classifications into disjoint `match_mask`, `conflict_mask`, and `unavailable_mask` that must partition the known mask `31`.

### 6.2 Appropriate LLM use

The LLM interprets natural-language descriptions such as lot ranges, alternative product naming, distribution scope, and date expressions. Mechanical facts—HTTP status, JSON shape, exact recall number, source timestamp, field types, bounds, and hashes—are checked programmatically.

Web text is quoted as untrusted evidence and never treated as instructions. The prompt is fixed by the contract and requests structured JSON with the three masks; free-form reasoning is not authoritative or stored.

### 6.3 Validator behavior

The leader fetches and evaluates the bound evidence. Each validator independently fetches the same fixed endpoint and performs the same semantic classification. A validator accepts only when:

1. the leader result is structurally and arithmetically valid;
2. source identity and freshness checks independently pass or independently produce the same all-unavailable classification;
3. the three semantic masks match the validator's independent classification; and
4. the deterministic verdict derived from those masks is identical.

Reasoning prose and JSON key order are not compared. The validator evaluates business meaning through the dimension classifications, not merely output format.

### 6.4 Deterministic verdict derivation

```text
if source_invalid_or_stale:
    UNRESOLVED
else if conflict_mask != 0:
    NOT_AFFECTED
else if match_mask == 31 and unavailable_mask == 0:
    AFFECTED
else:
    UNRESOLVED
```

The caller, registrar, owner, deployer, frontend, and model cannot directly set the stored verdict.

## 7. Domain model and state machine

### 7.1 Case states

- `PENDING`: immutable case exists; no consensus result has been stored.
- `DECIDED`: one consensus assessment has been stored.
- `CLOSED_UNRESOLVED`: the case was deterministically closed after its resolution deadline without a decision.

`AFFECTED`, `NOT_AFFECTED`, and `UNRESOLVED` are verdicts, not lifecycle states.

### 7.2 Fixed timing

- Resolution deadline: 48 hours after case creation.
- Source maximum age: 10 days at assessment.
- Decision validity: 10 days after assessment.

These are contract constants, not caller-selected policy.

### 7.3 Transition table

| From | Actor | Method | Preconditions | On-chain effect | To | Replay behavior |
|---|---|---|---|---|---|---|
| Absent | Anyone | `open_case` | Unique bounded case ID; canonical subject; valid type and recall number; valid predecessor reference or empty | Store immutable case, timestamps, hashes, registrar, and replay domain | `PENDING` | Duplicate ID rejected |
| `PENDING` | Anyone | `resolve_case` | Before deadline; no assessment | Run web plus LLM consensus; validate masks; store derived verdict and evidence binding | `DECIDED` | Further resolution rejected |
| `PENDING` | Anyone | `close_unresolved` | Deadline reached; no assessment | Store terminal unresolved closure and closure time | `CLOSED_UNRESOLVED` | Further close or resolve rejected |
| `DECIDED` or `CLOSED_UNRESOLVED` | Anyone | `open_case` with predecessor | New unique ID; predecessor exists; same subject hash, product type, and recall number | Store new linked refresh case | New `PENDING` case | Old case unchanged; duplicate child ID rejected |

All consequential methods are permissionless because no caller can supply the outcome. Permissionless behavior will be tested with an unrelated address.

### 7.4 Reads

- `read_case`: immutable input and lifecycle metadata.
- `read_assessment`: stored historical verdict, masks, evidence hashes, and source timestamps; unavailable before decision.
- `read_effective_status`: returns current authoritative result and freshness. It returns `UNRESOLVED` for pending, closed, expired, or missing effective evidence.
- `read_predecessor`: migration or refresh provenance.

## 8. Contract classification and recovery

The contract is `INTENTIONALLY_FROZEN`.

No address is added to native GenVM upgraders. The public schema contains no upgrade, admin override, force-resolve, arbitrary source, pause, or storage-rewrite method. The consequence is that defects and policy changes cannot be patched in place.

Recovery procedure:

1. stop integrations from opening new cases on the affected deployment;
2. publish and test a corrected contract version;
3. obtain explicit deployment-wallet confirmation;
4. deploy and verify the new source hash;
5. create refresh cases on the new contract with predecessor references containing the old contract address and case ID;
6. have downstream integrations explicitly switch to the verified new address.

Historical decisions remain readable and cannot be rewritten. There is no privileged rescue path because the contract holds no funds.

## 9. Architecture and repository structure

The repository follows the useful separation of concerns observed in the reference project without copying its research-domain contract or workflow:

```text
contracts/       Intelligent Contract source
tests/direct/    deterministic, authorization, lifecycle, failure, and validator tests
tests/integration/ network deployment, transaction, consensus, and readback tests
deploy/          explicit deployment and sample-transaction scripts
samples/         canonical subject and negative fixtures
docs/            architecture, consensus, security, recovery, and design records
deployments/     manifest template and verified network manifests
verification/    fixed test summaries and live proof matrix
```

The contract remains one focused contract. Helper logic stays as small pure functions in the same source file where GenVM deployment constraints make that clearest; test and operational concerns are separated into their own directories.

## 10. Data flow

1. A registrar canonicalizes and submits a product subject, product type, exact FDA recall number, and optional predecessor.
2. The contract validates and stores the immutable case and replay domain.
3. Any address calls `resolve_case` before the deadline.
4. Leader and validators independently query the contract-constructed openFDA endpoint.
5. Each execution verifies source identity, schema, stable fields, and freshness programmatically.
6. The LLM classifies the five business dimensions.
7. The Equivalence Principle accepts only semantic-mask agreement.
8. Deterministic code derives and stores the verdict and evidence hashes.
9. Integrators read `read_effective_status`; they never advance based solely on a submitted transaction hash or off-chain cache.
10. After expiry, the effective status fails closed until a linked refresh case is assessed.

## 11. Error handling

- Invalid caller input and invalid transitions revert without mutation.
- External and model failures become an all-unavailable evaluation where possible.
- Consensus failure leaves the state pending and therefore effectively unresolved.
- Repeated calls cannot overwrite a terminal record.
- Read methods distinguish missing assessment data from an effective unresolved status.
- Deployment and sample scripts poll for `FINALIZED`, then require execution `SUCCESS`, then perform readback. A submitted hash alone is never treated as success.

## 12. Testing strategy

### 12.1 Direct tests

Direct tests cover:

- canonical subject success and malformed/non-canonical/oversized input;
- valid product types and recall-number character constraints;
- caller inability to submit URLs, prompts, masks, or verdicts;
- case uniqueness, predecessor integrity, and replay-domain separation;
- permissionless resolution and closure by an unrelated address;
- early closure, late resolution, double resolution, double closure, and terminal transitions;
- exact recall mismatch, zero and duplicate records;
- HTTP failure, malformed JSON, missing fields, oversized response;
- fresh, stale, and future `meta.last_updated`;
- complete match, explicit conflict, partial evidence, and all-unavailable derivation;
- malformed, overlapping, incomplete, and out-of-range masks;
- validator semantic agreement, dissent, and changed-mask rejection;
- pending and expired effective-status fail-closed behavior;
- refresh linkage without mutation of history;
- no upgrader or privileged recovery path.

Every bug fixed during implementation receives a regression test.

### 12.2 Integration tests

Integration tests cover contract deployment, schema readback, case opening, unrelated-address resolution, validator consensus, receipt polling, terminal execution status, authoritative readback, replay rejection, and source-code retrieval/hash comparison.

Local or mocked integration verifies controlled positive and negative branches. Studionet evidence must include at least one complete live case transaction. If the live FDA source or validators cannot establish a positive or negative result, the valid demonstration result is `UNRESOLVED`; it must not be relabeled as a successful safety decision.

### 12.3 Tooling and quality gates

- Pin Python and GenLayer dependencies.
- Run `genvm-lint` against the contract.
- Run the formatter/linter selected for Python support files.
- Run all direct tests.
- Run integration tests in the configured environment.
- Scan tracked and untracked publication candidates for secrets and generated artifacts.
- Record exact commands, exit codes, dependency versions, commit, and source SHA-256.

## 13. Deployment and verification gates

Before deployment, inspect the active GenLayer network, chain ID, CLI configuration, deployment wallet, Git author, repository remote, and active GitHub identity where applicable. State the exact proposed deployment and stop for user confirmation.

After confirmation:

1. deploy the exact tested source;
2. poll the deployment receipt to `FINALIZED` and execution `SUCCESS`;
3. record contract address, deployment transaction, network, chain ID, deployer, commit, source SHA-256, and explorer link in a manifest;
4. execute a complete sample case workflow;
5. poll every transaction to `FINALIZED` and verify execution `SUCCESS` or the explicitly expected rollback;
6. read authoritative state from the deployed contract;
7. retrieve deployed code and compare its SHA-256 with the delivered source;
8. publish a proof matrix mapping every material claim to transaction and test evidence.

No private key, API key, token, mnemonic, raw prompt transcript, local instruction file, or credential-bearing configuration may enter source, logs, README, commits, or verification artifacts. `.env.example` contains variable names and safe public defaults only.

## 14. Deliverables

- Intelligent Contract source.
- Direct tests and network integration tests.
- Deployment and sample-workflow scripts.
- Deployment manifest schema and verified Studionet manifest.
- `.env.example` without secrets.
- README covering installation, lint, test, deployment, interaction, failure semantics, frozen recovery, and limitations.
- Contract address, deployment transaction, explorer link, sample transaction, final receipt states, readback, exact commit, and source hash after authorized deployment.
- Fixed local verification summary and proof matrix.

## 15. Success criteria

The project is complete only when the delivered source passes lint and all tests; the confirmed wallet deploys that exact source; deployment and sample transactions reach `FINALIZED` with execution `SUCCESS`; contract readback matches the expected state; deployed code hashes to the delivered source; and the evidence package contains no unsupported claim or secret.

Until those conditions are met, the project remains incomplete and its README and handoff must state the missing evidence precisely.

## 16. Authoritative references

- GenLayer project criteria supplied by the user: <https://docs.google.com/document/d/1OFI3yLTi3QyBeNZgtm_0G9iuuCD9-77q7cn3IPDsFgY/edit>
- GenLayer Equivalence Principle: <https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle>
- GenLayer web access: <https://docs.genlayer.com/developers/intelligent-contracts/features/web-access>
- GenLayer transaction context: <https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context>
- GenLayer upgradability and freezing: <https://docs.genlayer.com/developers/intelligent-contracts/features/upgradability>
- GenLayer testing: <https://docs.genlayer.com/developers/intelligent-contracts/testing>
- openFDA food enforcement overview and weekly update policy: <https://open.fda.gov/apis/food/enforcement/>
- openFDA device enforcement overview and weekly update policy: <https://open.fda.gov/apis/device/enforcement/>
- openFDA enforcement searchable fields: <https://open.fda.gov/apis/food/enforcement/searchable-fields/>
