# Azure Web App (Docker) Deployment

This project is split into two containers:
- `backend` (FastAPI on port `8000`)
- `frontend` (Next.js on port `3000`)

For Azure App Service, deploy them as two Linux Web Apps using images from Azure Container Registry (ACR).

## Prerequisites
- Azure CLI installed and logged in:
  - `az login`
  - `az account set --subscription "<your-subscription-id-or-name>"`

## One-Command Deployment
From repo root:

```bash
export RESOURCE_GROUP="rg-pfcd-demo"
export LOCATION="eastus"
export APP_SERVICE_PLAN="asp-pfcd-linux"
export ACR_NAME="acrpfcddemo001"          # must be globally unique
export BACKEND_APP_NAME="pfcd-backend-demo"
export FRONTEND_APP_NAME="pfcd-frontend-demo"

# Optional:
# export TAG="v1"
# export DATABASE_URL="mssql+pyodbc://<user>:<password>@<server>.database.windows.net:1433/<db>?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
# export NEXT_PUBLIC_DEFAULT_PROVIDER="google"
# export NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE="balanced"
# export BACKEND_PUBLIC_URL="https://pfcd-backend-demo.azurewebsites.net"
# export FRONTEND_PUBLIC_URL="https://pfcd-frontend-demo.azurewebsites.net"
# export ALLOWED_ORIGINS="https://pfcd-frontend-demo.azurewebsites.net"
# export NEXT_PUBLIC_AUTH_ENABLED="false"  # build-time, rebuild required when changed

./infra/azure/deploy_webapp.sh
```

## Required Secrets (Backend Web App)
Set these in backend app settings after deploy:
- `GOOGLE_API_KEY` and/or `OPENAI_API_KEY`
- If using Azure OpenAI path:
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_CHAT_DEPLOYMENT`
  - `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT`

Example:
```bash
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$BACKEND_APP_NAME" \
  --settings \
  GOOGLE_API_KEY="..." \
  OPENAI_API_KEY="..."
```

## Notes
- Backend app settings set by script:
  - `UPLOADS_DIR=/home/uploads`
  - `EXPORTS_DIR=/home/exports`
  - `DATABASE_URL` (default `sqlite:////home/pfcd.db`, override with Azure SQL connection string)
- `WEBSITES_PORT` and `PORT` are set automatically for both apps.
- Frontend image is built with:
  - `NEXT_PUBLIC_API_URL=/api`
  - `INTERNAL_API_URL=<backend-url>/api`
  - `NEXT_PUBLIC_AUTH_ENABLED=<true|false>`
  This keeps browser calls same-origin through frontend rewrites.
- `NEXT_PUBLIC_AUTH_ENABLED` is build-time in Next.js:
  - changing this value requires rebuilding and redeploying frontend image.
- Recommended cloud baseline:
  - use Azure SQL via `DATABASE_URL` instead of SQLite.

## Redeploy With New Code
Re-run the same script with a new tag:

```bash
export TAG="$(date +%Y%m%d%H%M%S)"
./infra/azure/deploy_webapp.sh
```
