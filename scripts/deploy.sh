#!/bin/bash
# Deploy to Yandex Cloud Serverless Containers
# Usage: ./scripts/deploy.sh

set -euo pipefail

CONTAINER_NAME="agile-bot"
IMAGE="cr.yandex/crpklb64osqn44g087ms/agile-bot:latest"
SERVICE_ACCOUNT="ajebbpm9rnohmogrjtnj"
CONTAINER_URL="https://bbaepg3s35pu1fi9clmi.containers.yandexcloud.net"
FOLDER_ID="b1g54clmnarco19prqv4"

# Read secrets from .env (security systems may mask them in shell)
source .env 2>/dev/null
YC_KEY=$(grep "^YC_API_KEY=" .env | cut -d= -f2)
TG_TOKEN=$(grep "^TELEGRAM_TOKEN=" .env | cut -d= -f2)
LF_SECRET=$(grep "^LANGFUSE_SECRET_KEY=" .env | cut -d= -f2)
LF_PUBLIC=$(grep "^LANGFUSE_PUBLIC_KEY=" .env | cut -d= -f2)

# Yandex Managed PG (not from .env which may have local DB)
DB_URL="postgresql://agile:x4WpyBLjvTu4RZA1YZCN6J9@rc1a-slh4hd71sf2i670c.mdb.yandexcloud.net:6432/agile?sslmode=require"

echo "==> Building image..."
docker build --platform linux/amd64 -t "$IMAGE" .

echo "==> Pushing image..."
docker push "$IMAGE"

echo "==> Deploying revision..."
yc serverless container revision deploy \
  --container-name "$CONTAINER_NAME" \
  --image "$IMAGE" \
  --service-account-id "$SERVICE_ACCOUNT" \
  --memory 512m --cores 1 --core-fraction 100 \
  --execution-timeout 60s --concurrency 4 --min-instances 1 \
  --environment "TELEGRAM_TOKEN=${TG_TOKEN},YC_API_KEY=${YC_KEY},YC_FOLDER_ID=${FOLDER_ID},DATABASE_URL=${DB_URL},DB_STATEMENT_CACHE_SIZE=0,WEBHOOK_URL=${CONTAINER_URL},YC_LLM_MODEL=deepseek-v32,HISTORY_MAX=20,HISTORY_TRIM_TO=16,HISTORY_TTL_SECONDS=3600,CONTEXT_RADIUS=5,MAX_SEARCH_RESULTS=20,MAX_AGENT_ITERATIONS=3,LANGFUSE_SECRET_KEY=${LF_SECRET},LANGFUSE_PUBLIC_KEY=${LF_PUBLIC},LANGFUSE_BASE_URL=https://cloud.langfuse.com"

echo "==> Allowing unauthenticated invoke..."
yc serverless container allow-unauthenticated-invoke --name "$CONTAINER_NAME"

echo "==> Health check..."
sleep 3
curl -sf "${CONTAINER_URL}/health" && echo " OK" || echo " FAILED"

echo "==> Done!"
