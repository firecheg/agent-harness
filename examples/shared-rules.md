# Shared agent rules

The coordinator owns analysis, task specification, and final judgment. Configured
summary and code workers perform all source orientation, search, classification,
fact gathering, and implementation, regardless of file size or how the source is
split. The coordinator reads original source only to check a specific worker
claim, diff, or disputed fact, and states that question first. The first working
update, every routing change, and the final update include a truthful canary with
status (`planned`, `dispatched`, `completed`, or `cached`) and a real run
reference. Direct work states `no delegation` and its reason.

Select effort per task: `low` for mechanical work, `medium` for ordinary
engineering, `high` for difficult diagnosis or safety, and `xhigh` for
exceptional cross service work. Use `max` only with explicit project or user
permission; if unsupported, record `effective unset`. Use one initial attempt
and at most one targeted correction for a diagnosed failure. Keep memory scoped
to the project and make narrow exceptions explicit. These are coordination
policies, not hard runtime limits or a sandbox boundary; the configured runtime
remains the source of enforcement.
