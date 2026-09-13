# Multi-agent orchestration

This package is the generated multi-agent subset of Agent Harness: orchestration, providers, cold start, graphs, reasoning, memory and MCP. It is generated from Agent Harness; edit the harness, not this tree.

Install it with Python 3.11 or newer:

```sh
python -m pip install .
agent-harness --help
```

Run the cold start through the bundled `multi-agent` skill, then use
`agent-harness setup detect` and `agent-harness setup write answers.json`.

To register the MCP server by hand, add `agent-harness-mcp` as a stdio server
in the MCP client configuration, using the installed command as its command.
Installing this package and Agent Harness in one environment is unsupported:
their files and console entry points conflict.
