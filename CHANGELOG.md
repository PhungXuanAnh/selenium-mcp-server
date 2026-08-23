# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add a 10-tool compact surface that maps all existing browser capabilities while retaining the original 23-tool legacy profile as an explicit compatibility fallback
- Add profile/schema budgets, old-to-new mapping parity tests, and real MCP stdio coverage for both profiles
- Add compact condition waits, explicit navigation policies, document-scoped element references, nine interaction actions, viewport/full-page/element screenshots, bounded diagnostics cursors, and structured async JavaScript results
- Add a controlled `--download_dir` with runtime browser/download metadata from `tabs(action="list")`
- Add compact network event-type filtering and complete parser-checked JSON argument examples for every overloaded compact action

### Changed
- Make compact the default MCP tool profile; pass `--tool-profile legacy` for the original 23 tool names
- Shorten legacy tool descriptions and server instructions without changing legacy names or call contracts
- Document the compact recommended workflow, action-specific JSON contracts, selector/reference lifecycle, timing units, style precedence, event postconditions, runtime discovery, and sensitive-data boundaries
- Clarify that text equality compares complete body text or newline-joined matched-element text, depending on whether a selector is supplied
- Expose one concise valid JSON arguments example in each high-friction compact description for `browser_logs`, `wait_for`, and `interact_element`
- Route compact console/performance reads through bounded session-local cursor buffers with peek/consume semantics and redaction by default; JavaScript console capture remains explicitly opt-in

### Fixed
- Verify input values after Selenium entry, recover transient no-op writes, and never report set-value success when the DOM value still differs
- Briefly wait for delayed Chrome console delivery and surface WebDriver log-read failures instead of reporting a misleading empty buffer
- Normalize console levels so `ALL` disables filtering, `ERROR` matches Chrome `SEVERE`, and invalid values report the accepted set
- Stop retaining performance logs in a process-global `/tmp` history; compact network reads now use bounded pagination and preserve events drained by network-idle waits
- Remove Chrome session and stacktrace noise from bounded response-body error envelopes

## [0.1.8] - 2026-08-22

### Added
- Tools to list, open, switch, and close browser tabs
- MCP stdio end-to-end coverage for tab management and named screenshot artifacts

### Changed
- Replace screenshot `save_path` with a required semantic `file_name` and optional `directory`; guide Agents to prefer absolute directories inside their current workspace, default to `<workspace>/tmp/selenium-screenshot` when omitted, normalize PNG names, and preserve existing artifacts with numeric suffixes

### Fixed
- Pin Hatchling below 1.32 so release builds use Core Metadata accepted by current PyPI tooling

## [0.1.6] - 2025-10-04
### Added
- Comprehensive CHANGELOG.md file following conventional format
- Updated PyPI metadata to point to GitHub changelog

### Changed
- Updated changelog URL in pyproject.toml to point to GitHub CHANGELOG.md file

## [0.1.5] - 2025-10-04
### Added
- Enhanced network log handling and updated test scripts for clarity
- Chrome profile support to driver initialization
- Improved UndetectedChromeDriver initialization and error handling
- Improved server configurations and driver initialization logging
- Refactored driver modules and implemented NormalChromeDriver and UndetectedChromeDriver classes
- Enhanced driver management and added undetected Chrome driver support
- Updated screenshot tool to accept optional save path
- Improved documentation

### Changed
- Reorganized logging configuration
- Enhanced network log testing functionality
- Updated features section and removed debug mode references from README
- Cleaned up imports and removed unnecessary comments in main files
- Refactored README structure and updated section numbering for clarity

## [0.1.4] - 2025-09-xx
### Added
- Style tools and test script for Selenium MCP server
- Tool to get direct children of an element with pagination support
- Tool to run javascript in console

### Changed
- Refactored tools to interact with element
- Refactored local storage tools
- Refactored get console log and get network log tools
- Refactored navigate, take screenshot, check_page_ready tools

## [0.1.3] - 2025-09-xx
### Added
- Publishing guide

### Changed
- Refactored mcp.json and pyproject.toml for improved command structure and script entry point
- README updates
