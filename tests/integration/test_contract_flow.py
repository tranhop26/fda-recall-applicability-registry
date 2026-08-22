import json
import os
from pathlib import Path

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded
from gltest.types import TransactionStatus

CONTRACT = Path("contracts/fda_recall_applicability_registry.py")
SUBJECT = Path("samples/subject-affected.json")
RECALL_NUMBER = "H-1223-2026"
CASE_ID = "studionet-h-1223-2026"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.studionet,
    pytest.mark.skipif(os.getenv("RUN_STUDIONET") != "1", reason="set RUN_STUDIONET=1 for live execution"),
]


def require_final_success(receipt):
    assert receipt["status"] == TransactionStatus.FINALIZED
    assert tx_execution_succeeded(receipt)


def test_studionet_deploy_consensus_readback_and_replay_rejection():
    accounts = get_accounts()
    assert len(accounts) >= 2, "integration flow requires two configured Studionet accounts"
    factory = get_contract_factory(contract_file_path=CONTRACT)
    deploy_receipt = factory.deploy_contract_tx(
        args=[],
        account=accounts[0],
        wait_transaction_status=TransactionStatus.FINALIZED,
    )
    require_final_success(deploy_receipt)
    contract_address = deploy_receipt["data"]["contract_address"]
    registrar_contract = factory.build_contract(contract_address, account=accounts[0])
    resolver_contract = registrar_contract.connect(accounts[1])
    subject = SUBJECT.read_text(encoding="utf-8").strip()
    assert json.dumps(json.loads(subject), sort_keys=True, separators=(",", ":")) == subject

    open_receipt = registrar_contract.open_case(args=[CASE_ID, "food", RECALL_NUMBER, subject, "", ""]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    require_final_success(open_receipt)

    resolve_receipt = resolver_contract.resolve_case(args=[CASE_ID]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    require_final_success(resolve_receipt)
    case_readback = registrar_contract.read_case(args=[CASE_ID]).call()
    assessment_readback = registrar_contract.read_assessment(args=[CASE_ID]).call()
    effective_readback = registrar_contract.read_effective_status(args=[CASE_ID]).call()
    assert case_readback[0] == "DECIDED"
    assert assessment_readback[0] in {"AFFECTED", "NOT_AFFECTED", "UNRESOLVED"}
    assert effective_readback[0] == assessment_readback[0]

    replay_receipt = resolver_contract.resolve_case(args=[CASE_ID]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    assert not tx_execution_succeeded(replay_receipt)
    assert registrar_contract.read_assessment(args=[CASE_ID]).call() == assessment_readback
