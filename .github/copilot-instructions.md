# Repository instructions

## Mandatory E2E after every update

After changing any file in this repository—including source, tests, dependencies, configuration, documentation, instructions, prompts, or skills—read and follow `.github/skills/selenium-mcp-e2e/SKILL.md`.

Run the real MCP stdio E2E after the final edit and before declaring the work complete:

```bash
.venv/bin/python tests/mcp_stdio_e2e.py -v
```

- The command must exit successfully. Unit tests, direct Python tool calls, compilation, linting, and MCP Inspector checks do not replace this E2E.
- If E2E fails, fix the cause and rerun it. If an external dependency prevents execution, report the work as blocked or unverified; do not claim completion.
- Keep E2E isolated from `/home/xuananh/.config/google-chrome-selenium-mcp-direct`; the test must use its temporary Chrome profile.
- Confirm that the E2E leaves no MCP server or test Chrome process, and include the E2E and leak-check results in the final handoff.
