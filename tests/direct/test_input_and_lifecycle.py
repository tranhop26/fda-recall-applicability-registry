import hashlib
import json

import pytest
from conftest import CONTRACT, SDK_VERSION


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


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
