#!/usr/bin/env bash

set -euo pipefail

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI not found. Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
  exit 1
fi

required_vars=(
  RESOURCE_GROUP
  LOCATION
  APP_SERVICE_PLAN
  ACR_NAME
  BACKEND_APP_NAME
  FRONTEND_APP_NAME
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: ${name}"
    exit 1
  fi
done

TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"
SKIP_BUILD="${SKIP_BUILD:-false}"

BACKEND_IMAGE_REPO="${BACKEND_IMAGE_REPO:-pfcd-backend}"
FRONTEND_IMAGE_REPO="${FRONTEND_IMAGE_REPO:-pfcd-frontend}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

BACKEND_PUBLIC_URL="${BACKEND_PUBLIC_URL:-https://${BACKEND_APP_NAME}.azurewebsites.net}"
FRONTEND_PUBLIC_URL="${FRONTEND_PUBLIC_URL:-https://${FRONTEND_APP_NAME}.azurewebsites.net}"

ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-${FRONTEND_PUBLIC_URL},http://localhost:3000,http://127.0.0.1:3000}"
NEXT_PUBLIC_DEFAULT_PROVIDER="${NEXT_PUBLIC_DEFAULT_PROVIDER:-google}"
NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE="${NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE:-balanced}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api}"
NEXT_PUBLIC_AUTH_ENABLED="${NEXT_PUBLIC_AUTH_ENABLED:-false}"
DATABASE_URL="${DATABASE_URL:-sqlite:////home/pfcd.db}"

echo "==> Ensuring resource group and ACR"
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}" >/dev/null
az acr create --resource-group "${RESOURCE_GROUP}" --name "${ACR_NAME}" --sku Basic --admin-enabled true >/dev/null

ACR_LOGIN_SERVER="$(az acr show --name "${ACR_NAME}" --resource-group "${RESOURCE_GROUP}" --query loginServer -o tsv)"
ACR_USER="$(az acr credential show --name "${ACR_NAME}" --query username -o tsv)"
ACR_PASS="$(az acr credential show --name "${ACR_NAME}" --query 'passwords[0].value' -o tsv)"

BACKEND_IMAGE="${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_REPO}:${TAG}"
FRONTEND_IMAGE="${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_REPO}:${TAG}"

if [[ "${SKIP_BUILD}" != "true" ]]; then
  echo "==> Building backend image ${BACKEND_IMAGE}"
  az acr build \
    --registry "${ACR_NAME}" \
    --image "${BACKEND_IMAGE_REPO}:${TAG}" \
    --file backend/Dockerfile \
    .

  echo "==> Building frontend image ${FRONTEND_IMAGE}"
  az acr build \
    --registry "${ACR_NAME}" \
    --image "${FRONTEND_IMAGE_REPO}:${TAG}" \
    --file frontend/Dockerfile \
    --build-arg "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" \
    --build-arg "INTERNAL_API_URL=${BACKEND_PUBLIC_URL}/api" \
    --build-arg "NEXT_PUBLIC_AUTH_ENABLED=${NEXT_PUBLIC_AUTH_ENABLED}" \
    frontend
fi

echo "==> Ensuring Linux App Service plan"
if ! az appservice plan show --name "${APP_SERVICE_PLAN}" --resource-group "${RESOURCE_GROUP}" >/dev/null 2>&1; then
  az appservice plan create \
    --name "${APP_SERVICE_PLAN}" \
    --resource-group "${RESOURCE_GROUP}" \
    --is-linux \
    --sku B1 >/dev/null
fi

echo "==> Ensuring backend Web App"
if ! az webapp show --name "${BACKEND_APP_NAME}" --resource-group "${RESOURCE_GROUP}" >/dev/null 2>&1; then
  az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APP_SERVICE_PLAN}" \
    --name "${BACKEND_APP_NAME}" \
    --deployment-container-image-name "${BACKEND_IMAGE}" >/dev/null
fi

echo "==> Configuring backend container and app settings"
az webapp config container set \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${BACKEND_APP_NAME}" \
  --container-image-name "${BACKEND_IMAGE}" \
  --container-registry-url "https://${ACR_LOGIN_SERVER}" \
  --container-registry-user "${ACR_USER}" \
  --container-registry-password "${ACR_PASS}" >/dev/null

az webapp config appsettings set \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${BACKEND_APP_NAME}" \
  --settings \
  "WEBSITES_ENABLE_APP_SERVICE_STORAGE=true" \
  "WEBSITES_PORT=${BACKEND_PORT}" \
  "PORT=${BACKEND_PORT}" \
  "ENV=production" \
  "ALLOWED_ORIGINS=${ALLOWED_ORIGINS}" \
  "UPLOADS_DIR=/home/uploads" \
  "EXPORTS_DIR=/home/exports" \
  "DATABASE_URL=${DATABASE_URL}" >/dev/null

echo "==> Ensuring frontend Web App"
if ! az webapp show --name "${FRONTEND_APP_NAME}" --resource-group "${RESOURCE_GROUP}" >/dev/null 2>&1; then
  az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APP_SERVICE_PLAN}" \
    --name "${FRONTEND_APP_NAME}" \
    --deployment-container-image-name "${FRONTEND_IMAGE}" >/dev/null
fi

echo "==> Configuring frontend container and app settings"
az webapp config container set \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FRONTEND_APP_NAME}" \
  --container-image-name "${FRONTEND_IMAGE}" \
  --container-registry-url "https://${ACR_LOGIN_SERVER}" \
  --container-registry-user "${ACR_USER}" \
  --container-registry-password "${ACR_PASS}" >/dev/null

az webapp config appsettings set \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FRONTEND_APP_NAME}" \
  --settings \
  "WEBSITES_PORT=${FRONTEND_PORT}" \
  "PORT=${FRONTEND_PORT}" \
  "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" \
  "INTERNAL_API_URL=${BACKEND_PUBLIC_URL}/api" \
  "NEXT_PUBLIC_AUTH_ENABLED=${NEXT_PUBLIC_AUTH_ENABLED}" \
  "NEXT_PUBLIC_DEFAULT_PROVIDER=${NEXT_PUBLIC_DEFAULT_PROVIDER}" \
  "NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE=${NEXT_PUBLIC_DEFAULT_PROCESSING_PROFILE}" >/dev/null

echo "==> Restarting apps"
az webapp restart --resource-group "${RESOURCE_GROUP}" --name "${BACKEND_APP_NAME}" >/dev/null
az webapp restart --resource-group "${RESOURCE_GROUP}" --name "${FRONTEND_APP_NAME}" >/dev/null

echo "Deployment complete."
echo "Backend URL : ${BACKEND_PUBLIC_URL}"
echo "Frontend URL: ${FRONTEND_PUBLIC_URL}"
echo "Image tag   : ${TAG}"
