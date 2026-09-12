# Architecture and boundaries

Agent Harness coordinates user-configured command-line agents and shares user-owned resources across clients. Provider names, role assignments and model capabilities belong in configuration; private state does not belong in this repository.

```mermaid
flowchart TD
  User[CLI or MCP client] --> Task[Task and project boundary]
  Task --> Policy[Role and reasoning policy]
  Policy --> Registry[Configured agent/provider registry]
  Registry --> Runner[Argument-list process runner]
  Runner --> Provider[External CLI provider]
  Provider --> Evidence[Result, provenance and invocation log]
  Task --> Memory[Project-scoped memory]
  Task --> Context[Bounded context and cache]
  Context --> Index[Optional external index query]
  Context --> Policy
  Resources[User-owned shared resources] --> Adapters[Explicit client adapters]
```

## Execution and provider contract

The runner receives a validated task, resolves a configured role/agent and records the chosen model and reasoning parameters. It invokes an argument list without shell evaluation. Provider response parsing is explicit. A command alias is not an independent author: reviewer checks use the configured author identity.

The generic provider boundary is a command-line process. Supporting an arbitrary HTTP API still requires a CLI or bridge that speaks to that API; the project does not claim identical APIs across model vendors. Optional vendor presets are conveniences, not core requirements.

## Graphs, roles and rounds

A graph node names either a configured agent or a role (`spec`, `implement`, `review`, `review_2`, `judge`, `prosecutor`, ...). `agent-harness init` records which agents fill each role on this machine in `~/.agent-harness/roles.json` (`AGENT_HARNESS_ROLES` overrides); a role may list a preference chain, and the first installed agent wins. Binding happens before a run and re-validates the bound graph, so two roles that resolve to one author identity are rejected as self-review. A spec's `distinct` groups name roles that must resolve to different author identities even without a review edge between them.

A `rounds` block (`{"nodes": [...], "until": "<node id>", "max": N}`) runs its nodes in order, repeatedly, until the `until` node's answer ends in `{"pass": true, "issues": []}`; sub-nodes receive `{round}` and `{previous}` (the last round's transcript). Running out of rounds is a node failure, not a pass. Blocks cannot nest.

## Reasoning and cost

Each invocation is assessed independently. The caller supplies the task kind or all five complexity dimensions; source text, file count and parent effort are not proxies for task complexity. Unknown difficulty defaults to medium. Automatic selection never chooses max. Unsupported model capabilities are reported explicitly.

A recommendation is not a dispatched request. Logs distinguish the recommended level, selected/capped level, parameter sent, provider outcome and available usage information. A CLI flag does not measure internal thinking. The harness does not promise a fixed cost reduction or infer missing billing data.

## Context, indexes and memory

Workers receive bounded source selections and questions. Cache identity includes source fingerprints and reasoning policy/decision. External index queries return selected evidence; an index is not assumed fresh without its snapshot metadata. An indexer is optional when explicit source paths are supplied.

Memory is scoped to repository identity, including worktrees, or an explicit workspace identity. Global notes require explicit global reach. Memory is dated context, not an instruction channel. Credentials, transcripts and source corpora are not public examples.

## Shared resources and clients

The resource layer manages references to a user-owned canonical location. A client adapter describes where that client expects resources or server configuration. Changes are explicit, journaled and reversible; rollback must not overwrite a user's later edits. Provider authorization stays with the provider/client.

Native read hooks cover recognized operations and supported clients. They are not a universal sandbox and cannot reliably infer the purpose of a source read. Instructions and observable routing remain part of the operational policy.

## Why a separate repository

The source project supplied graph orchestration and memory. The extracted product also contains common resources, client connections, context budgeting, indexing bridges and reasoning policy. Keeping these as one public technology package gives them a clear installation and extension contract without distributing a maintainer's live setup.

This repository is the intended home for future reusable-core development. The source installation is retained as a migration reference; it is not modified by preparing this release. Avoid maintaining two divergent implementations after migration.
