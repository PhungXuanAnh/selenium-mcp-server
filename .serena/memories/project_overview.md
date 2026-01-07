# Project Overview

## Purpose
The Selenium MCP Server is a Model Context Protocol (MCP) server that provides web automation capabilities through Selenium WebDriver. It allows AI assistants to interact with web pages by providing tools for navigation, element interaction, taking screenshots, JavaScript execution, and more.

## Key Features
- **Web Navigation**: Navigate to URLs with timeout control and page readiness checking
- **Element Discovery & Interaction**: Find elements by multiple criteria (text, class, ID, attributes, XPath) and interact with them
- **Screenshots**: Capture full-page screenshots
- **Element Styling**: Retrieve CSS styles and computed style information
- **JavaScript Execution**: Execute custom JavaScript code in browser console
- **Browser Logging**: Access console logs and network request logs with filtering
- **Local Storage Management**: Complete CRUD operations for browser local storage
- **iFrame Support**: Work with elements inside iframes
- **XPath Support**: Use XPath expressions for precise element targeting
- **Chrome Browser Control**: Connect to existing Chrome instances or automatically start new ones

## Project Type
Python-based MCP server using FastMCP framework

## Main Entry Points
- Package entry point: `python -m mcp_server_selenium`
- Script entry point: `selenium-mcp-server` (installed via pip)
- Main module: `src/mcp_server_selenium/__main__.py`
