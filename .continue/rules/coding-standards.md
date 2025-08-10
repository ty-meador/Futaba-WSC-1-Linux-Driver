---
description: Coding Standards
---

# Coding Standards

- **Python**, use ruff for linting and formatting. Do not deviate from ruff settings
- **Imports**: run `ruff check --select I --fix .` to auto-sort.
- **Code organization**: Keep modules focused and cohesive. Split by responsibility when reasoning becomes difficult. All functions MUST be atomic.
- **File/Dir naming**: snake_case for Python; kebab-case for repos.
- **Secrets & PII**: never commit keys/tokens; load via `os.getenv` or `.env`.
