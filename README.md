# Clausi CLI

> Modern command-line interface for auditing software projects against the **EU AI Act** and **GDPR**.

---

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick-start (End Users)](#quick-start-end-users)
4. [Configuration](#configuration)
5. [Scanning Projects](#scanning-projects)
6. [Environment Variables](#environment-variables)
7. [Development & Contribution](#development--contribution)
8. [License](#license)

---

## Overview
Clausi CLI submits source-code and metadata to the hosted Clausi platform
(`https://api.clausi.ai`) which returns a compliance report in the format of
your choice (PDF, HTML, JSON).

Supported regulatory frameworks (built-in):

| Key    | Regulation                                              |
|--------|---------------------------------------------------------|
| EU-AIA | European Union Artificial Intelligence Act (EU AI Act)  |
| GDPR   | General Data Protection Regulation                      |
| ISO-42001 | ISO/IEC 42001 AI Management System |
| HIPAA | Health Insurance Portability and Accountability Act |
| SOC2 | SOC 2 – System and Organization Controls Type 2 |

Additional frameworks can be added on the server side without requiring a
client update.

---

## Installation

| Audience           | Command                                                |
|--------------------|--------------------------------------------------------|
| **End users**      | `pip install clausi`                                   |
| **Contributors**   | `git clone https://github.com/earosenfeld/clausi-cli`<br>`cd clausi-cli`<br>`pip install -e .[dev]` |

Python ≥ 3.8 is required.

---

## Quick-start (End Users)
1. **Interactive wizard** (recommended for the first run)
   ```bash
   clausi setup
   ```
2. **Or set the OpenAI key directly**
   ```bash
   clausi config set --openai-key sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
3. **Run your first scan**
   ```bash
   clausi scan /path/to/project -r EU-AIA
   ```
   The report is saved to `./reports/` by default.

---

## Configuration
All settings live in a single YAML file:

```
Windows : %USERPROFILE%\.clausi\config.yml
macOS/Linux : ~/.clausi/config.yml
```

Typical structure:
```yaml
openai_key: "sk-..."

report:
  company_name: "ACME Corp"
  company_logo: "C:/assets/logo.png"
  template:     "default"   # default | detailed | executive

regulations:
  default: EU-AIA            # default selection for scans
```

Useful commands:
| Command                       | Purpose                                |
|--------------------------------|----------------------------------------|
| `clausi config show`           | Display current configuration          |
| `clausi config set [...]`      | Update one or more fields              |
| `clausi config edit`           | Open the YAML in `$EDITOR` / Notepad   |
| `clausi config path`           | Print the config file location         |

---

## Scanning Projects
Basic syntax:
```bash
clausi scan PATH [options]
```

Common options:
| Flag                         | Description                                              |
|------------------------------|----------------------------------------------------------|
| `-r`, `--regulation`         | Regulation key (repeat for multiple)                     |
| `--mode ai \| full`          | `ai` = lightweight analysis (default), `full` = deep scan |
| `--format pdf \| html \| json`| Report format                                            |
| `--template`                 | Report template (`default`, `detailed`, `executive`)     |
| `-o`, `--output`             | Output directory (otherwise uses config)                 |

Examples:
```bash
# EU AI Act – fast scan
clausi scan . -r EU-AIA --mode ai

# GDPR deep scan, HTML report
clausi scan /srv/app -r GDPR --mode full --format html

# Scan against both regulations, use detailed template
clausi scan ~/project -r EU-AIA -r GDPR --template detailed
```

Upon completion the CLI prints a table of findings and stores:
* `audit.<pdf|html|json>` – the full report
* `audit_metadata.json` – summary of the scan session

---

## Environment Variables
| Variable           | Purpose                                   |
|--------------------|-------------------------------------------|
| `OPENAI_API_KEY`   | Overrides `openai_key` from the YAML file |
| `CLAUSI_OUTPUT_DIR`| Overrides `report.output_dir`             |

Precedence: **CLI flag → environment variable → config file → default**.

---

## Development & Contribution
1. Install dev dependencies as shown in the installation table.
2. Run tests:
   ```bash
   pytest
   ```
3. Lint and format:
   ```bash
   ruff check .    # static analysis
   ruff format .   # auto-format (Black style)
   ```
4. Submit pull requests against `main`.

---

## License
Licensed under the MIT License – © Clausi 2025.
