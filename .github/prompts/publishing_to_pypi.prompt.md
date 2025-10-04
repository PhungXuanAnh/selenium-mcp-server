---
mode: agent
---

# AI Agent Guide: Publishing Python Package to PyPI

This document provides structured instructions for AI agents (like GitHub Copilot) to publish Python packages to PyPI with proper changelog management and version control.

**Target Project**: https://pypi.org/project/mcp-server-selenium/
**Repository**: https://github.com/PhungXuanAnh/selenium-mcp-server

## Agent Workflow Summary

When user requests PyPI publishing, follow this structured approach:

1. 🔍 **Examine Project** - Check pyproject.toml, version, and current state
2. 📝 **Create/Update Changelog** - Maintain CHANGELOG.md with proper format  
3. 🔧 **Update Metadata** - Ensure pyproject.toml points to GitHub changelog
4. 📦 **Build & Publish** - Create distribution files and upload to PyPI
5. ✅ **Verify & Tag** - Confirm publication and create git tags

## Agent Task Checklist

Use `manage_todo_list` tool to track progress with these tasks:
- [ ] Examine project configuration (pyproject.toml, version, structure)
- [ ] Create/update CHANGELOG.md file (Keep a Changelog format)
- [ ] Update pyproject.toml metadata (changelog URL to GitHub)
- [ ] Build and publish to PyPI (handle version conflicts)
- [ ] Verify publication and create git tags

## Prerequisites for Agent

Agent should verify these exist:

1. **Python 3.10+** installed and configured
2. **build** and **twine** packages available
3. **PyPI API token** ready for authentication
4. **Git repository** with proper structure and permissions
5. **pyproject.toml** with correct metadata

### Agent Environment Setup

```bash
# Configure Python environment
configure_python_environment

# Install required packages if needed
install_python_packages(["build", "twine"])
```

### Installing Required Tools

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or install traditional tools
pip install build twine
```

## Agent Actions: Step-by-Step Instructions

### Step 1: Examine Project Configuration

**Agent Tools to Use:**
- `read_file` - Check pyproject.toml for version and metadata
- `mcp_gitkraken_bun_git_log_or_diff` - Check recent commits for context
- `run_in_terminal` - Check existing git tags: `git tag --sort=-version:refname`

**Key Checks:**
- Current version in pyproject.toml
- Existing changelog structure  
- PyPI metadata completeness
- Git repository state

### Step 2: Create/Update CHANGELOG.md

**Agent Action:** Use `create_file` or `replace_string_in_file`

**Required Format:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), 
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [X.Y.Z] - YYYY-MM-DD
### Added
- New features and enhancements

### Changed  
- Changes in existing functionality

### Fixed
- Bug fixes and corrections

### Removed
- Removed or deprecated features
```

### Step 3: Update pyproject.toml Metadata

**Agent Action:** Ensure changelog URL points to GitHub:

```toml
[project.urls]
"Homepage" = "https://github.com/PhungXuanAnh/selenium-mcp-server"
"Bug Reports" = "https://github.com/PhungXuanAnh/selenium-mcp-server/issues"  
"Source Code" = "https://github.com/PhungXuanAnh/selenium-mcp-server"
"Documentation" = "https://github.com/PhungXuanAnh/selenium-mcp-server#readme"
"Changelog" = "https://github.com/PhungXuanAnh/selenium-mcp-server/blob/master/CHANGELOG.md"
```

### Step 4: Build and Publish Process

**Agent Tools Required:**
- `configure_python_environment` - Set up Python environment
- `run_in_terminal` - Execute build and publish commands

**Build Commands:**
```bash
# Clean previous builds  
rm -rf dist/ build/ *.egg-info/

# Build distribution files
python -m build
# or /usr/bin/python3 -m build

# Upload to PyPI  
python -m twine upload dist/*
# or /usr/bin/python3 -m twine upload dist/*
```

**Handle Version Conflicts:**
If version exists on PyPI:
1. Increment version in pyproject.toml (e.g., 0.1.5 → 0.1.6)
2. Update CHANGELOG.md with new version entry
3. Rebuild and republish

### Step 5: Git Management  

**Agent Actions:**
```bash
# Add and commit changes
git add .
git commit -m "chore: bump version to X.Y.Z and update changelog"

# Create version tag
git tag vX.Y.Z

# Push changes and tags
git push origin master
git push origin vX.Y.Z
```

**Use MCP Git tools:**
- `mcp_gitkraken_bun_git_add_or_commit`
- `mcp_gitkraken_bun_git_push`

## Expected Project Structure

This selenium-mcp-server project has:

```
selenium-mcp-server/
├── src/mcp_server_selenium/
│   ├── __init__.py
│   ├── __main__.py  
│   └── ...
├── pyproject.toml
├── README.md
├── CHANGELOG.md  
├── LICENSE
└── dist/ (created during build)
```

## Agent Tasks: Configuration Management

### Task 1: Verify pyproject.toml Structure

Agent should check/update the main configuration file:

**Required fields for this project:**

```toml
## Troubleshooting for Agents

### Common Issues and Solutions

**1. Version Already Exists Error**
```
ERROR: HTTPError: 400 Bad Request - File already exists
```
**Agent Solution:**
1. Increment version in pyproject.toml
2. Update CHANGELOG.md with new version
3. Rebuild and republish

**2. Build Module Not Found**
```
python: No module named build
```
**Agent Solutions:**
- Try system Python: `/usr/bin/python3 -m build`
- Install build: `pip install build` or use `install_python_packages`

**3. Authentication Issues**
```  
ERROR: Invalid credentials
```
**Agent Action:** User needs to provide PyPI API token when prompted

**4. Permission Denied**
```
ERROR: 403 Forbidden
```
**Check:** User has proper PyPI account permissions for package

### Agent Best Practices

**1. Always Use Todo Lists**
```python
manage_todo_list(operation="write", todoList=[
    {"id": 1, "title": "Examine project", "status": "not-started"},
    {"id": 2, "title": "Create changelog", "status": "not-started"},
    # ... more tasks
])
```

**2. Version Increment Strategy**
- Patch: 0.1.5 → 0.1.6 (bug fixes, minor changes)
- Minor: 0.1.6 → 0.2.0 (new features, backward compatible)  
- Major: 0.2.0 → 1.0.0 (breaking changes)

**3. Changelog Entry Template**
```markdown
## [X.Y.Z] - YYYY-MM-DD
### Added
- Comprehensive CHANGELOG.md file following conventional format
- Updated PyPI metadata to point to GitHub changelog

### Changed  
- Updated changelog URL in pyproject.toml to point to GitHub CHANGELOG.md file
```

**4. Verification Steps**
- Check PyPI page: `https://pypi.org/project/mcp-server-selenium/`
- Verify changelog link: `https://github.com/PhungXuanAnh/selenium-mcp-server/blob/master/CHANGELOG.md`
- Test installation: `pip install mcp-server-selenium`
```

### Task 2: Create/Update CHANGELOG.md

Agent must maintain a proper changelog following [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [X.Y.Z] - YYYY-MM-DD
### Added
- New features

### Changed
- Changes in existing functionality

### Fixed
- Bug fixes

### Removed
- Removed features
```

**Agent Action**: Use `create_file` or `replace_string_in_file` to maintain changelog

### Task 3: Verify Project Files

Agent should confirm these exist:
- ✅ README.md (comprehensive documentation)
- ✅ LICENSE (MIT license for this project)
- ✅ pyproject.toml (proper metadata)
- ✅ CHANGELOG.md (version history)

## Quick Reference for Agents

### Essential Commands Sequence

```bash
# 1. Configure environment
configure_python_environment

# 2. Check current state  
read_file(pyproject.toml)
git tag --sort=-version:refname

# 3. Build package
python -m build
# or /usr/bin/python3 -m build  

# 4. Upload to PyPI
python -m twine upload dist/*
# User will be prompted for API token

# 5. Git operations
git add .
git commit -m "chore: bump version and update changelog"
git tag vX.Y.Z
git push origin master vX.Y.Z
```

### MCP Tools Usage

**Git Operations:**
```python
# Add and commit
mcp_gitkraken_bun_git_add_or_commit(action="add", directory=project_path)
mcp_gitkraken_bun_git_add_or_commit(action="commit", message="...", directory=project_path)

# Push changes
mcp_gitkraken_bun_git_push(directory=project_path)
```

**File Operations:**
```python  
# Create changelog
create_file(filePath="CHANGELOG.md", content="...")

# Update pyproject.toml  
replace_string_in_file(filePath="pyproject.toml", oldString="...", newString="...")
```

### Success Criteria

Agent should verify:
- ✅ Package published to PyPI successfully
- ✅ Changelog URL works on PyPI project page
- ✅ Git tags created and pushed
- ✅ Version incremented properly
- ✅ CHANGELOG.md follows proper format

## Building the Package

### 1. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info/
```

### 2. Build Distribution Files

**Using uv (Recommended):**
```bash
uv build
```

**Using traditional tools:**
```bash
python -m build
```

This creates:
- `dist/your_package-0.1.0.tar.gz` (source distribution)
- `dist/your_package-0.1.0-py3-none-any.whl` (wheel distribution)

### 3. Verify Build

```bash
ls -la dist/
```

## Publishing to PyPI

### 1. Test on TestPyPI First (Recommended)

TestPyPI is a separate instance for testing:

```bash
# For TestPyPI, you need a separate token from https://test.pypi.org/
uv publish --publish-url https://test.pypi.org/legacy/ --token your-testpypi-token
```

Test installation:
```bash
pip install -i https://test.pypi.org/simple/ your-package-name
```

### 2. Publish to Production PyPI

**Using uv:**
```bash
uv publish
```

**Using twine:**
```bash
twine upload dist/*
```

### 3. Verify Publication

1. Check your package page: `https://pypi.org/project/your-package-name/`
2. Test installation: `pip install your-package-name`

## Testing Your Package

### 1. Install in Clean Environment

```bash
# Create virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install your package
pip install your-package-name

# Test it works
your-command --help
```

### 2. Test Installation Methods

```bash
# Install from PyPI
pip install your-package-name

# Install specific version
pip install your-package-name==0.1.0

# Install with extras
pip install your-package-name[dev]
```

## Version Management

### 1. Semantic Versioning

Follow semantic versioning (SemVer):
- `MAJOR.MINOR.PATCH`
- `1.0.0` → `1.0.1` (patch: bug fixes)
- `1.0.0` → `1.1.0` (minor: new features, backward compatible)
- `1.0.0` → `2.0.0` (major: breaking changes)

### 2. Update Version

1. Update version in `pyproject.toml`:
   ```toml
   version = "0.1.1"
   ```

2. Create git tag:
   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```

3. Rebuild and republish:
   ```bash
   rm -rf dist/
   uv build
   uv publish
   ```

## Troubleshooting

### Common Issues

1. **403 Forbidden Error**
   - Check your API token is correct
   - Ensure you have permissions for the package name
   - Package name might already exist

2. **Package Name Conflicts**
   ```bash
   # Check if name exists
   curl -s https://pypi.org/pypi/your-package-name/json
   ```

3. **Build Failures**
   - Check `pyproject.toml` syntax
   - Ensure all required files exist
   - Verify Python version compatibility

4. **Import Errors After Installation**
   - Check package structure
   - Verify `__init__.py` files exist
   - Ensure entry points are correct

### Debug Commands

```bash
# Check package metadata
uv build --verbose

# Validate distribution
twine check dist/*

# Test local installation
pip install -e .
```

## Best Practices

### 1. Package Naming

- Use lowercase letters, numbers, and hyphens
- Be descriptive but concise
- Check availability on PyPI first
- Avoid trademarked names

### 2. Version Control

- Tag releases in git
- Maintain a CHANGELOG.md
- Use semantic versioning
- Don't reuse version numbers

### 3. Documentation

- Include comprehensive README
- Add docstrings to functions/classes
- Provide usage examples
- Document installation requirements

### 4. Testing

- Include unit tests
- Test on multiple Python versions
- Use CI/CD for automated testing
- Test installation in clean environments

### 5. Security

- Use API tokens, not username/password
- Enable 2FA on PyPI account
- Regularly rotate API tokens
- Review package permissions

### 6. Maintenance

- Respond to issues promptly
- Keep dependencies updated
- Monitor security vulnerabilities
- Deprecate old versions gracefully

## Automation with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@v1.5.0
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

## Conclusion

Publishing to PyPI involves:

1. ✅ Proper project structure
2. ✅ Correct `pyproject.toml` configuration
3. ✅ PyPI account with API token
4. ✅ Building distribution files
5. ✅ Testing on TestPyPI (optional but recommended)
6. ✅ Publishing to PyPI
7. ✅ Verification and testing

Following this guide ensures your package is properly published and accessible to the Python community.

---

## 🤖 AGENT SUMMARY: Complete Workflow

When user says "help me publish to PyPI" or similar, follow this exact sequence:

### 1. Initialize Todo List
```python
manage_todo_list(operation="write", todoList=[
    {"id": 1, "title": "Examine project configuration", "description": "Check pyproject.toml, version, and current state", "status": "in-progress"},
    {"id": 2, "title": "Create CHANGELOG.md file", "description": "Create proper changelog following conventional format", "status": "not-started"},  
    {"id": 3, "title": "Update pyproject.toml metadata", "description": "Ensure PyPI metadata includes changelog URL pointing to GitHub", "status": "not-started"},
    {"id": 4, "title": "Build and publish to PyPI", "description": "Build package and upload using API token", "status": "not-started"},
    {"id": 5, "title": "Verify publication", "description": "Check package published with correct metadata", "status": "not-started"}
])
```

### 2. Core Agent Actions
```python
# Step 1: Examine
read_file("pyproject.toml", startLine=1, endLine=50)
mcp_gitkraken_bun_git_log_or_diff(action="log", directory=project_path)
run_in_terminal("git tag --sort=-version:refname", explanation="Check existing tags")

# Step 2: Create/Update Changelog  
create_file(filePath="CHANGELOG.md", content=changelog_template)

# Step 3: Update Metadata
replace_string_in_file(
    filePath="pyproject.toml",
    oldString='"Changelog" = "https://github.com/.../releases"',
    newString='"Changelog" = "https://github.com/.../blob/master/CHANGELOG.md"'
)

# Step 4: Build & Publish
configure_python_environment()
run_in_terminal("/usr/bin/python3 -m build", explanation="Build package")
run_in_terminal("/usr/bin/python3 -m twine upload dist/*", explanation="Upload to PyPI")

# Step 5: Git Operations
mcp_gitkraken_bun_git_add_or_commit(action="add", directory=project_path)
mcp_gitkraken_bun_git_add_or_commit(action="commit", message="chore: bump version and update changelog", directory=project_path)
run_in_terminal("git tag vX.Y.Z", explanation="Create version tag")
mcp_gitkraken_bun_git_push(directory=project_path)
```

### 3. Key Checkpoints
- ✅ Version conflicts → increment version in pyproject.toml  
- ✅ Build module missing → use system Python `/usr/bin/python3`
- ✅ Authentication → user provides PyPI token when prompted
- ✅ Verification → check PyPI page and changelog link

### 4. Final Deliverables
- 📦 Package published to PyPI
- 📝 CHANGELOG.md created with proper format
- 🔗 PyPI metadata pointing to GitHub changelog  
- 🏷️ Git tags created and pushed
- ✅ All todos marked completed

**Remember:** Always use `manage_todo_list` to track progress and mark todos as completed when done!

## Resources

- [PyPI Official Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/)
- [MCP Server Selenium Project](https://github.com/PhungXuanAnh/selenium-mcp-server)
