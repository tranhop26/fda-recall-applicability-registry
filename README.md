# FDA Recall Applicability Registry

An `INTENTIONALLY_FROZEN` GenLayer Intelligent Contract that decides whether one immutable, declared product subject is covered by one exact FDA enforcement recall. The contract—not the caller, registrar, deployer, or an off-chain service—is the source of truth for the decision.

## Before the code: the trust problem

- Parties that cannot trust each other: a seller/manufacturer may prefer `NOT_AFFECTED`; a buyer, marketplace, or safety reviewer may prefer `AFFECTED`. Neither side may submit or override a verdict.
- Truth GenLayer establishes: whether the five declared dimensions—manufacturer, product identity, lot/code, territory, and relevant date—match, explicitly conflict with, or are unavailable in the bound FDA recall record.
- On-chain consequence: a case moves from `PENDING` to `DECIDED` and stores a deterministic `AFFECTED`, `NOT_AFFECTED`, or fail-closed `UNRESOLVED` assessment. After expiry, the effective read returns `UNRESOLVED` while historical evidence remains auditable.
- Data and insufficient-evidence policy: the contract builds an exact `api.fda.gov/{food|drug|device}/enforcement.json` URL from the product type and recall number. It requires one matching record, stable fields, a non-future `meta.last_updated` no more than ten calendar days old, and validator agreement on semantic masks. Missing, stale, malformed, contradictory, inaccessible, or non-consensus evidence never auto-approves; it produces `UNRESOLVED` or leaves the case pending.

This project has no funds, escrow, stake, payout, refund, owner, or admin override because the workflow does not require financial custody.

## Core workflow

```text
Absent --open_case--> PENDING --resolve_case before 48h--> DECIDED
                              --close_unresolved after 48h--> CLOSED_UNRESOLVED

DECIDED --after 10-day validity--> effective UNRESOLVED / STALE
terminal local case --open_case with same identity--> new linked PENDING case
```

`AFFECTED` requires all five dimensions to match. `NOT_AFFECTED` requires at least one explicit conflict. Missing or ambiguous evidence is `UNRESOLVED`.

Public methods:

- `open_case(case_id, product_type, recall_number, subject_json, predecessor_contract, predecessor_case_id)`
- `resolve_case(case_id)`
- `close_unresolved(case_id)`
- `read_case(case_id)`
- `read_assessment(case_id)`
- `read_effective_status(case_id)`
- `read_predecessor(case_id)`

All writes are permissionless, but no write method accepts a verdict, semantic mask, prompt, URL, or source result. A case is single-use and terminal states cannot be overwritten.

## Repository

- `contracts/fda_recall_applicability_registry.py`: deployable Intelligent Contract
- `tests/direct`: input, state, permissions, evidence, LLM, and validator tests
- `tests/integration`: live network deploy/write/consensus/readback/replay flow
- `deploy/run_studionet.py`: read-only preflight and confirmed verified deployment
- `samples`: canonical real-record subject and explicit-conflict fixture
- `deployments/manifest.schema.json`: deployment evidence contract
- `verification`: test summary schema and proof matrix
- `docs`: architecture, consensus, security, and frozen recovery

## Install

Python 3.12+ and GenLayer CLI 0.39.2 are expected.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --requirement requirements.txt
```

On Windows, the current direct GenVM runner can encounter an open-file limitation. The verified workaround is to run direct tests in WSL while keeping lint and support tests in the Windows environment.

## Lint and tests

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\genvm-lint check contracts\fda_recall_applicability_registry.py
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest -m "not integration and not studionet" -q
.\.venv\Scripts\python -m pytest tests\integration --collect-only -q
```

Direct tests from WSL:

```bash
PYTHONUTF8=1 python3 -m pytest tests/direct -q
```

The live integration test is intentionally gated because it deploys and sends transactions:

```powershell
$env:RUN_STUDIONET='1'
.\.venv\Scripts\python -m pytest tests\integration -m studionet -v
```

## Canonical input

`subject_json` must be compact, sorted JSON with exactly these string fields:

```json
{"date_type":"best_by","date_value":"2027-01-19","lot_or_code":"260119","manufacturer":"PT Organics Limited","model_or_sku":"PTO Item 10720","product_name":"Pumpkin Tree Peter Rabbit Organics Banana & Strawberry fruit puree, 4oz/113g pouch","territory":"Virginia"}
```

`date_type` is one of `manufacture`, `best_by`, `expiry`, `purchase`, or `unknown`. An unknown date requires an empty value; other types require `YYYY-MM-DD`.

The sample is bound to openFDA recall `H-1223-2026`, observed with source update date `2026-08-12`. The contract always re-fetches and rechecks freshness at resolution time; the repository never treats the sample file as evidence.

## Safe deployment

Copy `.env.example` only if useful; it contains no secret. The CLI account remains in the GenLayer account store. Do not place a private key or mnemonic in this repository.

Read-only preflight:

```powershell
.\.venv\Scripts\python deploy\run_studionet.py
```

This prints the exact network, chain ID, active wallet, contract hash, and planned actions, then exits without mutation. After the user confirms that exact context:

```powershell
.\.venv\Scripts\python deploy\run_studionet.py --confirmed-wallet 0xCONFIRMED_ADDRESS
```

The runner requires Studionet chain ID `61999`, exact wallet match, `FINALIZED` plus `SUCCESS` for deploy/open/resolve, contract readback, and deployed-source hash equality before atomically writing `deployments/studionet.json`.

## Current deployment status

Not deployed yet. No contract address or transaction is claimed until the confirmation gate and live verification complete.

## Frozen classification and recovery

The contract is `INTENTIONALLY_FROZEN`: there is no upgrader, owner, admin override, force resolve, pause, or arbitrary-source setter. Same-deployment refreshes may link only to an existing terminal local case with identical product type, recall number, and subject hash.

For a defect or policy change, deploy a newly reviewed contract, verify its source hash, publish an old-to-new migration mapping in the deployment evidence, and require consumers to switch explicitly. Cross-deployment predecessor validation is intentionally not claimed because the current contract cannot authenticate an external deployment's storage.

See `docs/recovery.md` for the exact runbook.

## Security and limitations

- The contract decides applicability for submitted attributes; it does not authenticate a physical item.
- openFDA can be unavailable, delayed, corrected, or stale. Those conditions fail closed.
- FDA text is untrusted quoted evidence. Mechanical source checks are code, while the LLM only classifies bounded natural-language dimensions.
- Validators compare normalized business meaning—three masks plus source hash/date—not explanation wording or JSON key order.
- `read_effective_status`, not an off-chain cache or submitted transaction hash, is the authoritative integration read.
- The live result may validly be `UNRESOLVED`; the runner never substitutes an expected favorable outcome.

Authoritative background: [GenLayer Equivalence Principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle), [web access](https://docs.genlayer.com/developers/intelligent-contracts/features/web-access), [upgradability](https://docs.genlayer.com/developers/intelligent-contracts/features/upgradability), and [openFDA food enforcement API](https://open.fda.gov/apis/food/enforcement/).
