# `backend/` (renamed)

This folder has been renamed to **`system_orchestrator/`** as of Phase B —
see the root `README.md` for the full rename mapping and rationale.

`backend/app` is kept here as a thin backward-compatible alias
(`backend/app/__init__.py`) so the old run command still works:

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

New code and docs should use the new location instead:

```bash
cd system_orchestrator && uvicorn app.main:app --reload --port 8000
```
