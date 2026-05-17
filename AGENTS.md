# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Python web-scraping/update utility. Core logic lives in `wslib.py` and `funclib.py`. `main.py` is the primary entry point and loads site definitions from `urlList.json`. Source-maintenance helpers include `add_new_source.py`, `check_new_source.py`, and `sample_new_source.py`. Script-style checks such as `test.py`, `test_detail.py`, and `test_new_source.py` are kept at the root. Batch helpers live under `bat/`. Configuration and input data are root-level JSON files, including `urlList.json`, `notUseUrlList.json`, and samples.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install runtime dependencies.
- `pipenv install --dev`: install runtime and development tools from `Pipfile`.
- `python main.py`: run the full update flow using `urlList.json`.
- `python test.py` or `python test_detail.py`: run the current script-style checks.
- `python check_new_source.py`: inspect newly added source definitions.

Run commands from the repository root so relative paths such as `./urlList.json` resolve correctly.

## Coding Style & Naming Conventions

Use Python 3 and follow PEP 8. Prefer 4-space indentation, snake_case for variables and functions, and PascalCase for classes such as `MinistrySiteDataGetter`. Keep shared scraping or parsing behavior in `wslib.py` or `funclib.py`; keep one-off execution in small scripts. Development tooling in `Pipfile` includes Black and isort integrations, so keep changed files Black-compatible and group imports as standard library, third-party packages, then local modules.

## Testing Guidelines

There is no formal pytest suite yet; existing tests are executable scripts. When adding checks, use `test_*.py` naming and keep them runnable with `python <file>`. Prefer deterministic inputs from `sample.json`, `test.json`, or small fixture JSON files over live network calls. For scraping changes, include one focused script or documented manual command showing the affected source.

## Commit & Pull Request Guidelines

Git history could not be inspected because the repository is not configured as a safe Git directory. Use short, imperative commit messages such as `Add source validation check` or `Fix feed date parsing`. Pull requests should include a concise summary, commands run, affected data files or sources, and operational impact. Link related issues when available.

## Security & Configuration Tips

Do not commit real credentials or regenerated Firebase service-account keys. Treat `.env` and `ws-db-11235813-firebase-adminsdk-lh4mi-50c38e64b5.json` as sensitive configuration. Keep source URL changes small and review `urlList.json` diffs carefully before running update scripts.
