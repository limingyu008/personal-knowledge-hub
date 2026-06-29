# Development Guide

## Repository Layout

```text
backend/              FastAPI backend
frontend/             Vue management console
browser-extension/    Chrome / Edge extension
docs/                 Project documents
```

## Backend Development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload
```

Run a syntax check:

```bash
cd backend
python3 -m py_compile app/*.py
```

## Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Build:

```bash
npm run build
```

## Browser Extension Development

```bash
cd browser-extension
npm install
npm run build
```

Load `browser-extension/dist` from Chrome / Edge extension management page.

## Commit Style

Recommended commit format:

```text
feat(backend): add chroma vector retrieval
feat(frontend): add model config console
feat(extension): save selected page to knowledge hub
fix(backend): handle document parse failure
docs: update startup guide
```

Prefer feature-based commits instead of tool-based commits. For example, one feature commit may include backend, frontend, browser extension, and documentation changes.

## Branching

For solo development, keep it simple:

```text
main                  stable runnable version
feature/<topic>       feature work
fix/<topic>           bug fix work
```

## Before Pushing

Check the following before pushing to GitHub:

```bash
git status --short
```

Do not commit:

- API keys
- `.env`
- `backend/data/`
- `node_modules/`
- `dist/`
- real personal documents
