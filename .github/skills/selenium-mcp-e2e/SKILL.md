---
name: selenium-mcp-e2e
description: Run and diagnose this repository's real MCP stdio end-to-end test after any file update. Use before handing off every change to selenium-mcp-server; unit tests, direct Python tool calls, and MCP Inspector checks are not substitutes.
---

# Selenium MCP E2E

Validate every repository update through the actual MCP client/server boundary and real Chrome.

## Required check

Run from the repository root after the final edit:

```bash
.venv/bin/python tests/mcp_stdio_e2e.py -v
```

The test must exercise all of these layers in one run:

- spawn `python -m mcp_server_selenium` over stdio;
- initialize a real MCP `ClientSession` and discover the affected tools;
- invoke the tools through MCP serialization and dispatch;
- operate real Chrome through the normal Selenium driver;
- verify observable filesystem/browser results;
- close the client/server and browser cleanly.

The test owns a temporary `user_data_dir`. Do not point it at the persistent profile
`/home/xuananh/.config/google-chrome-selenium-mcp-direct`.

## Failure handling

If E2E fails, keep the exact failing output, diagnose the server/Chrome state, fix the cause, and rerun the same E2E command. Do not replace it with a unit test, direct tool import, or a cheaper smoke check.

If Chrome or another external dependency genuinely prevents execution, report the blocker explicitly. Do not describe the update as verified.

After the run, confirm no test process remains:

```bash
ps -eo pid,ppid,args | rg '([m]cp_server_selenium|[c]hrome).*?/tmp/[^ ]+/chrome-profile' || true
```

No output is the expected result. Do not stop the persistent MCP server using
`/home/xuananh/.config/google-chrome-selenium-mcp-direct`. Report the E2E command,
pass/fail result, and leak-check result in the handoff.
