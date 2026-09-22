# Shared agent rules

- Answer clearly in the language requested. Check paths and shell syntax for the current platform; on PowerShell, do not use `&&`.
- Preserve unrelated uncommitted work and secrets. Do not print or commit credentials.
- Without explicit permission, do not push, force-push, change remotes, delete branches, publish, message others, or take irreversible actions.
- If the first line of a task is `ROLE: <role>`, you are an agent-harness worker. Follow the role instructions already in the task. Do not delegate or invoke agent-harness; the coordinator rules below do not apply.
- Otherwise you are the coordinator: read `rules/orchestrator.md` before substantial work and follow it.
