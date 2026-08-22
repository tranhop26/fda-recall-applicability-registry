import copy
import json

import pytest
from conftest import (
    CONTRACT,
    FDA_URL_PATTERN,
    SDK_VERSION,
    mock_fda_payload,
    mock_semantic_result,
    semantic_result,
)


def open_pending(direct_vm, direct_deploy, canonical_subject):
    direct_vm.warp("2026-08-22T12:00:00+00:00")
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")
    return contract


def resolve_with(direct_vm, contract, fda_payload, semantic):
    direct_vm.strict_mocks = True
    direct_vm.check_pickling = True
    mock_fda_payload(direct_vm, fda_payload)
    mock_semantic_result(direct_vm, semantic)
    contract.resolve_case("case-1")


def test_complete_semantic_match_is_affected(direct_vm, direct_deploy, canonical_subject, fda_payload):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    resolve_with(direct_vm, contract, fda_payload, semantic_result())

    assessment = contract.read_assessment("case-1")
    assert assessment[0:4] == ("AFFECTED", 31, 0, 0)
    assert assessment[5] == "2026-08-18"
    assert contract.read_effective_status("case-1")[0:2] == ("AFFECTED", "CURRENT")


def test_explicit_dimension_conflict_is_not_affected(direct_vm, direct_deploy, canonical_subject, fda_payload):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    resolve_with(direct_vm, contract, fda_payload, semantic_result(lot_or_code="CONFLICT"))

    assert contract.read_assessment("case-1")[0:4] == ("NOT_AFFECTED", 27, 4, 0)


def test_unavailable_dimension_is_unresolved(direct_vm, direct_deploy, canonical_subject, fda_payload):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    resolve_with(direct_vm, contract, fda_payload, semantic_result(relevant_date="UNAVAILABLE"))

    assert contract.read_assessment("case-1")[0:4] == ("UNRESOLVED", 15, 0, 16)


def test_http_failure_is_stored_as_unresolved(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.strict_mocks = True
    direct_vm.mock_web(FDA_URL_PATTERN, {"status": 503, "body": "service unavailable"})

    contract.resolve_case("case-1")

    assert contract.read_assessment("case-1")[0:4] == ("UNRESOLVED", 0, 0, 31)


@pytest.mark.parametrize(
    "last_updated",
    ["2026-08-01", "2026-08-24", "not-a-date"],
)
def test_stale_future_or_malformed_source_is_unresolved(
    direct_vm, direct_deploy, canonical_subject, fda_payload, last_updated
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    fda_payload["meta"]["last_updated"] = last_updated
    direct_vm.strict_mocks = True
    mock_fda_payload(direct_vm, fda_payload)

    contract.resolve_case("case-1")

    assert contract.read_assessment("case-1")[0:4] == ("UNRESOLVED", 0, 0, 31)


def malformed_payloads(fda_payload):
    wrong_recall = copy.deepcopy(fda_payload)
    wrong_recall["results"][0]["recall_number"] = "F-9999-2026"
    duplicate = copy.deepcopy(fda_payload)
    duplicate["results"].append(copy.deepcopy(duplicate["results"][0]))
    missing_field = copy.deepcopy(fda_payload)
    del missing_field["results"][0]["code_info"]
    return [[], {"meta": fda_payload["meta"], "results": []}, wrong_recall, duplicate, missing_field]


def test_malformed_or_mismatched_records_are_unresolved(direct_vm, direct_deploy, canonical_subject, fda_payload):
    for index, payload in enumerate(malformed_payloads(fda_payload)):
        direct_vm.clear_mocks()
        contract = open_pending(direct_vm, direct_deploy, canonical_subject)
        direct_vm.strict_mocks = True
        mock_fda_payload(direct_vm, payload)
        contract.resolve_case("case-1")
        assert contract.read_assessment("case-1")[0:4] == ("UNRESOLVED", 0, 0, 31), index


def test_malformed_model_output_fails_closed(direct_vm, direct_deploy, canonical_subject, fda_payload):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.strict_mocks = True
    mock_fda_payload(direct_vm, fda_payload)
    mock_semantic_result(direct_vm, json.dumps({"manufacturer": True}))

    contract.resolve_case("case-1")

    assert contract.read_assessment("case-1")[0:4] == ("UNRESOLVED", 0, 0, 31)


def test_validator_ignores_reasoning_wording_when_meaning_matches(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    resolve_with(direct_vm, contract, fda_payload, semantic_result(reason="leader wording"))
    direct_vm.clear_mocks()
    mock_fda_payload(direct_vm, fda_payload)
    mock_semantic_result(direct_vm, semantic_result(reason="validator wording"))

    assert direct_vm.run_validator() is True


def test_validator_rejects_changed_business_meaning(direct_vm, direct_deploy, canonical_subject, fda_payload):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    resolve_with(direct_vm, contract, fda_payload, semantic_result())
    direct_vm.clear_mocks()
    mock_fda_payload(direct_vm, fda_payload)
    mock_semantic_result(direct_vm, semantic_result(lot_or_code="CONFLICT"))

    assert direct_vm.run_validator() is False
