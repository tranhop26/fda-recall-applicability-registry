# FDA Recall Applicability Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, deploy, and verify an intentionally frozen GenLayer Intelligent Contract that decides whether an immutable product subject is affected by one exact FDA recall enforcement record.

**Architecture:** A single Python Intelligent Contract stores canonical cases and terminal assessments as JSON in `TreeMap` storage. Deterministic code validates identity, lifecycle, freshness, replay, and verdict derivation; a bounded nondeterministic block fetches a contract-constructed openFDA endpoint and uses an LLM only to classify five semantic applicability dimensions. Direct tests mock web and LLM behavior, integration tests exercise GenLayer transaction and readback behavior, and a deployment runner records only finalized successful evidence.

**Tech Stack:** Python 3.12+, GenVM/`py-genlayer` pinned by contract dependency hash, `genlayer-test==0.29.2`, `genlayer-py==0.16.3`, `genvm-linter==0.11.0`, `pytest==9.1.1`, `ruff==0.12.5`, GenLayer CLI `0.39.2`, GenLayer Studionet chain ID `61999`.

## Global Constraints

- The Intelligent Contract is the source of truth; caller, registrar, deployer, owner, scripts, and model cannot submit or override a verdict.
- Contract classification is exactly `INTENTIONALLY_FROZEN`; do not add any native upgrader or public upgrade/admin override method.
- Fetch only `https://api.fda.gov/{food|drug|device}/enforcement.json` with a contract-built exact recall-number query.
- Required verdicts are exactly `AFFECTED`, `NOT_AFFECTED`, and fail-closed `UNRESOLVED`.
- Required lifecycle states are exactly `PENDING`, `DECIDED`, and `CLOSED_UNRESOLVED`.
- Semantic bits are `MANUFACTURER=1`, `PRODUCT_IDENTITY=2`, `LOT_OR_CODE=4`, `TERRITORY=8`, `RELEVANT_DATE=16`, and `KNOWN_MASK=31`.
- Resolution deadline is 48 hours; maximum openFDA source age and decision validity are each 10 days.
- `NOT_AFFECTED` requires an explicit semantic conflict; missing or ambiguous evidence is never favorable.
- No stake, escrow, payout, fee accounting, refund, or other custody feature is permitted.
- No frontend, backend service, Vercel project, arbitrary web search, or caller-supplied source URL is in scope.
- Never write a private key, mnemonic, API token, credential, or secret-bearing environment value to source, output, log, README, commit, or manifest.
- Stop for user confirmation after inspecting network and wallet and before the first live deployment transaction.
- Do not claim completion before lint, all tests, deployment, sample transaction, `FINALIZED`/`SUCCESS`, readback, and deployed-source hash comparison are evidenced.

## File Map

| File | Responsibility |
|---|---|
| `contracts/fda_recall_applicability_registry.py` | Entire deployable contract, pure validation helpers, evidence parser, semantic evaluation, lifecycle, and views |
| `tests/direct/conftest.py` | Reusable canonical subjects, FDA payloads, timestamps, and deployment helpers |
| `tests/direct/test_input_and_lifecycle.py` | Input validation, state transitions, authorization model, deadlines, replay, refresh, effective reads |
| `tests/direct/test_evidence_and_consensus.py` | Web/schema/freshness failures, semantic masks, verdict derivation, validator agreement/dissent |
| `tests/integration/test_contract_flow.py` | Network deploy/open/resolve/readback/replay flow, selected by integration marker |
| `samples/subject-affected.json` | Canonical demo subject whose fields bind to the selected FDA record |
| `samples/subject-conflict.json` | Canonical explicit-conflict subject for controlled tests |
| `deploy/run_studionet.py` | Preflight, deploy, finalized receipt checks, sample calls, readback, code retrieval, manifest generation |
| `deployments/manifest.schema.json` | Required deployment evidence schema |
| `deployments/studionet.json` | Generated only after verified live deployment; never contains secrets |
| `verification/test-summary.json` | Hash-bound local command results generated after all checks pass |
| `verification/proof-matrix.md` | Live actor/action/transaction/readback/source evidence |
| `docs/architecture.md` | Concise contract and data-flow description |
| `docs/consensus.md` | Semantic masks and Equivalence Principle rationale |
| `docs/security.md` | Trust boundaries, fail-closed behavior, and limitations |
| `docs/recovery.md` | Frozen-contract migration runbook |
| `.env.example` | Safe public variable names only |
| `.gitignore` | Excludes secrets, environments, caches, generated logs, and intermediate `work/` |
| `gltest.config.yaml` | Contract path and network configuration |
| `pyproject.toml` | Ruff and pytest configuration |
| `requirements.txt` | Exact Python tool/test dependencies |
| `README.md` | Install, lint, tests, deploy, use, semantics, recovery, evidence, and limitations |

---

### Task 1: Project foundation and canonical case input

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `gltest.config.yaml`
- Create: `contracts/fda_recall_applicability_registry.py`
- Create: `tests/direct/conftest.py`
- Create: `tests/direct/test_input_and_lifecycle.py`

**Interfaces:**
- Consumes: the approved subject schema and constants in the design spec.
- Produces: `FdaRecallApplicabilityRegistry.__init__()`, `open_case(case_id: str, product_type: str, recall_number: str, subject_json: str, predecessor_contract: str, predecessor_case_id: str)`, `_canonical_subject(subject_json: str) -> tuple[str, str]`, and stored case JSON.

- [ ] **Step 1: Add pinned tool configuration and safe ignores**

Create `requirements.txt` with:

```text
genlayer-test==0.29.2
genlayer-py==0.16.3
genvm-linter==0.11.0
pytest==9.1.1
ruff==0.12.5
```

Configure Ruff for Python 3.12 with line length 120, Pytest markers `integration` and `studionet`, and `gltest.config.yaml` with `paths.contracts: contracts`. Ignore `.env`, virtual environments, caches, test output, `work/`, and any local wallet/config export. `.env.example` contains only:

```text
GENLAYER_NETWORK=studionet
GENLAYER_RPC_URL=https://studio.genlayer.com/api
DEPLOYMENT_MANIFEST=deployments/studionet.json
```

- [ ] **Step 2: Write failing canonical-input tests**

Add tests that deploy the skeleton and assert:

```python
def test_open_case_stores_canonical_subject(direct_deploy, canonical_subject):
    contract = direct_deploy(CONTRACT)
    contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")
    case = contract.read_case("case-1")
    assert case[0] == "PENDING"
    assert case[1] == "food"
    assert case[2] == "F-1000-2026"
    assert len(case[3]) == 64


@pytest.mark.parametrize("product_type", ["cosmetic", "FOOD", "", "food/../drug"])
def test_open_case_rejects_invalid_product_type(direct_deploy, canonical_subject, product_type):
    contract = direct_deploy(CONTRACT)
    with pytest.raises(Exception, match="Invalid product type"):
        contract.open_case("case-1", product_type, "F-1000-2026", canonical_subject, "", "")


def test_open_case_rejects_noncanonical_subject(direct_deploy, pretty_subject):
    contract = direct_deploy(CONTRACT)
    with pytest.raises(Exception, match="canonical JSON"):
        contract.open_case("case-1", "food", "F-1000-2026", pretty_subject, "", "")
```

Also cover exact subject keys, string types, enum `date_type`, ISO-or-empty `date_value`, identifier bounds, recall character set `[A-Za-z0-9-]`, oversized fields, and duplicate IDs.

- [ ] **Step 3: Run the focused tests and observe failure**

Run:

```powershell
python -m pytest tests/direct/test_input_and_lifecycle.py -q
```

Expected: collection or deployment failure because the contract and methods are not implemented.

- [ ] **Step 4: Implement minimal canonical case storage**

Use the exact contract dependency header from the reference SDK:

```python
# { "Seq": [{ "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }] }
from genlayer import *

import hashlib
import json
from datetime import datetime, timezone


class FdaRecallApplicabilityRegistry(gl.Contract):
    cases: TreeMap[str, str]
    assessments: TreeMap[str, str]

    def __init__(self):
        self.cases = TreeMap[str, str]()
        self.assessments = TreeMap[str, str]()
```

Implement bounded `_canonical_json`, SHA-256, exact key validation, product type/recall/case validation, transaction timestamp capture, and immutable case storage. Store `registrar`, `created_at`, `resolution_deadline`, predecessor fields, subject hash, and a replay-domain hash that includes schema version, `gl.message.chain_id`, `gl.message.contract_address`, case ID, registrar, source identity, subject hash, and predecessor.

- [ ] **Step 5: Run lint and focused tests**

Run:

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
python -m ruff check tests/direct contracts
python -m pytest tests/direct/test_input_and_lifecycle.py -q
```

Expected: lint succeeds and all Task 1 tests pass.

- [ ] **Step 6: Commit the foundation**

```powershell
git add .gitignore .env.example requirements.txt pyproject.toml gltest.config.yaml contracts tests/direct
git commit -m "feat: add canonical FDA recall cases"
```

### Task 2: Lifecycle, permissionless actions, replay, and effective reads

**Files:**
- Modify: `contracts/fda_recall_applicability_registry.py`
- Modify: `tests/direct/test_input_and_lifecycle.py`

**Interfaces:**
- Consumes: stored case JSON and replay domain from Task 1.
- Produces: `close_unresolved(case_id: str)`, `read_case(case_id: str)`, `read_assessment(case_id: str)`, `read_effective_status(case_id: str) -> tuple[str, str, u64]`, and `read_predecessor(case_id: str)`.

- [ ] **Step 1: Write failing lifecycle and permission tests**

Add tests using `direct_vm.prank(direct_bob)` and `direct_vm.warp("2026-08-25T00:00:01+00:00")`:

```python
def test_unrelated_address_closes_after_deadline(direct_vm, direct_deploy, direct_bob, canonical_subject):
    contract = open_pending(direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-25T00:00:01+00:00")
    with direct_vm.prank(direct_bob):
        contract.close_unresolved("case-1")
    assert contract.read_effective_status("case-1")[0] == "UNRESOLVED"
    assert contract.read_case("case-1")[0] == "CLOSED_UNRESOLVED"


def test_pending_reads_fail_closed(direct_deploy, canonical_subject):
    contract = open_pending(direct_deploy, canonical_subject)
    assert contract.read_effective_status("case-1")[0] == "UNRESOLVED"
```

Cover early close rejection, double close, resolve-after-close rejection via a temporary stub, missing case, missing assessment, and unchanged state after reverts.

- [ ] **Step 2: Run focused tests and observe transition failures**

```powershell
python -m pytest tests/direct/test_input_and_lifecycle.py -q
```

Expected: new tests fail because closure and effective reads do not exist.

- [ ] **Step 3: Implement deterministic lifecycle helpers**

Implement `_case`, `_assessment`, `_store_case`, terminal-state checks, `close_unresolved`, and views. `close_unresolved` must be callable by any sender only when transaction time is at or after the stored deadline. It stores closure time but no fabricated assessment. `read_effective_status` returns `(verdict, freshness, valid_until)` with `("UNRESOLVED", "PENDING", 0)` for pending and `("UNRESOLVED", "CLOSED", 0)` for closed.

- [ ] **Step 4: Run tests and lint**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
python -m pytest tests/direct/test_input_and_lifecycle.py -q
```

Expected: all lifecycle tests pass.

- [ ] **Step 5: Commit lifecycle behavior**

```powershell
git add contracts/fda_recall_applicability_registry.py tests/direct/test_input_and_lifecycle.py
git commit -m "feat: enforce recall case lifecycle"
```

### Task 3: Bound openFDA evidence parsing and freshness

**Files:**
- Modify: `contracts/fda_recall_applicability_registry.py`
- Modify: `tests/direct/conftest.py`
- Create: `tests/direct/test_evidence_and_consensus.py`

**Interfaces:**
- Consumes: immutable `product_type`, `recall_number`, subject, replay domain, and transaction timestamp.
- Produces: `_source_url(product_type: str, recall_number: str) -> str`, `_fetch_record(product_type: str, recall_number: str, assessed_at: int) -> dict`, `_stable_fda_record(payload: dict, recall_number: str, assessed_at: int) -> dict`, and `_unresolved_evaluation() -> dict`.

- [ ] **Step 1: Add controlled FDA fixtures and failing parser tests**

The canonical success payload contains `meta.last_updated: "2026-08-21"` and one result with all stable fields. Add:

```python
def test_http_failure_becomes_unavailable(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_deploy, canonical_subject)
    direct_vm.strict_mocks = True
    direct_vm.mock_web(r"https://api[.]fda[.]gov/food/enforcement[.]json.*", {"status": 503, "body": "down"})
    mock_unavailable_llm(direct_vm)
    contract.resolve_case("case-1")
    assert contract.read_assessment("case-1")[0] == "UNRESOLVED"


@pytest.mark.parametrize("last_updated", ["2026-08-01", "2026-08-24", "not-a-date"])
def test_stale_future_or_malformed_source_is_unresolved(
    direct_vm, direct_deploy, canonical_subject, fda_payload, last_updated
):
    contract = open_pending(direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-22T12:00:00+00:00")
    fda_payload["meta"]["last_updated"] = last_updated
    mock_fda_payload(direct_vm, fda_payload)
    contract.resolve_case("case-1")
    assert contract.read_assessment("case-1")[0] == "UNRESOLVED"
```

Add exact tests for zero results, two results, wrong recall number, missing stable fields, wrong root types, invalid UTF-8, and response length over the contract cap.

- [ ] **Step 2: Run evidence tests and observe failure**

```powershell
python -m pytest tests/direct/test_evidence_and_consensus.py -q
```

Expected: failures because `resolve_case` and evidence helpers are absent.

- [ ] **Step 3: Implement fixed-source and mechanical validation**

Build only the fixed URL with `%22` quotes and `limit=2`. Bound the response before JSON parsing. Require exactly one result and exact normalized recall number. Parse `meta.last_updated` as UTC midnight, reject future values and ages greater than `SOURCE_MAX_AGE_SECONDS = 864000`, and canonicalize only the listed stable fields. On any external/schema/freshness exception, return:

```python
{
    "match_mask": 0,
    "conflict_mask": 0,
    "unavailable_mask": 31,
    "source_valid": False,
    "source_hash": "",
    "source_last_updated": "",
}
```

Do not accept a source URL, hostname, or query from storage or calldata.

- [ ] **Step 4: Run parser tests and lint**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
python -m pytest tests/direct/test_evidence_and_consensus.py -q
```

Expected: mechanical evidence failure tests pass; semantic tests remain absent.

- [ ] **Step 5: Commit evidence binding**

```powershell
git add contracts/fda_recall_applicability_registry.py tests/direct
git commit -m "feat: bind decisions to fresh openFDA evidence"
```

### Task 4: Semantic LLM evaluation and Equivalence Principle

**Files:**
- Modify: `contracts/fda_recall_applicability_registry.py`
- Modify: `tests/direct/test_evidence_and_consensus.py`

**Interfaces:**
- Consumes: canonical subject, stable FDA record, evidence hash, replay domain.
- Produces: `_valid_evaluation(value: dict) -> bool`, `_derive_verdict(match_mask: int, conflict_mask: int, unavailable_mask: int, source_valid: bool) -> str`, `_evaluate(case_json: str, assessed_at: int) -> dict`, and `resolve_case(case_id: str)`.

- [ ] **Step 1: Write failing verdict and semantic tests**

Add table tests for deterministic derivation:

```python
@pytest.mark.parametrize(
    "match_mask,conflict_mask,unavailable_mask,source_valid,expected",
    [
        (31, 0, 0, True, "AFFECTED"),
        (15, 16, 0, True, "NOT_AFFECTED"),
        (15, 0, 16, True, "UNRESOLVED"),
        (0, 0, 31, False, "UNRESOLVED"),
    ],
)
def test_semantic_verdict_derivation(
    direct_vm,
    direct_deploy,
    canonical_subject,
    fda_payload,
    match_mask,
    conflict_mask,
    unavailable_mask,
    source_valid,
    expected,
):
    contract = open_pending(direct_deploy, canonical_subject)
    mock_evaluation(
        direct_vm,
        fda_payload,
        match_mask=match_mask,
        conflict_mask=conflict_mask,
        unavailable_mask=unavailable_mask,
        source_valid=source_valid,
    )
    contract.resolve_case("case-1")
    assert contract.read_assessment("case-1")[0] == expected
```

Add invalid-mask tests for bools, negative values, out-of-range bits, overlaps, incomplete partitions, missing keys, and a leader result whose verdict field attempts to contradict deterministic derivation.

- [ ] **Step 2: Add validator meaning tests**

Use strict web/LLM mocks and `direct_vm.run_validator()`:

```python
def test_validator_accepts_different_reasoning_with_same_semantic_masks(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    resolve_with_masks(contract, direct_vm, match=31, conflict=0, unavailable=0, reason="leader wording")
    remock_same_masks(direct_vm, reason="validator wording")
    assert direct_vm.run_validator() is True


def test_validator_rejects_changed_business_meaning(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    resolve_with_masks(contract, direct_vm, match=31, conflict=0, unavailable=0)
    remock_masks(direct_vm, match=15, conflict=16, unavailable=0)
    assert direct_vm.run_validator() is False
```

This proves that prose and formatting are not authoritative while semantic dimension classifications are.

- [ ] **Step 3: Run semantic tests and observe failure**

```powershell
python -m pytest tests/direct/test_evidence_and_consensus.py -q
```

Expected: new semantic and validator tests fail.

- [ ] **Step 4: Implement the bounded prompt and validator**

The fixed JSON prompt must identify web content as untrusted quoted evidence, include the case replay domain, define all five dimensions, require a complete `MATCH|CONFLICT|UNAVAILABLE` classification, and forbid inference from absent text. Invoke `gl.nondet.exec_prompt(prompt, response_format="json")` inside the nondeterministic block.

Convert classifications to masks or require numeric masks with a complete partition. The custom validator independently calls the same fetch/evaluation path and accepts only valid leader output with identical masks, source-valid flag, source hash, and source update date. It must not compare `reason` text. Run through `gl.vm.run_nondet_unsafe`.

After consensus, validate again, derive the verdict deterministically, calculate the assessment hash, and store once. Set `assessed_at` and `valid_until = assessed_at + 864000`. A malformed consensus return raises `Invalid consensus evaluation` without mutation.

- [ ] **Step 5: Run all direct tests and lint**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
python -m ruff check tests/direct
python -m pytest tests/direct -q
```

Expected: contract lint passes and all direct tests pass.

- [ ] **Step 6: Commit consensus behavior**

```powershell
git add contracts/fda_recall_applicability_registry.py tests/direct
git commit -m "feat: add semantic recall consensus"
```

### Task 5: Refresh lineage, expiry, replay rejection, and frozen proof

**Files:**
- Modify: `contracts/fda_recall_applicability_registry.py`
- Modify: `tests/direct/test_input_and_lifecycle.py`
- Modify: `tests/direct/test_evidence_and_consensus.py`

**Interfaces:**
- Consumes: terminal cases and stored subject/source identity.
- Produces: predecessor validation, historical immutable reads, expired effective reads, and absence of privileged upgrade paths.

- [ ] **Step 1: Write failing lineage and expiry tests**

Add tests asserting that a refresh case requires an existing terminal predecessor, the same subject hash/product type/recall number, and a unique new ID. Verify the predecessor remains byte-for-byte unchanged. Warp beyond `valid_until` and assert:

```python
assert contract.read_assessment("case-1")[0] == "AFFECTED"
assert contract.read_effective_status("case-1")[0] == "UNRESOLVED"
assert contract.read_effective_status("case-1")[1] == "STALE"
```

Test repeated resolution, resolution after deadline, resolution after closure, and same inputs under a new case ID producing a different replay domain.

- [ ] **Step 2: Write the frozen-contract proof test**

Read the deployed direct schema/source and assert no callable method name contains `upgrade`, `admin`, `override`, `force`, `pause`, or `set_source`. If the direct fixture cannot expose native root metadata, retain the schema assertion and add a source test asserting no `root.upgraders` mutation exists.

- [ ] **Step 3: Run tests and observe failures**

```powershell
python -m pytest tests/direct -q
```

Expected: refresh, stale-read, or frozen-proof tests fail until implemented.

- [ ] **Step 4: Implement refresh and expiry rules**

Extend `open_case` predecessor validation without adding a separate mutable recovery method. A non-empty predecessor requires both predecessor fields, an existing terminal local predecessor, and matching subject/source identity. `read_predecessor` returns the stored contract/case reference. Preserve the historical assessment after expiry while making only the effective read fail closed.

- [ ] **Step 5: Run the complete direct gate**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
python -m ruff check tests/direct
python -m pytest tests/direct -q
```

Expected: all checks pass.

- [ ] **Step 6: Commit replay and recovery behavior**

```powershell
git add contracts/fda_recall_applicability_registry.py tests/direct
git commit -m "test: prove replay safety and frozen recovery"
```

### Task 6: Network integration tests and canonical samples

**Files:**
- Create: `tests/integration/test_contract_flow.py`
- Create: `samples/subject-affected.json`
- Create: `samples/subject-conflict.json`
- Modify: `pyproject.toml`
- Modify: `gltest.config.yaml`

**Interfaces:**
- Consumes: public contract schema from Tasks 1–5.
- Produces: marked network tests that deploy, transact to `FINALIZED`, assert execution `SUCCESS`, read back, and reject replay.

- [ ] **Step 1: Add canonical sample files**

Use compact sorted JSON matching the exact subject schema. The affected sample must be selected from the same live FDA record intended for the sample transaction; record its recall number separately in test environment configuration rather than embedding an unverifiable positive claim.

- [ ] **Step 2: Write the integration test**

Create a test marked `integration` that uses:

```python
factory = get_contract_factory(contract_file_path=CONTRACT)
deploy_tx = factory.deploy_contract_tx(
    args=[],
    wait_transaction_status=TransactionStatus.FINALIZED,
)
assert deploy_tx["status"] == TransactionStatus.FINALIZED
assert tx_execution_succeeded(deploy_tx)
contract = factory.build_contract(deploy_tx["data"]["contract_address"])
```

Open a case from the default account, resolve it from a second unrelated account, wait each write to `FINALIZED`, require `tx_execution_succeeded`, read the effective state, and send a repeated resolution expected to fail without changing readback. Gate live web execution behind `RUN_STUDIONET=1`; controlled local integration uses validator/web mocks where supported.

- [ ] **Step 3: Run integration collection and direct regression**

```powershell
python -m pytest tests/integration --collect-only -q
python -m pytest tests/direct -q
```

Expected: integration tests collect; direct tests still pass. If a local GenLayer network is available, also run `gltest tests/integration -v --network localnet` and record the result without treating its absence as Studionet evidence.

- [ ] **Step 4: Commit integration coverage**

```powershell
git add tests/integration samples pyproject.toml gltest.config.yaml
git commit -m "test: add GenLayer recall integration flow"
```

### Task 7: Deployment runner and manifest integrity

**Files:**
- Create: `deploy/run_studionet.py`
- Create: `deployments/manifest.schema.json`
- Create: `tests/test_deployment_runner.py`

**Interfaces:**
- Consumes: GenLayer CLI `0.39.2`, tested contract source, safe environment variables, and confirmed active wallet/network.
- Produces: preflight report, submitted hashes, finalized receipts, readbacks, deployed code comparison, and `deployments/studionet.json` only after verification.

- [ ] **Step 1: Write failing runner unit tests**

Mock command execution and assert the runner:

```python
def test_manifest_not_written_when_receipt_is_not_finalized(tmp_path, fake_cli, deployment_request):
    fake_cli.receipt = {"status": "ACCEPTED"}
    with pytest.raises(RuntimeError, match="FINALIZED"):
        run_verified_deployment(deployment_request, cli=fake_cli, output_dir=tmp_path)
    assert not (tmp_path / "studionet.json").exists()


def test_manifest_not_written_when_execution_rolls_back(tmp_path, fake_cli, deployment_request):
    fake_cli.receipt = finalized_receipt(execution_result="ROLLBACK")
    with pytest.raises(RuntimeError, match="SUCCESS"):
        run_verified_deployment(deployment_request, cli=fake_cli, output_dir=tmp_path)
    assert not (tmp_path / "studionet.json").exists()


def test_manifest_requires_deployed_source_hash_match(tmp_path, fake_cli, deployment_request):
    fake_cli.receipt = finalized_receipt(execution_result="SUCCESS")
    fake_cli.deployed_code = "different source"
    with pytest.raises(RuntimeError, match="source hash"):
        run_verified_deployment(deployment_request, cli=fake_cli, output_dir=tmp_path)
    assert not (tmp_path / "studionet.json").exists()
```

Also test secret redaction, exact chain ID `61999`, exact wallet confirmation flag, transaction-hash parsing, and atomic manifest replacement.

- [ ] **Step 2: Run runner tests and observe failure**

```powershell
python -m pytest tests/test_deployment_runner.py -q
```

Expected: module import failure before the runner exists.

- [ ] **Step 3: Implement safe preflight and execution**

Use `subprocess.run` with argument arrays, never shell strings. Preflight executes read-only `genlayer config get`, `genlayer account`, `git config --get user.name`, `git config --get user.email`, `git remote -v`, and `gh auth status` when available. It prints the network, chain ID, wallet address, contract source path/hash, and exact planned actions, then exits unless `--confirmed-wallet <address>` exactly matches the active wallet.

After confirmation, execute:

```text
genlayer deploy --contract contracts/fda_recall_applicability_registry.py
genlayer receipt <deployTx> --status FINALIZED
genlayer write <address> open_case --args <six exact args>
genlayer receipt <openTx> --status FINALIZED
genlayer write <address> resolve_case --args <caseId>
genlayer receipt <resolveTx> --status FINALIZED
genlayer call <address> read_effective_status --args <caseId>
genlayer code <address>
```

Require leader `execution_result == "SUCCESS"` for deployment/open/resolve, canonicalize receipt/readback JSON, compare SHA-256 of retrieved deployed code with the local source bytes, and atomically write the manifest only after every check passes.

- [ ] **Step 4: Validate manifest schema and tests**

The schema requires network, chain ID, deployer, contract address, commit, source hash, deploy/open/resolve transaction hashes, `FINALIZED` statuses, `SUCCESS` execution results, readback, explorer links, CLI/tool versions, and generated timestamp. Run:

```powershell
python -m ruff check deploy tests/test_deployment_runner.py
python -m pytest tests/test_deployment_runner.py -q
```

Expected: all runner tests pass with no real network mutation.

- [ ] **Step 5: Commit deployment automation**

```powershell
git add deploy deployments/manifest.schema.json tests/test_deployment_runner.py
git commit -m "feat: add verified Studionet deployment runner"
```

### Task 8: Documentation, recovery, and fixed verification format

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/consensus.md`
- Create: `docs/security.md`
- Create: `docs/recovery.md`
- Create: `verification/proof-matrix.md`
- Create: `verification/test-summary.schema.json`

**Interfaces:**
- Consumes: exact implemented schema, commands, tests, frozen classification, and deployment evidence fields.
- Produces: reproducible operator/user documentation with no unsupported live claim.

- [ ] **Step 1: Write docs against the actual public methods**

README must contain the trust problem, exact GenLayer decision, on-chain consequence, source/freshness/failure policy, state machine, method signatures, setup, lint, direct test, integration test, preflight, deploy, sample workflow, readback, frozen migration, source verification, security, and limitations. Before live deployment, label every address/transaction/evidence field `Not deployed yet` rather than using placeholders that resemble real values.

- [ ] **Step 2: Write focused design docs and recovery runbook**

`docs/consensus.md` maps each stored decision field to source, downstream effect, validator check, comparison rule, and differential test. `docs/security.md` includes prompt injection, source outage, stale data, replay, malicious registrar, validator dissent, and physical-identity limitations. `docs/recovery.md` gives the six frozen migration steps from the approved design and explicitly states that there is no privileged recovery or fund custody.

- [ ] **Step 3: Create evidence schemas without fabricated results**

The proof matrix header is:

```markdown
| Actor | Action | Contract method | Transaction hash | FINALIZED/SUCCESS | Readback | Source/test |
|---|---|---|---|---|---|---|
```

Until deployment, include only local-test rows and a clear incomplete deployment gate. The test-summary schema requires command, exit code, UTC time, tool version, commit, and contract source hash.

- [ ] **Step 4: Check docs, links, and secrets**

```powershell
python -m ruff check .
git diff --check
rg -n "PRIVATE_KEY|MNEMONIC|API_KEY=.+|BEGIN PRIVATE|0x[0-9a-fA-F]{64}" --glob '!work/**' --glob '!docs/superpowers/**' .
```

Expected: formatting checks pass; the secret scan reports no credential values. Transaction hashes are allowed only after verified deployment and must be reviewed manually.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md docs verification/proof-matrix.md verification/test-summary.schema.json
git commit -m "docs: document recall registry operation and recovery"
```

### Task 9: Full local verification and deployment confirmation gate

**Files:**
- Create after successful commands: `verification/test-summary.json`
- Modify only if tests expose defects: contract, tests, scripts, or docs tied to the defect

**Interfaces:**
- Consumes: all source, tests, scripts, and documentation.
- Produces: a clean local evidence package and an exact user confirmation request; no live mutation.

- [ ] **Step 1: Install the pinned environment**

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --requirement requirements.txt
```

Record versions using the virtual-environment Python. Do not print environment variables.

- [ ] **Step 2: Run the complete local quality gate**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest -m "not integration and not studionet" -q
.\.venv\Scripts\python -m pytest tests/integration --collect-only -q
git diff --check
```

If any check fails, add a regression test where applicable, make the minimum fix, rerun the focused test, then rerun this entire gate.

- [ ] **Step 3: Produce the local verification record**

Calculate the exact contract SHA-256 and Git commit, then write `verification/test-summary.json` only from successful command results. Validate it against the schema and ensure the working tree contains no accidental secrets, caches, `work/`, or environment files.

- [ ] **Step 4: Inspect external identity context read-only**

Run the deployment runner without `--confirmed-wallet`. Capture only safe outputs: active network name, chain ID, wallet address, Git author, GitHub CLI account if configured, repository remote if configured, contract source hash, and exact proposed deploy/open/resolve actions.

- [ ] **Step 5: Stop and ask the user for deployment confirmation**

Report the exact wallet address, Studionet chain ID `61999`, source SHA-256, and actions. Ask the user to confirm that exact wallet and action set. Do not deploy, write, push, or create any external resource before the confirmation.

- [ ] **Step 6: Commit the verified local evidence**

```powershell
git add verification/test-summary.json
git commit -m "test: record verified local quality gate"
```

If committing changes the commit recorded inside the summary, record both `tested_commit` and `evidence_commit`; do not rewrite history merely to make a self-referential hash.

### Task 10: Confirmed Studionet deployment, sample workflow, and final proof

**Files:**
- Generate: `deployments/studionet.json`
- Modify: `README.md`
- Modify: `verification/proof-matrix.md`
- Modify: `verification/test-summary.json` only to add the final source/evidence commit relationship without changing past command results

**Interfaces:**
- Consumes: the user's exact wallet/action confirmation from Task 9 and the locally verified commit/source.
- Produces: verified contract address, deploy/sample transaction hashes, explorer links, finalized successful receipts, readback, deployed-source match, and known limitations.

- [ ] **Step 1: Recheck confirmation context immediately before mutation**

Run preflight again and compare active wallet, network, chain ID, Git commit, and source hash to the confirmed values. If any differs, stop and request new confirmation.

- [ ] **Step 2: Deploy exact tested source and wait for finality**

Run `deploy/run_studionet.py --confirmed-wallet <confirmed-address>` with the selected real recall and canonical sample subject. The runner must block until deployment reaches `FINALIZED`, require leader execution `SUCCESS`, and read the deployed contract address.

- [ ] **Step 3: Execute the complete sample transaction flow**

Open the immutable case, wait for `FINALIZED/SUCCESS`, call permissionless `resolve_case`, wait for `FINALIZED/SUCCESS`, then call `read_case`, `read_assessment`, and `read_effective_status`. Preserve the actual verdict, including `UNRESOLVED`; never substitute an expected favorable verdict.

- [ ] **Step 4: Verify deployed source**

Retrieve code using `genlayer code <address>`, hash the exact returned source bytes using the runner's normalized retrieval contract, and require equality with the delivered source SHA-256. Also inspect schema to confirm no privileged upgrade/admin method exists.

- [ ] **Step 5: Complete manifest and proof matrix**

Record deploy/open/resolve transaction hashes, explorer URLs, `FINALIZED` statuses, `SUCCESS` execution results, source hash, readbacks, wallet, network, chain ID, Git commits, test results, and actual limitations. Each material claim receives a proof-matrix row.

- [ ] **Step 6: Run final regression and hygiene gate**

```powershell
genvm-lint check contracts/fda_recall_applicability_registry.py
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest -q
git diff --check
git status --short
```

Review tracked and untracked files manually. Do not add `.env`, caches, raw CLI logs, or `work/`.

- [ ] **Step 7: Commit the fixed evidence package**

```powershell
git add deployments/studionet.json README.md verification/proof-matrix.md verification/test-summary.json
git commit -m "docs: publish verified Studionet evidence"
```

- [ ] **Step 8: Final handoff**

Report the exact source commit and hash, contract address, deployment transaction and explorer link, sample transaction hash, final receipt/execution states, readback, lint/direct/integration results, README path, proof matrix, and remaining limitations. Claim completion only if every mandatory item is present and verified.

## Plan Self-Review Record

- Spec coverage: trust matrix, decision, consequence, source/subject/time/freshness binding, semantic Equivalence Principle, fail-closed consensus, lifecycle, permissionless actions, replay, frozen recovery, no custody, direct/integration tests, deployment stop, finality, readback, source verification, README, manifest, and proof matrix all map to Tasks 1–10.
- Placeholder scan: the plan contains no deferred implementation marker; pre-deployment evidence uses explicit `Not deployed yet` wording, not fake addresses or hashes.
- Type and name consistency: public methods and verdict/state names are fixed in Tasks 1–10; timing and mask constants match the approved design.
- Scope check: one contract and one primary FDA applicability workflow; no independent frontend, backend, financial, multi-regulator, or arbitrary-search subsystem is introduced.
