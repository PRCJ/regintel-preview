# Testing guide (unit, integration, Playwright)

For the **testing team**. Two stacks:

| Layer | Tool | What it covers |
|-------|------|----------------|
| Unit + integration | **pytest** | Scoring, crawl helpers, Eva API, published JSON |
| UI / E2E | **Playwright** (`e2e/`) | Home, Documents, Horizon, Pipeline, Eva |

## One-time setup

```bash
# Python
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Playwright (Node) — browsers + OS libs
cd e2e
npm install
npx playwright install --with-deps chromium
cd ..
```

`--with-deps` installs packages such as `libnspr4`. If Chromium fails with `libnspr4.so` and you cannot use sudo:

```bash
sudo apt-get update && sudo apt-get install -y libnspr4 libnss3 libatk-bridge2.0-0 libdrm2 libgbm1 libxkbcommon0
# or without sudo:
mkdir -p /tmp/pw-libs && cd /tmp/pw-libs && apt-get download libnspr4 libnss3 libasound2t64 libgbm1
for deb in *.deb; do dpkg-deb -x "$deb" /tmp/pw-libs/root; done
export LD_LIBRARY_PATH=/tmp/pw-libs/root/usr/lib/x86_64-linux-gnu
```

## Commands

```bash
# All Python tests
.venv/bin/pytest

# Unit only / integration only
.venv/bin/pytest -m unit
.venv/bin/pytest -m integration

# With coverage
.venv/bin/pytest --cov=collector --cov=tools --cov-report=term-missing

# Playwright against local web/ (starts http.server :4173)
cd e2e && npm test

# Headed / inspector
cd e2e && npm run test:headed
cd e2e && npm run test:ui

# Against the hosted preview
BASE_URL=https://roomcraft-e1312--rhandar-level-56hqwy9h.web.app cd e2e && npm run test:live
```

GitHub Pages (after deploy): `https://prcj.github.io/regintel-preview/`

## What the suites assert

**Unit (`tests/unit/`)**
- Score bands 90/75/50/25 (`schema.py`)
- Heuristic scoring: laws high/critical, brand kits and `/news/` not relevant
- PDF relevance keep/reject
- Same-site aliases (SDAIA, SAMA, MOJ) and `.pdf.aspx` detection
- Daily collector item extract + content hash
- Eva meta-question routing and placeholder titles

**Integration (`tests/integration/`)**
- Score → jsonl → `eva_summaries.json` + `eva_meta.json`
- Eva HTTP API: `/api/health`, `/api/documents`, `/api/changes`, `/api/pipeline`, `/api/eva/ask`
- Static `web/index.html` nav + scored catalog present

**Playwright (`e2e/tests/`)**
- Nav + crawl form + Eva FAB
- Site card → detail → back
- Documents default High+Critical, band change, search empty, drawer
- Horizon cards or empty state
- Pipeline six metrics
- Hash routing `#documents` / `#pipeline`

## CI

`.github/workflows/test.yml` runs pytest on every push, then Playwright (Chromium) with `web/` served locally.

## Writing more E2E

Add specs under `e2e/tests/*.spec.ts`. `baseURL` is `http://127.0.0.1:4173` unless `BASE_URL` is set. Prefer role/label selectors already in `web/index.html`.
