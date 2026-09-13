# Agent Harness

A provider-neutral Python harness for collaborative command-line agents: task graphs, independent review, project memory, bounded context, adaptive reasoning effort and shared client resources.

This repository contains the technology, not a personal collection of skills, MCP servers, accounts or model subscriptions. It is derived from [multi-agent-mod](https://github.com/firecheg/multi-agent-mod); see [provenance](PROVENANCE.md) and the [MIT license](LICENSE).

## What it does

| Layer | Responsibility |
|---|---|
| Provider registry | Resolve configured CLI commands, model capabilities, output formats and author identities |
| Orchestration | Run dependency graphs and keep author/reviewer identities separate |
| Reasoning policy | Choose effort independently for each task and report unsupported capabilities |
| Context | Select bounded sources, delegate reading and cache answers with source/policy fingerprints |
| Memory and indexes | Retrieve project-scoped notes and optional external index evidence |
| Client resources | Share user-owned resources through explicit, reversible client adapters |

Provider and client are separate concepts. A new CLI provider does not require a new client adapter. Existing Claude/Codex integrations are optional; the common execution path accepts configuration for other command-line programs.

## Install and try without an account

Use Python 3.11 or newer. From this source checkout:

```sh
python -m pip install .
agent-harness --help
agent-harness ask demo-worker "Explain what this demo does" --task-kind lookup
```

The bundled demo is a deterministic local program, not a language model. It exercises the execution path without credentials or paid calls. Run commands from the project you want to work on; local invocation artifacts belong in that project's ignored `.mam/` directory. Installation does not register or modify clients.

To connect the agent CLIs you actually use (Claude Code, Codex, Gemini, Antigravity, or your own), run the cold start: `agent-harness setup detect`, answer which models you use and who reviews whom, then `agent-harness setup write answers.json` — see [setup](docs/setup.md). It writes `~/.agent-harness/config.json`; point `AGENT_HARNESS_CONFIG` at it. Do not put credentials or private configuration in this repository. See [provider configuration](docs/providers.md) for command templates, role bindings and capability declarations.

## Connect a client

`agent-harness-mcp` is the stdio server entry point. Start it through your client's MCP configuration rather than expecting it to print an interactive menu. The resource layer uses an explicit client manifest; see [client integration](docs/client-integration.md) for plan/apply/doctor/rollback examples and supported configuration formats.

Resource sharing points to your own canonical files. This project does not bundle a skill catalog or transfer provider credentials between applications.

The [shared rules template](examples/shared-rules.md) carries the operating policy: delegate source orientation and implementation, choose effort per task, limit retries, and report truthful routing status with run references. Adapt it to your configured roles before applying it to clients. These instructions complement runtime checks; they do not create a universal read sandbox.

## Reasoning, identity and evidence

Mechanical work can use low effort; unknown tasks default to medium; difficult and critical task kinds establish higher recommendations. The caller supplies a task kind or complete complexity assessment. File count, prompt length and the parent's effort do not determine a child's effort. Automatic routing never chooses max.

Logs distinguish recommendations, selected/capped values, parameters sent and actual outcomes. Unsupported effort is visible. A requested setting is not a measurement of internal thinking, and no fixed token-saving percentage is promised.

Reviewer identity is declared in configuration. Renaming one author does not make its review independent; the harness rejects equal declared identities. It cannot independently authenticate the intellectual independence of external programs.

Graphify and Spec Kit are optional external tools. Index snapshots require provenance/freshness checks. Read hooks cover recognized operations, not arbitrary scripts or the intent behind every read.

## Development and publication

```sh
python -m unittest discover -s . -p "test_*.py"
python tools/check_publication.py .
```

Tests use temporary state and offline providers. Review [publication checks](docs/publication-checks.md) before staging a release: inside Git, the checker examines index blobs, not uncommitted replacements of staged files. The configured Windows/Ubuntu CI matrix is not a claim that remote jobs have already passed.

See [architecture and repository decision](docs/architecture.md) for boundaries, migration intent and why this reusable technology has a separate home. The existing personal installation is not migrated by this source export.

See [local validation results](docs/validation.md) for completed checks and their limits.
