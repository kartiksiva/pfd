# Azure Deployment Notes (Current Baseline)

This file captures the current Azure baseline at commit `abcfdf4`.

## Active Topology

- Resource group: `app-pfcd-v2`
- App Service plan: `pfcd-dev-asp` (Linux)
- ACR: `acrpfcdkarthick20260408`
- Backend app: `pfcd-backend-karthick-20260408`
- Frontend app: `pfcd-frontend-karthick-20260408`

## Current Operating Model

- Frontend and backend are deployed as separate Linux Web Apps.
- Frontend calls backend via same-origin `/api` rewrite.
- Backend persistence baseline is Azure SQL (SQL Server) via `mssql+pyodbc`.
- Auth can be toggled on/off using app settings (see auth reference).

## Canonical Docs

Use these as source of truth:
- Full replication guide: `PROJECT_REPLICATION_GUIDE.md`
- Azure deployment script guide: `infra/azure/README.md`
- Auth toggle runbook: `infra/azure/AUTH_REFERENCE.md`

## Important Lessons from Migration

1. `NEXT_PUBLIC_AUTH_ENABLED` is build-time in Next.js.
- Changing it in app settings alone is not enough.
- Rebuild and redeploy frontend image whenever this flag changes.

2. Avoid SQLite for cloud baseline.
- SQLite path and permissions can fail at startup in App Service containers.
- Use Azure SQL `DATABASE_URL` for stable cloud behavior.

3. Use dedicated SQL database per app where possible.
- Reusing an old shared DB can cause schema mismatches.

4. App Service startup can show transient VNET/warmup noise.
- Validate final health after restart before assuming failure.

## Quick Health Checks

```bash
curl -sS -i https://pfcd-backend-karthick-20260408.azurewebsites.net/health
curl -sS -i https://pfcd-frontend-karthick-20260408.azurewebsites.net/api/auth/session
curl -sS -i -X POST https://pfcd-frontend-karthick-20260408.azurewebsites.net/api/jobs/demo
```

## Notes

- This file is intentionally concise and current-state only.
- Historical troubleshooting details are superseded by `PROJECT_REPLICATION_GUIDE.md`.
