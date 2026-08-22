# { "Seq": [{ "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }] }
from genlayer import *

import hashlib
import json
from datetime import datetime, timezone


SCHEMA_VERSION = "openfda-enforcement-v1"
RESOLUTION_WINDOW_SECONDS = 172800
PRODUCT_TYPES = ("food", "drug", "device")
DATE_TYPES = ("manufacture", "best_by", "expiry", "purchase", "unknown")
SUBJECT_KEYS = (
    "date_type",
    "date_value",
    "lot_or_code",
    "manufacturer",
    "model_or_sku",
    "product_name",
    "territory",
)


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_identifier(value: str, max_length: int, punctuation: str) -> bool:
    if len(value) == 0 or len(value) > max_length:
        return False
    return all(character.isalnum() or character in punctuation for character in value)


def _canonical_subject(subject_json: str) -> tuple[str, str]:
    if len(subject_json) == 0 or len(subject_json) > 4096:
        raise gl.vm.UserError("Invalid subject length")
    try:
        subject = json.loads(subject_json)
    except Exception:
        raise gl.vm.UserError("Subject must be canonical JSON") from None
    if not isinstance(subject, dict) or tuple(sorted(subject.keys())) != tuple(sorted(SUBJECT_KEYS)):
        raise gl.vm.UserError("Invalid subject keys")
    canonical = _canonical_json(subject)
    if canonical != subject_json:
        raise gl.vm.UserError("Subject must be canonical JSON")
    for key in SUBJECT_KEYS:
        if not isinstance(subject[key], str) or len(subject[key]) > 512:
            raise gl.vm.UserError("Invalid subject field")
    if subject["date_type"] not in DATE_TYPES:
        raise gl.vm.UserError("Invalid date type")
    date_value = subject["date_value"]
    if subject["date_type"] == "unknown":
        if date_value != "":
            raise gl.vm.UserError("Unknown date must be empty")
    else:
        if date_value == "":
            raise gl.vm.UserError("Known date requires value")
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except Exception:
            raise gl.vm.UserError("Invalid date value") from None
    return canonical, _sha256(canonical)


class FdaRecallApplicabilityRegistry(gl.Contract):
    cases: TreeMap[str, str]
    assessments: TreeMap[str, str]

    def __init__(self):
        self.cases = TreeMap()
        self.assessments = TreeMap()

    @gl.public.write
    def open_case(
        self,
        case_id: str,
        product_type: str,
        recall_number: str,
        subject_json: str,
        predecessor_contract: str,
        predecessor_case_id: str,
    ):
        if not _valid_identifier(case_id, 64, "-_.:"):
            raise gl.vm.UserError("Invalid case id")
        if case_id in self.cases:
            raise gl.vm.UserError("Case already exists")
        if product_type not in PRODUCT_TYPES:
            raise gl.vm.UserError("Invalid product type")
        if not _valid_identifier(recall_number, 64, "-"):
            raise gl.vm.UserError("Invalid recall number")
        canonical_subject, subject_hash = _canonical_subject(subject_json)
        created_at = int(datetime.now(timezone.utc).timestamp())
        registrar = str(gl.message.sender_address)
        replay_domain = _sha256(
            "|".join(
                (
                    SCHEMA_VERSION,
                    str(gl.message.chain_id),
                    str(gl.message.contract_address),
                    case_id,
                    registrar,
                    product_type,
                    recall_number,
                    subject_hash,
                    predecessor_contract,
                    predecessor_case_id,
                )
            )
        )
        self.cases[case_id] = _canonical_json(
            {
                "state": "PENDING",
                "product_type": product_type,
                "recall_number": recall_number,
                "subject": canonical_subject,
                "subject_hash": subject_hash,
                "registrar": registrar,
                "created_at": created_at,
                "resolution_deadline": created_at + RESOLUTION_WINDOW_SECONDS,
                "predecessor_contract": predecessor_contract,
                "predecessor_case_id": predecessor_case_id,
                "replay_domain": replay_domain,
                "closed_at": 0,
            }
        )

    @gl.public.write
    def close_unresolved(self, case_id: str):
        case = self._case(case_id)
        if case["state"] != "PENDING":
            raise gl.vm.UserError("Case is terminal")
        now = int(datetime.now(timezone.utc).timestamp())
        if now < case["resolution_deadline"]:
            raise gl.vm.UserError("Resolution deadline not reached")
        case["state"] = "CLOSED_UNRESOLVED"
        case["closed_at"] = now
        self._store_case(case_id, case)

    @gl.public.view
    def read_case(self, case_id: str) -> tuple[str, str, str, str, str, u64, u64, str]:
        case = self._case(case_id)
        return (
            case["state"],
            case["product_type"],
            case["recall_number"],
            case["subject_hash"],
            case["registrar"],
            case["created_at"],
            case["resolution_deadline"],
            case["replay_domain"],
        )

    @gl.public.view
    def read_assessment(self, case_id: str) -> tuple[str, u32, u32, u32, str, str, u64, u64, str]:
        self._case(case_id)
        assessment = self._assessment(case_id)
        return (
            assessment["verdict"],
            assessment["match_mask"],
            assessment["conflict_mask"],
            assessment["unavailable_mask"],
            assessment["source_hash"],
            assessment["source_last_updated"],
            assessment["assessed_at"],
            assessment["valid_until"],
            assessment["assessment_hash"],
        )

    @gl.public.view
    def read_effective_status(self, case_id: str) -> tuple[str, str, u64]:
        case = self._case(case_id)
        if case["state"] == "PENDING":
            return "UNRESOLVED", "PENDING", 0
        if case["state"] == "CLOSED_UNRESOLVED":
            return "UNRESOLVED", "CLOSED", 0
        assessment = self._assessment(case_id)
        now = int(datetime.now(timezone.utc).timestamp())
        if now > assessment["valid_until"]:
            return "UNRESOLVED", "STALE", assessment["valid_until"]
        return assessment["verdict"], "CURRENT", assessment["valid_until"]

    def _case(self, case_id: str):
        if case_id not in self.cases:
            raise gl.vm.UserError("Unknown case")
        return json.loads(self.cases[case_id])

    def _assessment(self, case_id: str):
        if case_id not in self.assessments:
            raise gl.vm.UserError("Assessment unavailable")
        return json.loads(self.assessments[case_id])

    def _store_case(self, case_id: str, case) -> None:
        self.cases[case_id] = _canonical_json(case)
