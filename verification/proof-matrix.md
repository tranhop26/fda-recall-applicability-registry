# Proof matrix

Live deployment was executed from the confirmed Chrome wallet in Normal (Full Consensus) mode. Receipt status and execution results were independently read back with GenLayer CLI 0.39.2.

Proof boundary: `AFFECTED`, stale-source `UNRESOLVED`, and replay rejection are live only where a finalized receipt and readback are listed below. `CLOSED_UNRESOLVED` and `NOT_AFFECTED` remain test-only. No live `NOT_AFFECTED` claim is made from stale FDA metadata.

| Actor | Action | Contract method | Transaction hash | FINALIZED/SUCCESS | Readback | Source/test |
|---|---|---|---|---|---|---|
| Test-only: direct registrar | Open canonical immutable case | `open_case` | Local direct execution | N/A / pass | `PENDING`, hashes and replay domain | `tests/direct/test_input_and_lifecycle.py` |
| Test-only: direct unrelated caller | Resolve and validator-check semantic evidence | `resolve_case` | Local direct execution | N/A / pass | Verdict, masks, evidence hash/date | `tests/direct/test_evidence_and_consensus.py` |
| Test-only: direct unrelated caller | Close after deadline | `close_unresolved` | Local direct execution | N/A / pass | `CLOSED_UNRESOLVED` | `tests/direct/test_input_and_lifecycle.py` |
| Test-only: deployment runner fake CLI | Reject non-final, rollback, mismatch, and secret output | Deploy/open/resolve/read | Simulated | Required by tests | Manifest written only after all gates | `tests/test_deployment_runner.py` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Deploy tested source | Constructor | `0xe1929472…80d018` | `FINALIZED` / leader `SUCCESS`; majority agree | Contract `0xbF3e…5f4e`; exact source hash match | `deployments/studionet.json` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Register immutable FDA sample | `open_case` | `0x1f22e8b2…b7b721` | `FINALIZED` / leader `SUCCESS`; majority agree | `DECIDED` after resolution; registrar and subject hash match | `deployments/studionet.json` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Resolve with FDA web evidence, LLM classification, and validator equivalence | `resolve_case` | `0xf564b66e…c641b9` | `FINALIZED` / leader `SUCCESS`; majority agree | `AFFECTED`, masks `31/0/0`, source date `2026-08-12`, effective `CURRENT` | `deployments/studionet.json` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Reject replay of already-decided case | `resolve_case` | `0x91827114…ecf331` | `FINALIZED` / `ERROR` | Original `DECIDED` case readback unchanged | `deployments/studionet.json` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Register stale-source safety sample | `open_case` | `0x1101fd32…4b384` | `FINALIZED` / `SUCCESS` | `PENDING`; subject SHA-256 `6e33240a…1fa33b` | `deployments/studionet.json` |
| Confirmed Studionet wallet `0x21b4…2eC7` | Resolve invalid or insufficient FDA source fail-closed | `resolve_case` | `0xeb81838c…404a31` | `FINALIZED` / `SUCCESS`; majority agree | `DECIDED`, assessment `UNRESOLVED`, masks `0/0/31`, effective `CURRENT`; independent post-finalization observation found FDA metadata stale, but the receipt does not uniquely bind that response | `deployments/studionet.json` |
| Read-only verifier | Retrieve deployed code and public schema | `code`, `schema` | N/A | CLI success | Remote/local canonical SHA-256 both `49e58dc6…21cfe`; exactly 7 expected public methods | `deployments/studionet.json` |
