# Security Policy

Do not attach production credentials or unredacted exported DSL files to public issues.

Before sharing a DSL, remove or replace:

- environment variable values marked as secrets;
- API keys, tokens, passwords, and authorization headers;
- dataset, workspace, app, workflow, and credential identifiers;
- signed URLs, webhook URLs, private hostnames, and internal API paths.

Report suspected vulnerabilities or accidental disclosures through a private GitHub security advisory. Include the affected version and a minimized, redacted reproduction.

`dify-local-sync` is restricted to user-controlled local Docker Compose deployments. Keep `/inner/api` private to the API container, never publish `INNER_API_KEY`, and never commit Compose env files, local environment Profiles, sync maps, or their backups. The generated Compose override contains only variable references, not the key itself.
