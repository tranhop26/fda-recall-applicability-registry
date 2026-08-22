import hashlib
import json
from dataclasses import replace

import pytest

from deploy.run_studionet import DeploymentRequest, run_verified_deployment

SOURCE = "# contract source\n"
WALLET = "0x" + "12" * 20
CONTRACT = "0x" + "34" * 20
TX_HASHES = ["0x" + pair * 32 for pair in ("aa", "bb", "cc")]


def finalized_receipt(tx_hash, *, execution_result="SUCCESS", contract_address=None):
    receipt = {
        "hash": tx_hash,
        "status": "FINALIZED",
        "consensus_data": {"leader_receipt": [{"execution_result": execution_result}]},
    }
    if contract_address is not None:
        receipt["data"] = {"contract_address": contract_address}
    return receipt


class FakeCli:
    def __init__(self):
        self.receipts = {
            TX_HASHES[0]: finalized_receipt(TX_HASHES[0], contract_address=CONTRACT),
            TX_HASHES[1]: finalized_receipt(TX_HASHES[1]),
            TX_HASHES[2]: finalized_receipt(TX_HASHES[2]),
        }
        self.deployed_code = SOURCE
        self.readbacks = {
            "read_case": ["DECIDED"],
            "read_assessment": ["AFFECTED", 31, 0, 0],
            "read_effective_status": ["AFFECTED", "CURRENT", 123],
        }
        self.write_index = 1

    def preflight(self):
        return {
            "network": "studionet",
            "chain_id": 61999,
            "wallet": WALLET,
            "rpc_url": "https://studio.genlayer.com/api",
            "cli_version": "0.39.2",
        }

    def deploy(self, contract_path):
        return TX_HASHES[0]

    def receipt(self, tx_hash):
        return self.receipts[tx_hash]

    def write(self, contract_address, method, args):
        tx_hash = TX_HASHES[self.write_index]
        self.write_index += 1
        return tx_hash

    def call(self, contract_address, method, args):
        return self.readbacks[method]

    def code(self, contract_address):
        return self.deployed_code


@pytest.fixture
def contract_source(tmp_path):
    path = tmp_path / "contract.py"
    path.write_text(SOURCE, encoding="utf-8", newline="")
    return path


@pytest.fixture
def deployment_request(contract_source):
    return DeploymentRequest(
        contract_path=contract_source,
        confirmed_wallet=WALLET,
        case_id="sample-case",
        product_type="food",
        recall_number="H-1223-2026",
        subject_json='{"subject":"bounded"}',
    )


def test_manifest_not_written_when_receipt_is_not_finalized(tmp_path, deployment_request):
    cli = FakeCli()
    cli.receipts[TX_HASHES[0]]["status"] = "ACCEPTED"

    with pytest.raises(RuntimeError, match="FINALIZED"):
        run_verified_deployment(deployment_request, cli=cli, output_dir=tmp_path)

    assert not (tmp_path / "studionet.json").exists()


def test_manifest_not_written_when_execution_rolls_back(tmp_path, deployment_request):
    cli = FakeCli()
    cli.receipts[TX_HASHES[1]] = finalized_receipt(TX_HASHES[1], execution_result="ROLLBACK")

    with pytest.raises(RuntimeError, match="SUCCESS"):
        run_verified_deployment(deployment_request, cli=cli, output_dir=tmp_path)

    assert not (tmp_path / "studionet.json").exists()


def test_manifest_requires_deployed_source_hash_match(tmp_path, deployment_request):
    cli = FakeCli()
    cli.deployed_code = "different source\n"

    with pytest.raises(RuntimeError, match="source hash"):
        run_verified_deployment(deployment_request, cli=cli, output_dir=tmp_path)

    assert not (tmp_path / "studionet.json").exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("network", "localnet", "Studionet"),
        ("chain_id", 1337, "61999"),
        ("wallet", "0x" + "99" * 20, "wallet confirmation"),
    ],
)
def test_preflight_rejects_wrong_network_chain_or_wallet(tmp_path, deployment_request, field, value, message):
    cli = FakeCli()
    original = cli.preflight
    cli.preflight = lambda: {**original(), field: value}

    with pytest.raises(RuntimeError, match=message):
        run_verified_deployment(deployment_request, cli=cli, output_dir=tmp_path)


def test_success_writes_hash_bound_manifest_atomically(tmp_path, deployment_request, monkeypatch):
    cli = FakeCli()
    replacements = []
    import deploy.run_studionet as runner

    real_replace = runner.os.replace

    def recording_replace(source, destination):
        replacements.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(runner.os, "replace", recording_replace)

    manifest = run_verified_deployment(deployment_request, cli=cli, output_dir=tmp_path)

    path = tmp_path / "studionet.json"
    assert replacements and replacements[-1][1] == path
    assert json.loads(path.read_text(encoding="utf-8")) == manifest
    assert manifest["source_sha256"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert manifest["transactions"] == {
        "deploy": TX_HASHES[0],
        "open_case": TX_HASHES[1],
        "resolve_case": TX_HASHES[2],
    }
    assert manifest["readback"]["effective_status"][0] == "AFFECTED"


def test_manifest_and_error_text_do_not_contain_secret_fields(tmp_path, deployment_request):
    cli = FakeCli()
    secret = "do-not-leak-private-key"
    request = replace(deployment_request, subject_json='{"note":"safe"}')
    cli.readbacks["read_case"] = ["DECIDED", {"private_key": secret}]

    manifest = run_verified_deployment(request, cli=cli, output_dir=tmp_path)

    serialized = json.dumps(manifest)
    assert secret not in serialized
    assert "private_key" not in serialized.lower()
