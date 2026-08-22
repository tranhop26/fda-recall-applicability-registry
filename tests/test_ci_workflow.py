from pathlib import Path

WORKFLOW = Path(".github/workflows/ci.yml")


def test_ci_is_secret_free_and_covers_required_quality_gates():
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "permissions:\n  contents: read",
        "python-version: '3.12'",
        "python -m pip check",
        "genvm-lint check contracts/fda_recall_applicability_registry.py",
        "python -m ruff format --check .",
        "python -m ruff check .",
        'python -m pytest -m "not integration and not studionet" -q',
        "python -m pytest tests/integration --collect-only -q",
        "python -m jsonschema -i deployments/studionet.json deployments/manifest.schema.json",
        "python -m jsonschema -i verification/test-summary.json verification/test-summary.schema.json",
    )
    for token in required:
        assert token in text
    lowered = text.lower()
    for forbidden in ("private_key", "mnemonic", "run_studionet=1", "gh release", "genlayer deploy"):
        assert forbidden not in lowered
