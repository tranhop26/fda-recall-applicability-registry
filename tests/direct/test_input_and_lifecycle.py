import hashlib
import json

import pytest
from conftest import (
    CONTRACT,
    SDK_VERSION,
    mock_fda_payload,
    mock_semantic_result,
    semantic_result,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def open_pending(direct_vm, direct_deploy, canonical_subject):
    direct_vm.warp("2026-08-22T00:00:00+00:00")
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")
    return contract


def test_open_case_stores_canonical_subject(direct_deploy, canonical_subject):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")

    case = contract.read_case("case-1")
    assert case[0] == "PENDING"
    assert case[1] == "food"
    assert case[2] == "F-1000-2026"
    assert case[3] == hashlib.sha256(canonical_subject.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("product_type", ["cosmetic", "FOOD", "", "food/../drug"])
def test_open_case_rejects_invalid_product_type(direct_deploy, canonical_subject, product_type):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    with pytest.raises(Exception, match="Invalid product type"):
        contract.open_case("case-1", product_type, "F-1000-2026", canonical_subject, "", "")


def test_open_case_rejects_noncanonical_subject(direct_deploy, pretty_subject):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    with pytest.raises(Exception, match="canonical JSON"):
        contract.open_case("case-1", "food", "F-1000-2026", pretty_subject, "", "")


def test_open_case_rejects_duplicate_case_id(direct_deploy, canonical_subject):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")

    with pytest.raises(Exception, match="Case already exists"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical_subject, "", "")


@pytest.mark.parametrize("case_id", ["", "x" * 65, "bad case", "case/1"])
def test_open_case_rejects_invalid_case_id(direct_deploy, canonical_subject, case_id):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    with pytest.raises(Exception, match="Invalid case id"):
        contract.open_case(case_id, "food", "F-1000-2026", canonical_subject, "", "")


@pytest.mark.parametrize("recall_number", ["", "x" * 65, "F 1000", 'F-1000"', "../F-1000"])
def test_open_case_rejects_invalid_recall_number(direct_deploy, canonical_subject, recall_number):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    with pytest.raises(Exception, match="Invalid recall number"):
        contract.open_case("case-1", "food", recall_number, canonical_subject, "", "")


def test_open_case_rejects_subject_with_missing_key(direct_deploy, subject_data):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    del subject_data["territory"]

    with pytest.raises(Exception, match="Invalid subject keys"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


def test_open_case_rejects_subject_with_extra_key(direct_deploy, subject_data):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["verdict"] = "AFFECTED"

    with pytest.raises(Exception, match="Invalid subject keys"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


def test_open_case_rejects_non_string_subject_field(direct_deploy, subject_data):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["manufacturer"] = 42

    with pytest.raises(Exception, match="Invalid subject field"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


@pytest.mark.parametrize("date_type", ["sell_by", "BEST_BY", ""])
def test_open_case_rejects_invalid_date_type(direct_deploy, subject_data, date_type):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["date_type"] = date_type

    with pytest.raises(Exception, match="Invalid date type"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


@pytest.mark.parametrize("date_value", ["2026/09/01", "2026-02-30", "01-09-2026"])
def test_open_case_rejects_invalid_date_value(direct_deploy, subject_data, date_value):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["date_value"] = date_value

    with pytest.raises(Exception, match="Invalid date value"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


def test_unknown_date_requires_empty_value(direct_deploy, subject_data):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["date_type"] = "unknown"

    with pytest.raises(Exception, match="Unknown date must be empty"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


def test_known_date_requires_value(direct_deploy, subject_data):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    subject_data["date_value"] = ""

    with pytest.raises(Exception, match="Known date requires value"):
        contract.open_case("case-1", "food", "F-1000-2026", canonical(subject_data), "", "")


def test_pending_effective_status_is_unresolved(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    assert contract.read_effective_status("case-1") == ("UNRESOLVED", "PENDING", 0)


def test_unrelated_address_closes_after_deadline(direct_vm, direct_deploy, direct_bob, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-24T00:00:00+00:00")

    with direct_vm.prank(direct_bob):
        contract.close_unresolved("case-1")

    assert contract.read_case("case-1")[0] == "CLOSED_UNRESOLVED"
    assert contract.read_effective_status("case-1") == ("UNRESOLVED", "CLOSED", 0)


def test_close_before_deadline_is_rejected_without_mutation(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-23T23:59:59+00:00")

    with pytest.raises(Exception, match="Resolution deadline not reached"):
        contract.close_unresolved("case-1")

    assert contract.read_case("case-1")[0] == "PENDING"


def test_closed_case_cannot_be_closed_twice(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-24T00:00:00+00:00")
    contract.close_unresolved("case-1")

    with pytest.raises(Exception, match="Case is terminal"):
        contract.close_unresolved("case-1")


def test_assessment_read_is_unavailable_before_decision(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    with pytest.raises(Exception, match="Assessment unavailable"):
        contract.read_assessment("case-1")


@pytest.mark.parametrize("method_name", ["read_case", "read_effective_status", "read_assessment"])
def test_unknown_case_reads_are_rejected(direct_deploy, method_name):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

    with pytest.raises(Exception, match="Unknown case"):
        getattr(contract, method_name)("missing")


def resolve_affected(direct_vm, contract, fda_payload):
    mock_fda_payload(direct_vm, fda_payload)
    mock_semantic_result(direct_vm, semantic_result())
    contract.resolve_case("case-1")


def current_contract_address(direct_vm):
    return "0x" + direct_vm._contract_address.hex()


def test_effective_status_fails_closed_after_expiry_but_history_remains(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    resolve_affected(direct_vm, contract, fda_payload)
    historical = contract.read_assessment("case-1")
    direct_vm.warp("2026-09-02T00:00:01+00:00")

    assert contract.read_assessment("case-1") == historical
    assert contract.read_effective_status("case-1") == ("UNRESOLVED", "STALE", historical[7])


def test_decided_case_rejects_repeated_resolution_without_mutation(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    resolve_affected(direct_vm, contract, fda_payload)
    before = contract.read_assessment("case-1")

    with pytest.raises(Exception, match="Case is terminal"):
        contract.resolve_case("case-1")

    assert contract.read_assessment("case-1") == before


def test_resolve_at_deadline_is_rejected(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-24T00:00:00+00:00")

    with pytest.raises(Exception, match="Resolution deadline passed"):
        contract.resolve_case("case-1")

    assert contract.read_case("case-1")[0] == "PENDING"


def test_closed_case_rejects_resolution(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-24T00:00:00+00:00")
    contract.close_unresolved("case-1")

    with pytest.raises(Exception, match="Case is terminal"):
        contract.resolve_case("case-1")


def test_refresh_requires_both_predecessor_fields(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)

    with pytest.raises(Exception, match="Invalid predecessor"):
        contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, "", "case-1")
    with pytest.raises(Exception, match="Invalid predecessor"):
        contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, current_contract_address(direct_vm), "")


def test_refresh_requires_local_terminal_predecessor(direct_vm, direct_deploy, canonical_subject):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    address = current_contract_address(direct_vm)

    with pytest.raises(Exception, match="Predecessor must be local"):
        contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, "0x" + "11" * 20, "case-1")
    with pytest.raises(Exception, match="Predecessor is not terminal"):
        contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, address, "case-1")
    with pytest.raises(Exception, match="Unknown predecessor"):
        contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, address, "missing")


@pytest.mark.parametrize(
    ("product_type", "recall_number", "subject_change"),
    [
        ("drug", "F-1000-2026", None),
        ("food", "F-1001-2026", None),
        ("food", "F-1000-2026", ("lot_or_code", "LOT-99")),
    ],
)
def test_refresh_requires_same_source_and_subject(
    direct_vm,
    direct_deploy,
    canonical_subject,
    subject_data,
    product_type,
    recall_number,
    subject_change,
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    direct_vm.warp("2026-08-24T00:00:00+00:00")
    contract.close_unresolved("case-1")
    if subject_change is not None:
        subject_data[subject_change[0]] = subject_change[1]
    refresh_subject = canonical(subject_data)

    with pytest.raises(Exception, match="Predecessor identity mismatch"):
        contract.open_case(
            "case-2",
            product_type,
            recall_number,
            refresh_subject,
            current_contract_address(direct_vm),
            "case-1",
        )


def test_valid_refresh_preserves_predecessor_and_records_lineage(
    direct_vm, direct_deploy, canonical_subject, fda_payload
):
    contract = open_pending(direct_vm, direct_deploy, canonical_subject)
    resolve_affected(direct_vm, contract, fda_payload)
    predecessor_case = contract.read_case("case-1")
    predecessor_assessment = contract.read_assessment("case-1")
    address = current_contract_address(direct_vm)

    contract.open_case("case-2", "food", "F-1000-2026", canonical_subject, address, "case-1")

    assert contract.read_predecessor("case-2") == (address, "case-1")
    assert contract.read_case("case-1") == predecessor_case
    assert contract.read_assessment("case-1") == predecessor_assessment
    assert contract.read_case("case-2")[0] == "PENDING"
    assert contract.read_case("case-2")[7] != predecessor_case[7]


def test_contract_has_no_privileged_or_upgrade_entrypoints(direct_deploy):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    forbidden = ("upgrade", "admin", "override", "force", "pause", "set_source")
    instance = object.__getattribute__(contract, "_instance")
    public_methods = {
        name for name, value in instance.__class__.__dict__.items() if not name.startswith("_") and callable(value)
    }

    assert public_methods == {
        "close_unresolved",
        "open_case",
        "read_assessment",
        "read_case",
        "read_effective_status",
        "read_predecessor",
        "resolve_case",
    }
    assert not any(token in name.lower() for name in public_methods for token in forbidden)
