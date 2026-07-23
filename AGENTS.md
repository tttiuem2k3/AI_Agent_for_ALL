# Repository Guidelines

## Project Structure & Module Organization

Production Python code uses a `src` layout. `src/Runtime` contains agents, messages, events, and middleware; `src/Providers` contains LLM, embedding, OCR, speech, and credential integrations; `src/Capabilities` contains tools, MCP, permissions, skills, and workspaces; `src/Service` exposes the FastAPI service and storage/scheduling infrastructure; and `src/Common` holds shared utilities. Runnable integration examples live in `development/run_examples`. The React/TypeScript development UI is a pnpm workspace under `development/Web_UI`, split into `frontend` and `backend`. Keep documentation and diagrams in `docs/`.

## Build, Test, and Development Commands

- `uv sync --all-extras` creates `.venv` and installs the locked Python dependencies.
- `uv run --extra dev pytest` runs the pytest suite configured at `development/tests`.
- `uv run python development/run_examples/agent_basic_test.py` runs one integration example directly; many require provider keys or external services.
- `uv build --wheel` builds the Python wheel into `dist/`.
- From `development/Web_UI`, run `pnpm install`, then `pnpm dev` to start both UI workspaces; use `pnpm build` for production builds and `pnpm format:check` for Prettier/ESLint validation.

## Coding Style & Naming Conventions

Use Python 3.11+ syntax, four-space indentation, type hints on public APIs, `snake_case` for modules/functions, and `PascalCase` for classes. Keep provider-specific behavior under the matching `Providers` package and preserve stable interfaces between Runtime, Capabilities, and Service. TypeScript/TSX follows the existing tab-indented style; run Prettier and ESLint rather than hand-formatting. React components use `PascalCase.tsx`, hooks use `useName.ts`, and imports are grouped and alphabetized per `eslint.config.js`.

## Testing Guidelines

Add pytest files as `development/tests/test_*.py`; name test functions `test_<behavior>`. Cover success, validation, and async/error paths. Treat `development/run_examples/*_test.py` as targeted integration checks because they are outside pytest's configured `testpaths`. Run focused tests during development and the full suite before review.

## Commit & Pull Request Guidelines

Git history is not included in this checkout. Use concise, imperative, scoped subjects, for example `Service: validate workspace IDs`. Pull requests should explain behavior changes, list verification commands, link the issue, and call out configuration or API impacts. Include screenshots for Web UI changes and never commit API keys, `.env` files, `.venv`, `dist`, `build`, or generated `*.egg-info` content.

## Agent-Specific Instructions

For code discovery, use the codebase knowledge graph first: `search_graph`, `trace_path`, then `get_code_snippet`. Use text/file search only for literals, configuration, non-code files, or when graph results are insufficient.
