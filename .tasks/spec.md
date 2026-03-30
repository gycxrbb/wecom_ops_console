# Specification
Based on the PRD, API_SPEC, and SYSTEM_DESIGN documents.

## Current State:
- Basic `Vue` + `FastAPI` + `SQLite/SQLAlchemy` skeleton is in place.
- Models like `User`, `Group`, `Template`, `Asset`, `MessageJob`, `SendLog` exist.
- API is mostly under `/api` instead of `/api/v1`.
- Authentication uses session/cookies for basic web pages, but API requires token-based `Authorization: Bearer <token>` in `API_SPEC.md`. (Currently it seems to rely on session).
- Some core modules like `approval_requests`, `audit_logs` are missing from the schema.
- Standardization of the JSON response wrappers (code, message, data, request_id) is likely missing in some routes.

## Target State:
- Align database tables with `SYSTEM_DESIGN.md` (add `approval_requests`, `audit_logs`).
- Implement the standard structure `{ "code", "message", "data", "request_id" }`.
- Migrate `/api` to `/api/v1` and implement missing JWT standard (or align with API_SPEC).
- Implement Dashboard API & Approvals API.

## Constraints & Rules:
- Apply `taskmaster` multi-thread rules.
- Do not randomly refactor running code without checking.
- Output focused metrics.
