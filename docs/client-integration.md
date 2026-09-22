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

Apply the minimal shared `AGENTS.md`, the bundled `examples/rules/*.md` role and
coordinator templates, and link configured skill directories. The Claude
example's `CLAUDE.md` imports both `AGENTS.md` and `orchestrator.md`;
`ROLE:` tasks follow worker files instead. The operation is reversible and
records its transaction under the selected shared directory:

```powershell
python -m execution.shared_harness apply `
  --home $env:USERPROFILE `
  --shared "$env:USERPROFILE/.agent-harness" `
  --mam (Get-Location) `
  --rules examples/shared-rules.md `
  --clients examples/clients-example.json
```

An already-active installation remains unchanged on repeat `apply`; run
`rollback` and then `apply` to install a newer template set. Existing custom
rule files that differ from bundled templates stop the new install for manual
resolution.

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

`configure` also copies `AGENT_HARNESS_CONFIG`, `AGENT_HARNESS_MEMORY` and
`AGENT_HARNESS_SHARED` into the server entry's `env` when they are set,
because some clients (e.g. Codex) launch stdio MCP servers without passing
along the user's environment. After changing those variables, run `upgrade`
(rollback + configure) to refresh the recorded entries.

## Shared resources and clients

The resource layer manages references to a user-owned canonical location. A client adapter describes where that client expects resources or server configuration. Changes are explicit, journaled and reversible; rollback must not overwrite a user's later edits. Provider authorization stays with the provider/client.

Native read hooks cover recognized operations and supported clients. They are not a universal sandbox and cannot reliably infer the purpose of a source read. Instructions and observable routing remain part of the operational policy.

## Why a separate repository

Agent Harness is where the code is developed. multi-agent-mod is a generated subset without the client wiring (tools/export_mod.py) and is never edited directly.
