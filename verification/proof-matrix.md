# Proof matrix

Live deployment is incomplete until exact wallet confirmation and verified transactions are available.

| Actor | Action | Contract method | Transaction hash | FINALIZED/SUCCESS | Readback | Source/test |
|---|---|---|---|---|---|---|
| Direct test registrar | Open canonical immutable case | `open_case` | Local direct execution | N/A / pass | `PENDING`, hashes and replay domain | `tests/direct/test_input_and_lifecycle.py` |
| Direct test unrelated caller | Resolve and validator-check semantic evidence | `resolve_case` | Local direct execution | N/A / pass | Verdict, masks, evidence hash/date | `tests/direct/test_evidence_and_consensus.py` |
| Direct test unrelated caller | Close after deadline | `close_unresolved` | Local direct execution | N/A / pass | `CLOSED_UNRESOLVED` | `tests/direct/test_input_and_lifecycle.py` |
| Deployment runner fake CLI | Reject non-final, rollback, mismatch, and secret output | Deploy/open/resolve/read | Simulated | Required by tests | Manifest written only after all gates | `tests/test_deployment_runner.py` |
| Confirmed Studionet wallet | Deploy and complete sample workflow | All workflow methods | Not deployed yet | Not deployed yet | Not deployed yet | Confirmation gate pending |
