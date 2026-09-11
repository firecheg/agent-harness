# Local publication validation

The prepared source passed the following checks on Windows:

- Python 3.11: full unittest discovery ran 68 tests; 67 passed and one was skipped because creating a file symlink requires unavailable privileges. The path-guard assertion and real directory-junction regression passed.
- Python 3.14: a wheel was built and installed into a clean virtual environment outside the checkout. Installed CLI help, the offline demo, and MCP initialize/tools-list requests passed.
- An independently constructed third CLI provider ran using configuration alone. Its empty supported-effort list produced no effective effort and no effort argument.
- The installed-package smoke helper passed. Packaged source files matched the checked source after newline normalization.
- Independent temporary-profile reproductions confirmed conflict refusal, new fragment configuration creation, and rejection of a parent junction escaping the selected home.
- The publication checker passed against the Git index, including explicit private-identifier deny checks; the staged whitespace check passed.

The deterministic providers exercise process integration, not model intelligence. External vendor services, Graphify and Spec Kit were not called during these offline checks. The Windows/Ubuntu GitHub Actions workflow is configured but has not been run remotely. File-symlink behavior on POSIX remains covered by a test awaiting execution on that platform.

The existing personal installation was not migrated. No remote repository was created and no push was performed.
