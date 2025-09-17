# Publishing a Python Package to PyPI: Complete Guide

This document provides a comprehensive step-by-step guide for publishing Python packages to the Python Package Index (PyPI).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Configuration Files](#configuration-files)
- [Building the Package](#building-the-package)
- [Setting Up PyPI Account](#setting-up-pypi-account)
- [Publishing to PyPI](#publishing-to-pypi)
- [Testing Your Package](#testing-your-package)
- [Version Management](#version-management)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Prerequisites

Before you start, ensure you have:

1. **Python 3.7+** installed
2. **uv** package manager (recommended) or **pip** and **build**
3. A **PyPI account** (create at https://pypi.org/account/register/)
4. Your project code ready

### Installing Required Tools

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or install traditional tools
pip install build twine
```

## Project Structure

Your project should have a structure like this:

```
your-project/
├── your_package/
│   ├── __init__.py
│   └── main.py
├── tests/
│   └── test_main.py
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

## Configuration Files

### 1. pyproject.toml

This is the main configuration file for modern Python packages:

```toml
[project]
name = "your-package-name"
version = "0.1.0"
description = "A brief description of your package"
readme = "README.md"
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
license = {text = "MIT"}
requires-python = ">=3.8"
dependencies = [
    "requests>=2.25.0",
    "click>=8.0.0",
]
keywords = ["python", "package", "example"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

[project.urls]
"Homepage" = "https://github.com/yourusername/your-package"
"Bug Reports" = "https://github.com/yourusername/your-package/issues"
"Source" = "https://github.com/yourusername/your-package"

[project.scripts]
your-command = "your_package.main:main"

[project.optional-dependencies]
dev = [
    "pytest>=6.0",
    "black>=21.0.0",
    "flake8>=3.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["your_package"]
```

### 2. README.md

Create a comprehensive README with:
- Project description
- Installation instructions
- Usage examples
- Contributing guidelines

### 3. LICENSE

Choose an appropriate license (MIT, Apache 2.0, GPL, etc.) and include the license file.

## Setting Up PyPI Account

### 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Fill in your details and verify your email
3. Enable two-factor authentication (recommended)

### 2. Generate API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Set the scope (recommend starting with "Entire account")
4. Copy the token (starts with `pypi-`)

### 3. Configure Authentication

**Option A: Environment Variable (Recommended)**
```bash
export UV_PUBLISH_TOKEN=pypi-your-actual-token-here
```

**Option B: Store in credentials file**
```bash
# Create ~/.pypirc
cat > ~/.pypirc << EOF
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-your-actual-token-here
EOF
```

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

## Resources

- [PyPI Official Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [PEP 621 - pyproject.toml](https://peps.python.org/pep-0621/)
- [Semantic Versioning](https://semver.org/)
- [Choose a License](https://choosealicense.com/)