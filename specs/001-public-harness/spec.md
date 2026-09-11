# Provider-neutral public Agent Harness

## User outcome
A user can install the reusable harness, configure their own command-line agents, share their own resources across clients, and run bounded collaborative tasks without adopting the maintainer's skills, accounts or model choices.

## Architecture decision
Create a separate Agent Harness repository derived from multi-agent-mod. The product boundary now includes context, memory, indexes, shared resources and client integration in addition to orchestration. Reuse the tested implementation and preserve MIT attribution. This new repository is the intended canonical home for further reusable technology development; the existing personal installation is not changed or automatically migrated.

## Required behavior
1. Provider commands, model capabilities, author identities and role bindings are configuration data. A third provider works without editing Python. Built-in vendor examples are optional.
2. DAG orchestration, independent review, project-scoped memory, per-task reasoning, bounded reading, context caching and external index retrieval retain their tested behavior.
3. Resource sharing and MCP connection technology is included without private resource catalogs. Client-specific support is explicit and reversible; generic clients have a documented extension path.
4. The default demonstration and tests run offline without credentials or paid model calls. Installation works outside the source checkout.
5. Public content excludes machine paths, credentials, project memory, indexes, run logs, private graphs and client snapshots. Git history is not copied.
6. Traceability distinguishes planned routing, dispatched parameters and actual outcomes. Unsupported reasoning is visible. No automatic costly fallback or token-saving percentage claims.

## Non-goals
Publishing a remote repository, migrating the live installation, bundling personal skills/MCP lists, shipping third-party source unnecessarily, or claiming live validation for every vendor.

## Acceptance
Install locally into an isolated environment; run the full offline suite; demonstrate an arbitrary third-provider name through the common execution path; verify package resources, memory isolation, reviewer identity, cache and bounds; verify reversible client operations in temporary homes; audit the exact publishable file set and create a clean local Git repository.
