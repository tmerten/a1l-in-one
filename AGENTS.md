Never make write calls to external provider APIs (GitHub, Jira, and any future integrations). Use GET/HEAD only — no POST/PUT/PATCH/DELETE, no comments, no status transitions, no labels. Configure provider tokens with read-only scopes.

The project's own HTTP API may expose write endpoints (e.g. triggering a manual sync). "Read-only" applies to outbound calls to providers, not to the dashboard's own surface.

Add tests, but focus on functionality — tests exist to validate behavior, not to mirror implementation.

- Use a real SQLite database in tests, not a mocked session. Mocked DBs pass while migrations break.
- For GitHub/Jira clients, use recorded HTTP cassettes (e.g. `pytest-recording`/VCR) rather than hand-mocking responses. Keeps tests behavior-driven, avoids hitting live APIs, and prevents accidental writes during test runs.
- Assert on observable outputs (metric values, response payloads, DB state) rather than on internal method calls or call counts.
