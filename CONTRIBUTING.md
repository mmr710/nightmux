# Contributing to nightmux

First off, thank you for considering contributing to `nightmux`!

`nightmux` is built to be a small, highly opinionated, zero-dependency tool that does one thing exceptionally well: bridging asynchronous AI coding sessions to Telegram.

## Governance Model

This project operates under a **Benevolent Dictator for Life (BDFL)** model. The creator and lead maintainer (@mmr710) retains the final say on all architectural decisions, feature inclusions, and the overarching roadmap of the project. 

The goal of this governance is to ensure the project remains lightweight, secure, and focused on its core philosophy without succumbing to feature bloat, competing standards, or scope creep.

## How to Contribute

### 1. Discuss Before Building
**Do not submit large Pull Requests without prior discussion.** 
If you have a feature idea, an architectural change, or a major refactor in mind, please open an **Issue** first to discuss it with the maintainer. Large PRs that drop out of nowhere without prior alignment will be rejected to save everyone's time.

### 2. Philosophy & Design Constraints
If you are submitting code, it must align with the core architectural decisions outlined in `ARCHITECTURE.md`:
- **Zero dependencies:** Everything must run using the Python 3.8+ standard library. No exceptions.
- **Local execution:** It must remain capable of running entirely on the user's local machine without requiring external cloud relays.
- **Keep it small:** The daemon is a single file designed to be readable in an afternoon. Keep logic simple and explicitly document any cleverness.

### 3. Submitting Pull Requests
- Keep PRs strictly focused on a single issue or feature.
- Ensure the code passes all existing self-checks by running `python3 nightmux.py --selfcheck` (and the same flag on the hook scripts).
- Update the `CHANGELOG.md` if necessary.

By contributing to this project, you agree that your contributions will be licensed under its MIT License.
