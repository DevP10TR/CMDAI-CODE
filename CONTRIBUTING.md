# Contributing to CMDAI CODE

Thank you for taking the time to contribute to CMDAI CODE! I welcome community bug reports, feature suggestions, and pull requests.

Please read through this guide before submitting contributions. It outlines how I manage the project, code quality expectations, and licensing terms.

---

## 1. Intellectual Property & Licensing Agreement

CMDAI CODE is governed by a custom non-commercial license (see [LICENSE](LICENSE)). All intellectual property, architecture, code, trademarks, and associated materials remain exclusively my property (**DevP10TR**).

By submitting a Pull Request or contributing code to this repository, you explicitly certify and agree that:
1. **Authorship:** You are the original author of the code you submit, or you have explicit authorization and legal rights to submit it.
2. **Inbound Licensing:** Once merged, any code you submit becomes part of the CMDAI CODE software and is governed by the project's [LICENSE](LICENSE).
3. **Grant of Rights:** You grant me (**DevP10TR**) a perpetual, worldwide, non-exclusive, royalty-free, transferable license to use, modify, adapt, build upon, and manage your contributions as part of this project.
4. **Non-Commercial Terms:** You understand that this project cannot be commercially sold or monetized by third parties without my prior written consent.

---

## 2. Getting Started

### Fork and Branch
1. Fork the repository to your own GitHub account.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/CMDAI-CODE.git
   cd CMDAI-CODE
   ```
3. Create a descriptive branch for your work:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

### Local Development Environment
1. Set up a Python virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   * **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   * **Windows (CMD):**
     ```cmd
     .\.venv\Scripts\activate.bat
     ```
   * **Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```
3. Install project dependencies and testing tools:
   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

---

## 3. Development Guidelines & Code Standards

* **Code Style:** Write clean, readable Python code adhering to [PEP 8](https://peps.python.org/pep-0008/).
* **Scope:** Keep Pull Requests small, atomic, and focused on a single bug fix or feature. Large PRs that touch multiple unrelated areas take longer to review and may be rejected.
* **Testing:**
  * Add or update tests in the `tests/` directory for any new logic or bug fixes.
  * Run the test suite before opening a PR to ensure nothing is broken:
    ```bash
    pytest
    ```
* **Security & Cleanliness:**
  * Never commit secrets, personal API tokens, `config.json`, private sessions, or model artifacts.
  * Verify that `.gitignore` is respected before staging files.

---

## 4. Submitting Pull Requests

1. **Open an Issue First:** For non-trivial features or major architectural changes, please open an Issue first so we can discuss the approach before you invest time writing code.
2. **Clear Commit Messages:** Use concise and descriptive commit messages (e.g. `feat: add model selector support` or `fix: resolve crash on missing config`).
3. **Fill Out the PR Template:** Complete all sections of the provided PR template, including the checklist confirming that tests pass and licensing conditions are accepted.
4. **Be Patient During Review:** I review PRs as soon as possible. I may suggest adjustments or ask for additional tests before merging.

Thank you again for helping me improve CMDAI CODE!
