# Auth Toggle Reference (Azure Web Apps)

Use this when switching between demo mode (no auth) and access-code auth.

## Apps
- Backend: `pfcd-backend-karthick-20260408`
- Frontend: `pfcd-frontend-karthick-20260408`
- Resource group: `app-pfcd-v2`

## Enable Auth

### Backend app settings
Set:
- `AUTH_ENABLED=true`
- `ACCESS_SESSION_SECRET=<strong-random-secret>`
- `OWNER_ACCESS_CODE=<owner-code>`
- `GUEST_ACCESS_CODE=<guest-code>`
- `GUEST_ACCESS_TIMEOUT_MINUTES=30`
- `ACCESS_COOKIE_SECURE=true`
- `ACCESS_COOKIE_SAMESITE=none`
- `ALLOWED_ORIGINS=https://pfcd-frontend-karthick-20260408.azurewebsites.net,http://localhost:3000,http://127.0.0.1:3000`

Example:
```bash
az webapp config appsettings set \
  --resource-group app-pfcd-v2 \
  --name pfcd-backend-karthick-20260408 \
  --settings \
  AUTH_ENABLED=true \
  ACCESS_SESSION_SECRET='change-me' \
  OWNER_ACCESS_CODE='PFCD-OWNER-XXXX' \
  GUEST_ACCESS_CODE='PFCD-GUEST-XXXX' \
  GUEST_ACCESS_TIMEOUT_MINUTES=30 \
  ACCESS_COOKIE_SECURE=true \
  ACCESS_COOKIE_SAMESITE=none \
  ALLOWED_ORIGINS='https://pfcd-frontend-karthick-20260408.azurewebsites.net,http://localhost:3000,http://127.0.0.1:3000'
```

### Frontend app settings
Set:
- `NEXT_PUBLIC_AUTH_ENABLED=true`
- `NEXT_PUBLIC_API_URL=/api`

Example:
```bash
az webapp config appsettings set \
  --resource-group app-pfcd-v2 \
  --name pfcd-frontend-karthick-20260408 \
  --settings \
  NEXT_PUBLIC_AUTH_ENABLED=true \
  NEXT_PUBLIC_API_URL=/api
```

### Restart
```bash
az webapp restart --resource-group app-pfcd-v2 --name pfcd-backend-karthick-20260408
az webapp restart --resource-group app-pfcd-v2 --name pfcd-frontend-karthick-20260408
```

## Disable Auth (Demo Mode)

### Backend
- `AUTH_ENABLED=false`

### Frontend
- `NEXT_PUBLIC_AUTH_ENABLED=false`

Example:
```bash
az webapp config appsettings set \
  --resource-group app-pfcd-v2 \
  --name pfcd-backend-karthick-20260408 \
  --settings AUTH_ENABLED=false

az webapp config appsettings set \
  --resource-group app-pfcd-v2 \
  --name pfcd-frontend-karthick-20260408 \
  --settings NEXT_PUBLIC_AUTH_ENABLED=false NEXT_PUBLIC_API_URL=/api

az webapp restart --resource-group app-pfcd-v2 --name pfcd-backend-karthick-20260408
az webapp restart --resource-group app-pfcd-v2 --name pfcd-frontend-karthick-20260408
```

## Quick Verification

Before entering code (auth enabled):
```bash
curl -sS -i https://pfcd-frontend-karthick-20260408.azurewebsites.net/api/auth/session
```
Expected: `401` with `ERR_AUTH_REQUIRED`.

After entering valid code:
Expected: `200` and `{"success":true,..."authenticated":true...}`.

Demo mode (`AUTH_ENABLED=false` and `NEXT_PUBLIC_AUTH_ENABLED=false`):
Expected: `200` authenticated response without code entry.
