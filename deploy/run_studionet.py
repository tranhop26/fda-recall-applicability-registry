from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STUDIONET_CHAIN_ID = 61999
EXPLORER_BASE = "https://explorer-studio.genlayer.com"
TX_PATTERN = re.compile(r"0x[0-9a-fA-F]{64}")
ADDRESS_PATTERN = re.compile(r"0x[0-9a-fA-F]{40}")
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
SECRET_KEY_PARTS = ("private", "mnemonic", "secret", "password", "token", "credential")


@dataclass(frozen=True)
class DeploymentRequest:
    contract_path: Path
    confirmed_wallet: str
    case_id: str
    product_type: str
    recall_number: str
    subject_json: str


def canonical_source_bytes(value: bytes | str) -> bytes:
    text = value.decode("utf-8") if isinstance(value, bytes) else value
    return (text.replace("\r\n", "\n").rstrip("\n") + "\n").encode("utf-8")


def source_sha256(value: bytes | str) -> str:
    return hashlib.sha256(canonical_source_bytes(value)).hexdigest()


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SECRET_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    return value


def _require_tx_hash(value: str) -> str:
    if TX_PATTERN.fullmatch(value) is None:
        raise RuntimeError("Invalid transaction hash returned by CLI")
    return value.lower()


def _execution_result(receipt: dict) -> str:
    try:
        return receipt["consensus_data"]["leader_receipt"][0]["execution_result"]
    except (KeyError, IndexError, TypeError):
        return ""


def _require_final_success(receipt: dict) -> None:
    if receipt.get("status") != "FINALIZED":
        raise RuntimeError("Transaction did not reach FINALIZED")
    if _execution_result(receipt) != "SUCCESS":
        raise RuntimeError("Transaction execution did not reach SUCCESS")


def _contract_address(receipt: dict) -> str:
    candidates = (
        receipt.get("data", {}).get("contract_address"),
        receipt.get("tx_data_decoded", {}).get("contract_address"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and ADDRESS_PATTERN.fullmatch(candidate):
            return candidate
    raise RuntimeError("Deployment receipt has no valid contract address")


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(Path(temporary_name), path)
    finally:
        temporary_path = Path(temporary_name)
        if temporary_path.exists():
            temporary_path.unlink()


def run_verified_deployment(
    request: DeploymentRequest,
    *,
    cli,
    output_dir: Path,
) -> dict:
    preflight = _sanitize(cli.preflight())
    if preflight.get("network") != "studionet":
        raise RuntimeError("Active network must be Studionet")
    if preflight.get("chain_id") != STUDIONET_CHAIN_ID:
        raise RuntimeError("Studionet chain ID must be 61999")
    active_wallet = str(preflight.get("wallet", ""))
    if active_wallet.lower() != request.confirmed_wallet.lower():
        raise RuntimeError("Active wallet does not match exact wallet confirmation")
    local_source = request.contract_path.read_bytes()
    local_hash = source_sha256(local_source)

    deploy_tx = _require_tx_hash(cli.deploy(request.contract_path))
    deploy_receipt = cli.receipt(deploy_tx)
    _require_final_success(deploy_receipt)
    contract_address = _contract_address(deploy_receipt)

    open_args = [
        request.case_id,
        request.product_type,
        request.recall_number,
        request.subject_json,
        "",
        "",
    ]
    open_tx = _require_tx_hash(cli.write(contract_address, "open_case", open_args))
    open_receipt = cli.receipt(open_tx)
    _require_final_success(open_receipt)

    resolve_tx = _require_tx_hash(cli.write(contract_address, "resolve_case", [request.case_id]))
    resolve_receipt = cli.receipt(resolve_tx)
    _require_final_success(resolve_receipt)

    readback = _sanitize(
        {
            "case": cli.call(contract_address, "read_case", [request.case_id]),
            "assessment": cli.call(contract_address, "read_assessment", [request.case_id]),
            "effective_status": cli.call(contract_address, "read_effective_status", [request.case_id]),
        }
    )
    deployed_hash = source_sha256(cli.code(contract_address))
    if deployed_hash != local_hash:
        raise RuntimeError("Deployed source hash does not match local source hash")

    manifest = {
        "network": "studionet",
        "chain_id": STUDIONET_CHAIN_ID,
        "rpc_url": preflight.get("rpc_url"),
        "deployer": active_wallet,
        "contract_address": contract_address,
        "case_id": request.case_id,
        "recall_number": request.recall_number,
        "source_sha256": local_hash,
        "deployed_source_sha256": deployed_hash,
        "transactions": {
            "deploy": deploy_tx,
            "open_case": open_tx,
            "resolve_case": resolve_tx,
        },
        "receipts": {
            "deploy": {"status": "FINALIZED", "execution_result": "SUCCESS"},
            "open_case": {"status": "FINALIZED", "execution_result": "SUCCESS"},
            "resolve_case": {"status": "FINALIZED", "execution_result": "SUCCESS"},
        },
        "readback": readback,
        "explorer": {
            "contract": f"{EXPLORER_BASE}/address/{contract_address}",
            "deploy_transaction": f"{EXPLORER_BASE}/tx/{deploy_tx}",
            "open_case_transaction": f"{EXPLORER_BASE}/tx/{open_tx}",
            "resolve_case_transaction": f"{EXPLORER_BASE}/tx/{resolve_tx}",
        },
        "tools": {"genlayer_cli": preflight.get("cli_version")},
        "generated_at": datetime.now(UTC).isoformat(),
    }
    manifest = _sanitize(manifest)
    _atomic_json(output_dir / "studionet.json", manifest)
    return manifest


class GenLayerCli:
    def __init__(self, executable: str = "genlayer"):
        resolved = shutil.which(executable)
        if resolved is None:
            raise RuntimeError("GenLayer CLI executable was not found")
        self.executable = resolved

    def _run(self, *arguments: str) -> str:
        completed = subprocess.run(
            [self.executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"GenLayer CLI command failed with exit code {completed.returncode}")
        return ANSI_PATTERN.sub("", completed.stdout)

    @staticmethod
    def _result_object(output: str) -> dict | list:
        marker = output.find("Result:")
        start = output.find("{", marker if marker >= 0 else 0)
        end = output.rfind("}")
        if start < 0 or end < start:
            raise RuntimeError("GenLayer CLI returned no structured result")
        block = output[start : end + 1]
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pythonish = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r"\1'\2'\3", block)
            pythonish = re.sub(r"\btrue\b", "True", pythonish)
            pythonish = re.sub(r"\bfalse\b", "False", pythonish)
            pythonish = re.sub(r"\bnull\b", "None", pythonish)
            value = ast.literal_eval(pythonish)
            if not isinstance(value, dict | list):
                raise RuntimeError("GenLayer CLI result has invalid shape") from None
            return value

    def preflight(self) -> dict:
        config = self._result_object(self._run("config", "get"))
        account = self._result_object(self._run("account", "show"))
        network = self._result_object(self._run("network", "info"))
        return {
            "network": config["network"],
            "chain_id": int(network["chainId"]),
            "wallet": account["address"],
            "rpc_url": network["rpc"],
            "cli_version": self._run("--version").strip(),
        }

    def deploy(self, contract_path: Path) -> str:
        output = self._run("deploy", "--contract", str(contract_path))
        matches = TX_PATTERN.findall(output)
        if not matches:
            raise RuntimeError("Deployment command returned no transaction hash")
        return matches[-1]

    def receipt(self, tx_hash: str) -> dict:
        value = self._result_object(self._run("receipt", tx_hash, "--status", "FINALIZED"))
        if not isinstance(value, dict):
            raise RuntimeError("Receipt has invalid shape")
        return value

    def write(self, contract_address: str, method: str, args: list[str]) -> str:
        output = self._run("write", contract_address, method, "--args", *args)
        matches = TX_PATTERN.findall(output)
        if not matches:
            raise RuntimeError("Write command returned no transaction hash")
        return matches[-1]

    def call(self, contract_address: str, method: str, args: list[str]):
        return self._result_object(self._run("call", contract_address, method, "--args", *args))

    def code(self, contract_address: str) -> str:
        output = self._run("code", contract_address)
        marker = output.find("Result:")
        if marker < 0:
            raise RuntimeError("Code command returned no source")
        source = output[marker + len("Result:") :]
        source = re.split(r"\n[\u221a]\s", source, maxsplit=1)[0]
        return source.strip("\r\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight or run a verified Studionet deployment")
    parser.add_argument("--confirmed-wallet", default="")
    parser.add_argument("--contract", type=Path, default=Path("contracts/fda_recall_applicability_registry.py"))
    parser.add_argument("--subject", type=Path, default=Path("samples/subject-affected.json"))
    parser.add_argument("--case-id", default="studionet-h-1223-2026")
    parser.add_argument("--recall-number", default="H-1223-2026")
    parser.add_argument("--output-dir", type=Path, default=Path("deployments"))
    args = parser.parse_args()
    cli = GenLayerCli()
    preflight = cli.preflight()
    contract_hash = source_sha256(args.contract.read_bytes())
    planned = {
        **preflight,
        "contract": str(args.contract),
        "source_sha256": contract_hash,
        "planned_actions": ["deploy", "open_case", "resolve_case", "readback", "source verification"],
    }
    if not args.confirmed_wallet:
        print(json.dumps(planned, indent=2, sort_keys=True))
        return 0
    request = DeploymentRequest(
        contract_path=args.contract,
        confirmed_wallet=args.confirmed_wallet,
        case_id=args.case_id,
        product_type="food",
        recall_number=args.recall_number,
        subject_json=args.subject.read_text(encoding="utf-8").strip(),
    )
    manifest = run_verified_deployment(request, cli=cli, output_dir=args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
