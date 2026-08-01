# `frontend/` (renamed)

This folder has been renamed to **`multilingual_guidance_ui/`** as of
Phase B — see the root `README.md` for the full rename mapping and
rationale. `frontend/index.html` here just redirects there for anyone who
still opens this path directly.

Serve the real UI from its new location instead:

```bash
cd multilingual_guidance_ui && python -m http.server 8080
```
