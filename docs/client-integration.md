# Client integration

Agent Harness has no implicit client list. A client is touched only when it is
named in a manifest, such as `examples/clients-example.json`. The manifest can
declare a skills directory, an instructions file, an include file, a JSON MCP
path, a marker-delimited configuration fragment, and a JSON hook path.

From the repository root, inspect a profile before changing it:

```powershell
python -m execution.shared_harness plan `
  --home $env:USERPROFILE `
  --shared "$env:USERPROFILE/.agent-harness" `
  --mam (Get-Location) `
  --clients examples/clients-example.json
```

Apply the shared rules and link the configured skill directories. The operation
is reversible and records its transaction under the selected shared directory:

```powershell
python -m execution.shared_harness apply `
  --home $env:USERPROFILE `
  --shared "$env:USERPROFILE/.agent-harness" `
  --mam (Get-Location) `
  --rules examples/shared-rules.md `
  --clients examples/clients-example.json
```

Register MCP and hook settings for the same explicit clients:

```powershell
python -m execution.client_adapters configure `
  --home $env:USERPROFILE `
  --mam (Get-Location) `
  --clients examples/clients-example.json
```

Check both transaction layers and roll them back when needed:

```powershell
python -m execution.shared_harness doctor --home $env:USERPROFILE
python -m execution.client_adapters doctor --home $env:USERPROFILE
python -m execution.shared_harness rollback `
  --home $env:USERPROFILE `
  --shared "$env:USERPROFILE/.agent-harness"
python -m execution.client_adapters rollback --home $env:USERPROFILE
```

Use `--clients` with a copied manifest for another editor or agent CLI. Keep
paths relative to the selected home. The adapter refuses pre-existing managed
entries, detects edits before rollback, and rejects links or junctions that
would write outside that home.
