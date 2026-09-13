---
name: shared-harness
description: "Connect agent-harness to editors and agent CLIs (shared skills and rules, MCP server, read hook) and use its bounded context and memory MCP tools. Use when installing or diagnosing the harness in a client, or when a task needs bounded reading of large files."
metadata:
  version: 1.0.0
---

# Shared harness

The harness keeps one canonical copy of shared resources under
`~/.agent-harness` (skills, rules, memory, roles, config) and connects clients
to it through an explicit manifest. Nothing is changed for a client that the
manifest does not name. Agents themselves are configured by the cold start in
the multi-agent skill.

`<harness>` below is the checkout, or the installed package root when
`--mam` is omitted.

## Connect clients

Always show the plan before changing anything, and ask before `apply` or
`configure`: they edit client settings.

```sh
python -m execution.shared_harness plan --clients <manifest.json>
python -m execution.shared_harness apply --rules <rules.md> --clients <manifest.json>
python -m execution.client_adapters configure --clients <manifest.json>
```

A manifest names, per client, a skills directory, an instructions file, an
include file, where its MCP server entry goes and where its hook goes. The
harness ships `examples/clients-claude-codex.json` and
`examples/clients-example.json` to copy from.

- **Add a bundled or shared skill** to every client in the manifest:
  `python -m execution.shared_harness add --source <harness>/skills/<name> --clients <manifest.json>`.
  The source must live in the harness `skills/` or `~/.agent-harness/skills`.
- **Check**: `python -m execution.shared_harness doctor` and
  `python -m execution.client_adapters doctor`.
- **Roll back**: the same modules with `rollback`. A rollback stops when the
  person edited a managed setting since it was applied; find out why, do not
  force it.

## MCP tools

The MCP server (`agent-harness-mcp`) exposes:

| Tool | Use |
|---|---|
| `context_read` | One question about up to 30 large text files in a project, answered by the `context_read` role binding within a bounded budget |
| `research_batch` | Up to six short questions (`kind`: `summary` or `code`, up to six paths each), at most three workers in parallel, plus a registered Graphify snapshot when one exists |
| `memory_search` | Notes for this project and explicitly global ones |
| `memory_write` | One durable fact; search first, global reach only when asked |
| `reasoning_assess` | The effort the harness would choose for a task, without calling a model |

Every tool that reads takes an absolute `project` path and stays inside it.
The cheap agents behind `summary`, `code` and `context_read` are set in the
config's `role_bindings`.

## Read hook

The hook denies whole-file reads of text files longer than 350 lines by default
(recognised Read and shell reads) and points at ranges or `context_read`.
Ranges are allowed. It is a guard against bulk reading, not a sandbox. Some
clients require trusting a new hook before it runs.

## Graphify indexes

Register a snapshot so `research_batch` can use it:

```sh
python -m execution.index_workers --project <absolute project> --register-graph <graph.json> --snapshot "<date> <commit>"
```

The graph must live inside the project or `~/.agent-harness/skills`. A
snapshot is not the current code: check conclusions against the files.
