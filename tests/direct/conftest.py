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
