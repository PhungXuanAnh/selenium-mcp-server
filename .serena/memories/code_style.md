# Code Style and Conventions

## Python Style
- **Python Version**: >= 3.10
- **Type Hints**: Used throughout the codebase (e.g., `Optional[Union[NormalChromeDriver, UndetectedChromeDriver]]`)
- **Docstrings**: Function-level docstrings explaining purpose, parameters, and return values

## Code Organization
- **Module Structure**: Clear separation of concerns
  - `server.py`: Core server logic and global state management
  - `tools/`: Individual tool implementations (navigate, screenshot, logs, etc.)
  - `drivers/`: WebDriver implementations (normal and undetected)
  - `config.py`: Configuration constants

## Naming Conventions
- **Variables**: snake_case (e.g., `driver_instance`, `user_data_dir`)
- **Functions**: snake_case (e.g., `get_driver`, `ensure_driver_initialized`)
- **Classes**: PascalCase (e.g., `NormalChromeDriver`, `UndetectedChromeDriver`)
- **Constants**: UPPER_CASE (e.g., `LOGGING_CONFIG`)

## Function Parameters
- Use descriptive parameter names with type hints
- Default values provided where appropriate
- Optional parameters clearly marked with `Optional[]`

## Error Handling
- Proper exception handling with try/except blocks
- Informative error messages
- Logging at appropriate levels (DEBUG, INFO, ERROR)

## Logging
- Uses Python's standard logging module
- Configured via `LOGGING_CONFIG` in config.py
- Verbosity levels controlled via CLI flags (-v, -vv)
- Log file: `/tmp/selenium-mcp.log`

## Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Explicit imports preferred over wildcard imports
