Never make write calls to external provider APIs (GitHub, Jira, and any future integrations). Use GET/HEAD only — no POST/PUT/PATCH/DELETE, no comments, no status transitions, no labels. Configure provider tokens with read-only scopes.

When implementing the front-end always use the back-ends OpenAPI spec and generate the front-end SDK with `npm run typegen` in the `frontend` directory.

The project's own HTTP API may expose write endpoints (e.g. triggering a manual sync). "Read-only" applies to outbound calls to providers, not to the dashboard's own surface.

Add tests, but focus on functionality — tests exist to validate behavior, not to mirror implementation.

- Use a real SQLite database in tests, not a mocked session. Mocked DBs pass while migrations break.
- For GitHub/Jira clients, use recorded HTTP cassettes (e.g. `pytest-recording`/VCR) rather than hand-mocking responses. Keeps tests behavior-driven, avoids hitting live APIs, and prevents accidental writes during test runs.
- Assert on observable outputs (metric values, response payloads, DB state) rather than on internal method calls or call counts.

Tokens and secrets live in environment variables and are read only by the app's config loader to populate provider clients. Outside of that loader:

- The agent must never read, print, or echo environment variables — no `echo $TOKEN`, no `env | grep`, no `printenv`, no scripts that inspect `os.environ` for diagnostic purposes.
- Never include token values in logs, exception messages, stack traces, HTTP error reports, or anything written to disk. Error messages may reference the env var *name* but never its value.
- Never ask the user to paste a token value into the conversation. If a token appears invalid, report the symptom (e.g. "Jira health check returned 401") and let the user inspect their own environment.
