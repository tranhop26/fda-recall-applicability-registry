import json
import sys

import pytest
from gltest.direct.loader import deploy_contract

# Some globally installed tooling exposes an empty `genlayer` shim. Direct mode
# must import the contract SDK selected by the contract dependency header.
for module_name in tuple(sys.modules):
    if module_name == "genlayer" or module_name.startswith("genlayer."):
        del sys.modules[module_name]


CONTRACT = "contracts/fda_recall_applicability_registry.py"
SDK_VERSION = "v0.2.16"
FDA_URL_PATTERN = r"https://api[.]fda[.]gov/food/enforcement[.]json[?]search=recall_number:%22F-1000-2026%22&limit=2"


@pytest.fixture
def direct_deploy(direct_vm):
    def _deploy(contract_path, *args, sdk_version=None, **kwargs):
        for module_name in tuple(sys.modules):
            if module_name == "genlayer" or module_name.startswith("genlayer."):
                del sys.modules[module_name]
        return deploy_contract(contract_path, direct_vm, *args, sdk_version=sdk_version, **kwargs)

    return _deploy


@pytest.fixture
def subject_data():
    return {
        "date_type": "best_by",
        "date_value": "2026-09-01",
        "lot_or_code": "LOT-42",
        "manufacturer": "Acme Foods",
        "model_or_sku": "SKU-7",
        "product_name": "Roasted Almonds",
        "territory": "United States",
    }


@pytest.fixture
def canonical_subject(subject_data):
    return json.dumps(subject_data, sort_keys=True, separators=(",", ":"))


@pytest.fixture
def pretty_subject(subject_data):
    return json.dumps(subject_data, indent=2)


@pytest.fixture
def fda_payload():
    return {
        "meta": {
            "disclaimer": "openFDA public data",
            "last_updated": "2026-08-18",
            "license": "https://open.fda.gov/license/",
            "results": {"limit": 2, "skip": 0, "total": 1},
            "terms": "https://open.fda.gov/terms/",
        },
        "results": [
            {
                "classification": "Class I",
                "code_info": "LOT-42, best by 2026-09-01",
                "distribution_pattern": "United States nationwide",
                "product_description": "Acme Foods Roasted Almonds, SKU-7",
                "recall_initiation_date": "20260810",
                "recall_number": "F-1000-2026",
                "recalling_firm": "Acme Foods",
                "report_date": "20260818",
                "status": "Ongoing",
                "termination_date": "",
            }
        ],
    }


def mock_fda_payload(direct_vm, payload, status=200):
    direct_vm.mock_web(FDA_URL_PATTERN, {"status": status, "body": json.dumps(payload)})


def semantic_result(
    manufacturer="MATCH",
    product_identity="MATCH",
    lot_or_code="MATCH",
    territory="MATCH",
    relevant_date="MATCH",
    reason="bounded evidence supports the classifications",
):
    return json.dumps(
        {
            "lot_or_code": lot_or_code,
            "manufacturer": manufacturer,
            "product_identity": product_identity,
            "reason": reason,
            "relevant_date": relevant_date,
            "territory": territory,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def mock_semantic_result(direct_vm, result):
    direct_vm.mock_llm(r"FDA recall applicability evaluator", result)
