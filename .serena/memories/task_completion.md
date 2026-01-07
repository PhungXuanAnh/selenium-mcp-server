# Task Completion Guidelines

## When a Task is Completed

### Code Quality Checks
Before considering a task complete, ensure:

1. **Code runs without errors**
   - Test the changes manually if possible
   - Check logs for any warnings or errors

2. **Type hints are correct**
   - All function parameters have type hints
   - Return types are specified

3. **Docstrings are present**
   - Functions have docstrings explaining purpose, parameters, and return values
   - Follow existing docstring format in the codebase

4. **Code follows conventions**
   - snake_case for functions and variables
   - PascalCase for classes
   - UPPER_CASE for constants

5. **Error handling is appropriate**
   - Proper exception handling where needed
   - Informative error messages

### Testing
- **Manual Testing**: Use MCP Inspector or direct tool testing script
  ```bash
  # For MCP Inspector
  make inspector
  # Access at http://127.0.0.1:6274/#tools
  
  # For direct testing
  .venv/bin/python -i test_call_tools_directly.py
  ```

- **Integration Testing**: Test with actual MCP clients if possible

### No Automated Checks (Currently)
**Note**: This project does NOT have:
- Unit tests
- Automated linting (no flake8, black, ruff, etc.)
- Automated formatting
- Pre-commit hooks
- CI/CD pipelines

### Documentation
- Update README.md if adding new features or changing behavior
- Update CHANGELOG.md for version-worthy changes
- Add docstrings to new functions and classes

### Before Committing
1. **Verify Changes**
   - Review git diff to ensure only intended changes are included
   - Check for any debug code or print statements that should be removed

2. **Test the Changes**
   - Run the server and test affected functionality
   - Check logs for any issues

3. **Update Documentation**
   - If adding new features, update README.md
   - Add any new memory files if significant architectural changes

## Minimal Requirements
Since there are no automated tests or linting:
- Code must run without Python syntax errors
- Follow existing code patterns and style
- Manual testing is the primary verification method
