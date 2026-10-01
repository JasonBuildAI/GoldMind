# Contributing to GoldMind

> 🌐 [中文](./CONTRIBUTING.md) | **English**

Thank you for considering contributing to GoldMind!

## How to contribute

- **Report a bug** - open an issue describing the problem
- **Suggest a feature** - open an issue with the idea
- **Write code** - send a pull request
- **Improve the docs** - both language versions live in this repo; keep them in sync

## Quick start

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/GoldMind.git
cd GoldMind
```

### 2. Set up a development environment

See the quick-start guide in [README_EN.md](README_EN.md)
(Chinese: [README.md](README.md)).

### 3. Create a branch

```bash
# feature branch
git checkout -b feature/short-name

# fix branch
git checkout -b fix/short-description
```

## Development conventions

### Tech stack

**Backend**
- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite (default, a single file; MySQL optional)

**Frontend**
- React 19
- TypeScript 5.9 (`strict: true`)
- Tailwind CSS 3

**AI**
- Any OpenAI-compatible LLM endpoint (OpenAI / DeepSeek / Qwen / Kimi / Ollama / Xiaomi MiMo, …;
  configuration is in `README_EN.md`) - every call goes through `backend/app/services/llm_provider.py`

### Code style

#### Python

- Follow PEP 8
- Use type hints
- Write docstrings

#### TypeScript

- Strict mode is on (`strict: true` in `tsconfig.app.json`)
- Meaningful variable names
- Comment complex logic

### Commit messages

The **single source of truth for the prefixes is rule 2 in [`AGENTS.md`](AGENTS.md)**; the common ones are:

```
feat: add a feature      fix: fix a bug
refactor: restructure    perf: speed something up
docs: update docs        test: add tests
chore: build/deps        build: build system      ci: CI config
```

One prefix per commit, one concern per commit; the first line must say what changed.
Messages are written **in English** (see `AGENTS.md`).

### Definition of done

A change is done when the gate is green: tests + static checks + build, with the exact
commands in the "Common commands" section of [README_EN.md](README_EN.md).
If you add a guard test, break the behaviour it guards once and confirm the test turns red -
a test that still passes on broken code is not a test.

## Project structure

```
GoldMind/
├── app/                    # frontend (React + TypeScript)
│   ├── src/
│   │   ├── sections/      # page sections
│   │   ├── components/    # reusable components
│   │   └── services/      # API client
│   └── package.json
├── backend/               # backend (FastAPI + Python)
│   ├── app/
│   │   ├── services/      # business logic (incl. llm_provider, quant/)
│   │   ├── routers/       # API routes
│   │   ├── models/        # data models
│   │   └── utils/         # rate limiting, time helpers
│   ├── scripts/           # migrations, doc generators, dev tools
│   ├── tests/             # unit / integration / e2e
│   └── requirements.txt
├── docs/                  # product direction, architecture, API, secrets
│   └── en/                # English mirrors
└── README.md / README_EN.md
```

## Security rules

**Important**: never commit any of the following

- LLM API keys (any provider)
- Database passwords
- Private keys or certificates

**Do this instead**
- Keep secrets in `.env` files
- Make sure `.env` is in `.gitignore`
- Check `git diff` before committing

**Already automated**: `backend/tests/unit/test_no_secrets_in_repo.py` scans every
version-controlled file; key-shaped strings, personal email addresses and QQ numbers turn
the gate red. It guards "from here on" - a leak already in history can only be removed by
rewriting it (see `docs/10-密钥与隐私.md`, English: `docs/en/secrets-and-privacy.md`).

## Reporting a bug

Include in the issue:

- What went wrong
- Steps to reproduce
- Expected vs. actual behaviour
- Environment (OS, Python/Node versions)
- Error logs

## Suggesting a feature

- The use case
- Your proposed approach
- Alternatives you considered (if any)

## Licence

By contributing, you agree that your contributions are licensed under the MIT Licence.

---

Thanks for contributing to GoldMind!
