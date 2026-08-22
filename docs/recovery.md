# Recovery for an intentionally frozen contract

The contract is `INTENTIONALLY_FROZEN`. Recovery never modifies deployed code or historical cases, and there is no privileged rescue path or fund custody.

## Normal refresh

After a decision expires, open a new case on the same deployment using that terminal case as predecessor. The contract requires the current contract address, an existing terminal predecessor, and identical product type, recall number, and subject hash. The old case and assessment remain unchanged.

## Defect or policy migration

1. Stop consumers from opening new cases on the affected deployment.
2. Publish the defect/policy explanation and a reviewed replacement source.
3. Run all direct, integration-collection, deployment-runner, lint, and secret gates.
4. Inspect network and wallet and obtain exact user confirmation.
5. Deploy the replacement; require `FINALIZED/SUCCESS`, source-hash equality, and readback.
6. Publish an evidence mapping from old contract/case IDs to new contract/case IDs.
7. Require consumers to switch explicitly to the verified new contract address.

The current contract deliberately rejects non-local predecessor addresses because it cannot authenticate another deployment's case storage. Therefore cross-deployment lineage is an explicit deployment-evidence mapping, not an on-chain claim accepted from arbitrary calldata.
