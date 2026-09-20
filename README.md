# dbGaP LinkML Schema Browser

A small static docs site (built with [mkdocs](https://www.mkdocs.org/)) for
browsing LinkML schemas generated from dbGaP `var_report.xml` variable
summaries — one page per study, all navigable from a single sidebar.

## Pushing to GitHub

This folder is already a git repo (`git init` + first commit done, on
branch `main`). To put it on GitHub:

```bash
# 1. Create an empty repo on GitHub (no README/license/gitignore — this
#    folder already has all of that), e.g. via the CLI:
gh repo create dbgap-linkml-docs --public --source=. --remote=origin

#    ...or create it in the GitHub web UI, then:
git remote add origin https://github.com/<your-username>/dbgap-linkml-docs.git

# 2. Push
git push -u origin main
```

## Enabling GitHub Pages (auto-deploy on every push)

A workflow at `.github/workflows/deploy-docs.yml` is already included — it
rebuilds the site from `schemas/` and deploys it via GitHub Pages every
time you push to `main` (or you can trigger it manually from the Actions
tab). To turn it on:

1. On GitHub: **Settings → Pages → Source → GitHub Actions** (not "Deploy
   from a branch" — the workflow uses the newer Pages Actions deployment).
2. Push to `main` (or re-run the workflow from the **Actions** tab).
3. Your site will be live at `https://<your-username>.github.io/dbgap-linkml-docs/`
   — the exact URL also shows up in the workflow run's summary and under
   Settings → Pages once the first deploy finishes.

No further setup needed — every future push that touches `schemas/`,
`docs/`, `build_docs.py`, or `mkdocs.yml` triggers a fresh build + deploy
automatically.

## Layout

```
dbgap-linkml-docs/
├── schemas/            <- drop your *_schema.yaml files here (from bdc2linkml.py)
├── build_docs.py        <- regenerates docs/ + mkdocs.yml from schemas/
├── docs/                 <- generated markdown (do not hand-edit; re-run build_docs.py)
│   ├── index.md          <- study index / landing page
│   └── studies/
│       ├── phs000179.md
│       ├── phs000280.md
│       └── ...
├── mkdocs.yml            <- generated nav config (do not hand-edit)
└── site/                 <- built static HTML (after `mkdocs build`)
```

## Adding a new study

1. Copy the study's `*_schema.yaml` (from `bdc2linkml.py`) into `schemas/`.
2. Run:
   ```bash
   python build_docs.py
   ```
   This regenerates every page under `docs/` and rewrites `mkdocs.yml`'s nav
   to include the new study automatically — no manual nav editing needed.
3. Preview or rebuild the site (see below).

## Preview / build

```bash
pip install mkdocs

mkdocs serve     # live-reload dev server at http://127.0.0.1:8000
mkdocs build     # writes static HTML to site/ (this is what you'd deploy)
```

`site/` can be hosted anywhere that serves static files — GitHub Pages,
S3, a plain nginx directory, etc. `mkdocs gh-deploy` will push it straight
to a `gh-pages` branch if you're on GitHub.

## What each study page shows

- **Datasets** — one section per LinkML class (= one dbGaP `pht` dataset
  table), with a table of its variables: name, dbGaP type, LinkML range,
  total N, and description.
- **Enums** — shared permissible-value sets, cross-linked from the Range
  column of any variable that uses them.

Per-variable observed value counts (`value_counts`), dbGaP variable IDs,
and source filenames live in each slot's `annotations` in the underlying
YAML — not repeated in the docs tables, to keep them readable, but the
YAML is always one click away if you need the full detail.
