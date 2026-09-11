# Plan

1. Inventory provenance and technology, define public boundaries and provider configuration.
2. Export an explicit source allowlist into the isolated repository; make orchestration/context provider-neutral and shared-resource/client integrations portable.
3. Package the application with an offline demo, configuration examples, architecture and extension documentation; retain MIT provenance.
4. Independently verify installation, tests, generic-provider integration and publication contents; initialize local Git without pushing.

## Ownership
Core executor owns orchestration, provider configuration, context/index workers and packaging. Integration executor owns resource/client adapters, read gate and Spec Kit wrapper. The primary agent owns architecture, public instructions, publication documentation and independent acceptance. Executors must not edit overlapping files.
