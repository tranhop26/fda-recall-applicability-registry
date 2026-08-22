# GitHub CI design

## Goal

Give every push and pull request a reproducible, secret-free quality gate for the delivered GenLayer contract without deploying another contract or sending any Studionet transaction.

## Selected approach

Add one GitHub Actions workflow using Ubuntu and Python 3.12. Install the pinned `requirements.txt`, then run dependency validation, GenVM lint, Ruff format/check, all non-live pytest tests, integration-test collection, and JSON Schema validation for the test summary and verified deployment manifest.

The workflow must not load wallet credentials, call a write method, run the `studionet` marker, deploy, publish, or modify repository contents. The existing live manifest remains the evidence for the already completed browser deployment.

## Workflow

- Trigger on pushes to `master` and pull requests targeting `master`.
- Grant repository contents read-only permission.
- Check out the exact commit and install Python 3.12.
- Install the pinned dependencies from `requirements.txt`.
- Run `pip check` and GenVM lint with UTF-8 output enabled.
- Run Ruff format and lint checks.
- Run tests excluding `integration` and `studionet`; this includes direct contract and deployment-runner coverage.
- Collect the gated integration test to ensure it remains importable.
- Validate `verification/test-summary.json` and `deployments/studionet.json` against their schemas.

## Failure behavior

Any command failure makes the job fail. No retry hides deterministic failures. Network dependency-install failures may be retried by rerunning the workflow, but the workflow itself performs no write or fallback deployment.

## Verification

Before push, parse the YAML, rerun the equivalent local commands, and confirm no secret or write-capable step exists. After push, wait for the GitHub Actions run and require a successful conclusion before reporting completion.
