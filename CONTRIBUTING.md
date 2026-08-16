# Contributing to SMarTrPlay

First off — **thank you** for taking the time to contribute! 🎉

SMarTrPlay is an open-source project and we welcome contributions of all kinds: bug reports, feature requests, code, documentation, translations, and more.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Code Style & Standards](#code-style--standards)
- [Pull Request Process](#pull-request-process)
- [Commit Message Convention](#commit-message-convention)
- [Issue Guidelines](#issue-guidelines)
- [Testing](#testing)
- [Release Process](#release-process)

---

## Code of Conduct

Be respectful, inclusive, and constructive. We follow a simple principle:

> **Treat others as you want to be treated.**

Harassment, discrimination, or personal attacks will not be tolerated.

---

## How Can I Contribute?

### 🐛 Reporting Bugs

1. Check existing [Issues](../../issues) to avoid duplicates
2. Open a new issue using the **Bug Report** template
3. Include:
   - OS and version (Linux distribution / Windows version)
   - Python version (`python3 --version`)
   - SMarTrPlay version
   - Steps to reproduce
   - Expected vs. actual behavior
   - Log output (if available)

### 💡 Suggesting Features

1. Open a new issue using the **Feature Request** template
2. Describe the feature and its use case
3. If possible, sketch a rough UI mockup or describe the expected workflow

### 📝 Improving Documentation

- Fix typos, improve clarity, add examples
- Submit a PR with your changes

### 🔧 Writing Code

- Pick an issue labeled `good first issue` or `help wanted`
- Fork the repo, create a branch, make your changes
- Submit a Pull Request (see [Pull Request Process](#pull-request-process))

### 🌍 Translating

- We welcome translations for the UI and documentation
- Contact us via [Telegram](https://t.me/SMartrAgents) if you'd like to help

---

## Development Setup

### Prerequisites

- Python 3.8+
- PyQt5 (`pip install PyQt5`)
- ffplay (FFmpeg suite — `sudo apt install ffmpeg` on Debian/Ubuntu)
- SQLite3 (usually pre-installed)
- Git

### Clone & Run

```bash
git clone https://github.com/SMartrAgents/SMarTrPlay.git
cd SMarTrPlay
pip install -r requirements.txt
python main.py
```

### Project Structure

```
SMarTrPlay/
├── main.py              # Entry point
├── src/                 # Source code
│   ├── ui/              # PyQt5 UI components
│   ├── player/          # ffplay integration & playback
│   ├── providers/        # Xtream Codes API & M3U parsing
│   ├── models/          # Data models (channels, VOD, series)   ├── database/        # SQLite layer (favorites, history, cache)
│   ├── epg/             # EPG parsing & display
│   ├── cast/            # DLNA / UPnP casting
│   ├── remote/          # Web remote control server
│   ├── recording/       # Stream recording
│   ├── subtitles/       # Subtitle loading & rendering
│   └── utils/           # Shared utilities
├── assets/             # Icons, themes, brand assets
├── docs/               # Documentation & screenshots
├── build/              # Build scripts & output
└── tests/              # Unit & integration tests
```

---

## Code Style & Standards

### Python

- Follow **PEP 8** with minor exceptions (line length max 120)
- Use **4 spaces** for indentation (no tabs)
- Use **type hints** where practical
- Prefer **explicit** over implicit
- Keep functions small and focused (max ~50 lines)
- Document public functions with **docstrings** (Google style)

```python
def get_channel_list(provider_id: str, category: str = "all") -> list[Channel]:
    """Retrieve channels for a given provider and category.
    
    Args:
        provider_id: The provider's unique identifier.
        category: Channel category filter (default: "all").
    
    Returns:
        List of Channel objects matching the criteria.
    """
    ...
```

### Naming Conventions

- **Variables / functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_prefixed_with_underscore`
- **Files**: `snake_case.py`

### UI / PyQt5

- Use **object names** (`setObjectName()`) for all widgets — enables QSS styling
- Follow the **SMarTr brand design** (dark blue `#0A1A2F`, cyan `#00D9FF`)
- Keep UI responsive — offload heavy operations to **QThread** or **QRunnable**
- Use **signals/slots** for inter-component communication
- Avoid blocking the main thread

### Imports

```python
# Standard library
import os
import json
from pathlib import Path

# Third-party
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt, QThread

# Local
from src.providers.xtream import XtreamClient
from src.models.channel import Channel
```

---

## Pull Request Process

### 1. Before You Start

- Check existing PRs to avoid duplicate work
- For major changes, open an issue first to discuss the approach

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bugfix-name
```

### 3. Make Your Changes

- Write clean, well-documented code
- Add or update tests where applicable
- Update documentation if behavior changes

### 4. Test Locally

```bash
# Run unit tests
python -m pytest tests/ -v

# Test the application manually
python main.py

# Test on both Linux and Windows if possible
```

### 5. Commit Your Changes

Follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```bash
git commit -m "feat: add DLNA device discovery"
git commit -m "fix: resolve EPG timezone offset on Linux"
git commit -m "docs: update installation instructions for Flatpak"
```

### 6. Push & Open a PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub using the **PR Template**.

### 7. PR Review

- Address review feedback promptly
- Keep the PR focused — one feature/fix per PR
- Squash commits if asked by a maintainer
- A maintainer will merge once approved

---

## Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Description |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style (formatting, no logic change) |
| `refactor` | Code refactoring (no feature/fix) |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system or dependencies |
| `ci` | CI/CD configuration |
| `chore` | Maintenance tasks |

**Format:**
```
<type>: <description>

[optional body]

[optional footer]
```

**Examples:**
```
feat: add picture-in-picture mode for live streams

fix: resolve series episode order for Xtream providers

docs: add keyboard shortcuts section to README
```

---

## Issue Guidelines

### Bug Reports

- Use the **Bug Report** template
- Be specific and reproducible
- Include logs from `~/.cache/smartrplay/smartrplay.log`

### Feature Requests

- Use the **Feature Request** template
- Explain the **why** (use case), not just the **what**
- If you're willing to implement it, say so

### Duplicate Issues

- Search before opening
- If you find a duplicate, comment with "Duplicate of #XXX"

---

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_xtream.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Writing Tests

- Use `pytest` framework
- Aim for meaningful coverage of core modules:
  - Provider API (Xtream, M3U)
  - Database operations
  - EPG parsing
  - Cast/DLNA discovery
- Mock external dependencies (network, ffplay process)
- Test edge cases (empty playlists, invalid URLs, missing EPG data)

---

## Release Process

Releases are automated via GitHub Actions:

1. A tag `vX.Y.Z` is pushed
2. GitHub Actions builds DEB, AppImage, and Windows EXE
3. A GitHub Release is created automatically with release notes
4. Artifacts are attached to the release

Maintainers handle tagging. Contributors don't need to worry about this.

---

## Getting Help

- 💬 **Telegram**: [@SMartrAgents](https://t.me/SMartrAgents)
- 📧 **Email**: akatongie@smartragents.ai
- 🐛 **Issues**: [GitHub Issues](../../issues)

---

<div align="center">

**Thank you for contributing to SMarTrPlay!** 🚀

© 2026 SMartrAgents / Karl Heinz Marko — [smartragents.ai](https://smartragents.ai)

</div>
