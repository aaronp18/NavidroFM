# Copilot / AI assistant instructions

The canonical guide for AI agents in this repository is
[`AGENTS.md`](../AGENTS.md) — read it before proposing changes.

Key points:

- Python 3.12, flat modules in `src/`, tests in `tests/` (pytest), linting with
  ruff. Run `make check` before finishing.
- Never hardcode container paths (`/app`, `/music`) — use the getters in
  `src/config.py` (`NAVIDROFM_*` environment variables).
- Add runtime dependencies to `requirements.txt` only; dev tools go in
  `requirements-dev.txt`.
- Tests must not use the network, a real Navidrome instance, or the local
  filesystem outside `tmp_path`.
- `src/legacy.py` is dead code; do not import or extend it.
- Never commit `.env`, `cookies.txt`, `docker-compose.yml` or downloaded media.
