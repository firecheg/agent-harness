# Providers and agent profiles

The harness executes configured command line workers through one registry. A
provider receives the task on standard input and returns text on standard
output (or JSON selected by `output`). The executor builds an argument list
with `shell=False`; configuration is never evaluated as shell code.

Set `AGENT_HARNESS_CONFIG` or pass `--config path/to/config.json` before a
`mam` subcommand. The bundled configuration uses the deterministic offline
`demo` provider:

```powershell
python mam.py ask demo-worker "check the configured path"
python mam.py --config examples/third-party-config.json ask third-party-worker "hello"
```

Each `providers` entry contains:

* `argv`: a non-empty argument vector. Supported substitutions are
  `{python}`, `{package_dir}`, `{model}`, `{effort}`, `{run}`, `{provider}` and
  `{sandbox}`. They remain individual arguments even when paths contain spaces.
* `input`: currently `stdin`.
* `output`: `text`, `json`, or `json_field`; the latter also requires
  `output_field` and accepts dotted JSON paths such as `response.answer`.
* `models`: model names mapped to `supported_effort` levels from
  `low`, `medium`, `high`, `xhigh`, `max`; `default_model` is a separate
  provider field naming one of those models.
* `model_args` and `effort_args`: optional argument templates appended to
  `argv` when a model or effective effort is selected.
* `author_identity`: the account or identity represented by the provider.
  Reviewer aliases with the same identity are rejected as self-review.
* `timeout_seconds`: a positive subprocess timeout.

`agents` binds a stable alias to a provider and model and gives it a role.
`role_bindings` maps task roles such as `summary`, `code`, or `context_read`
to those aliases. `reviewers` lists eligible aliases. The alias is not an
identity: two aliases sharing `author_identity` are still one author. A
profile may override the provider identity with its own `author_identity` when
two configured accounts are genuinely independent.

For an arbitrary third-party CLI, copy `examples/third-party-config.json`,
replace its `argv` with the CLI and worker path, and keep the worker's prompt
input on stdin. Declaring only the reasoning levels the model actually
supports makes an unsupported request visible in the persisted reasoning
decision; the harness does not silently fall back to a more expensive model.
An empty `supported_effort` list is valid and means the configured model is
known but supports no effort flag. An unknown model/provider is reported as
`unknown_model`; a configured model with a missing requested level is reported
as `unsupported`.

The bundled `demo` provider is explicitly a test/demo worker. It computes a
hash of stdin and prints metadata; it never contacts an LLM service.
