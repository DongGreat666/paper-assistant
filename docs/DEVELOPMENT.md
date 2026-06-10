# Development

## Python application

Create an environment, install dependencies, copy `.env.example` to `.env`,
then start the app:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\reflex.exe run
```

The app is available at <http://localhost:3000/>.

This repository is designed for trusted, single-user local use. Do not expose
the development server directly to a public network. Before any multi-user or
internet-facing deployment, add authentication, authorization, per-user data
isolation, upload limits, SSRF protection, resource limits, and managed secret
storage. See [SECURITY.md](../SECURITY.md).

Always use the project `.venv`. The Marker dependency set intentionally pins
compatible `openai`, `anthropic`, and `Pillow` versions. Installing unrelated
automation packages into the same environment can make Marker unusable.

`requirements.lock.txt` records the fully resolved environment used for
verification. Refresh it only after `pip check` and the application import both
pass.

## PDF reader frontend

The committed reader build lives under `assets/pdf-reader/`. Install frontend
dependencies only when changing the reader source:

```powershell
Set-Location pdf-reader
npm ci
npm run build
```

`pdf-reader/node_modules/` is intentionally not stored in the repository.

## Local runtime data

The following directories are intentionally excluded from Git:

- `data/`: local settings, secrets, history, and caches.
- `models/`: Marker model cache.
- `uploaded_files/`: imported papers and generated outputs.
- `.web/`: generated Reflex frontend.
- `logs/` and `artifacts/`: disposable diagnostics and test output.

Do not delete `models/` or `uploaded_files/` during routine cleanup.
