# OpenAI guide alignment

Checked on 2026-10-15 against [Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model) and the [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

Agent Harness invokes configured CLIs; it does not construct OpenAI Responses
requests. Keep the selected agent profile and model. A guide's recommended
model is not permission to replace a user's selection.

## CLI compatibility

The local Codex CLI 0.156.0 help confirms `exec`, `--model`, `--config`,
`--sandbox`, `--ignore-user-config`, and `--disable`. The bundled preset's
command shape needs no API migration. `model_reasoning_effort` is a CLI config
key; supported levels must be verified for both model and installed client.
The public harness contract remains low/medium/high/xhigh/max. It does not
expose none/minimal/ultra or automatically select max.

API-only settings such as `reasoning.mode`, `reasoning.context`,
`configuration_update`, `prompt_cache_options`, async tools and Responses item
replay do not become CLI flags. The client owns transport and conversation
state. Do not add an API proxy or assume API availability proves CLI support.

The selected effort must be supported before dispatch. A known model with
no effort levels can still run with auto routing and no effort flag.
Unknown capability metadata remains explicitly reported; it is not proof
of a model's reasoning capabilities. See [reasoning](reasoning.md).

## Prompt policy

State the goal, context, constraints, required evidence and done criteria.
Let the worker choose implementation steps within those boundaries. A request
to fix or build authorises the in-scope local work and relevant checks; do not
ask for the same permission again. Material ambiguity or missing permission
still requires clarification after preparing what is already authorised.

Keep user instructions above skill recommendations. Explain the exact skill
instruction if it blocks progress. Keep provider-neutral roles, bounded tasks,
source attribution and review independence. Use checks proportional to the
change, expanding them only for new failures or unresolved questions.

Keep human permission boundaries for push, merge, deploy, publishing, secrets,
external messages and irreversible actions. Never bypass sandbox, approval
review or a safety refusal, including through another model or proxy.

## Applying rules

Bundled templates affect future installations. An existing installation does
not receive them from a repeated `apply`. Preserve local customisations and
use a before-image, conflict check and rollback for a targeted rule update.
Already-running chats must read an explicit handoff to adopt new guidance;
editing files cannot replace their existing system instructions or model.

Offline tests validate dispatch and rule installation, not model quality or
subscription availability. Use doctor without `--deep` to avoid paid calls.
