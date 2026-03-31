Refactor notes

- Created `backend/` package with wrapper modules that re-export names from
  `server.py` to preserve runtime behavior while splitting the project into
  modules.
- The wrappers are temporary and intended to make incremental movement of
  functions/classes from `server.py` into dedicated files safer.

Next steps

- Move related functions and classes from `server.py` into the appropriate
  files in `backend/` (e.g. models into `backend/db.py`, routes into
  `backend/routes.py`, matching logic into `backend/services.py`).
- Update imports throughout the codebase to reference `backend.*` modules.
- Remove re-export wrappers and keep the new modules as the single source of
  truth.
