#!/bin/bash
# wire-pubsub.sh — Wire Pub/Sub push subscriptions to Cloud Run workers
# Run AFTER deploy.sh completes.
# Run from repo root: bash wire-pubsub.sh

set -e

PROJECT=file-orchestrator-2025
REGION=us-central1

# ── Fetch deployed service URLs ───────────────────────────────────────────────
echo "Fetching Cloud Run service URLs..."

INSPECT_URL=$(gcloud run services describe cfo-inspect \
  --project $PROJECT --region $REGION \
  --format "value(status.url)")

CLASSIFY_URL=$(gcloud run services describe cfo-classify \
  --project $PROJECT --region $REGION \
  --format "value(status.url)")

ACT_URL=$(gcloud run services describe cfo-act \
  --project $PROJECT --region $REGION \
  --format "value(status.url)")

echo "  inspect  → $INSPECT_URL"
echo "  classify → $CLASSIFY_URL"
echo "  act      → $ACT_URL"

# ── Service account for Pub/Sub → Cloud Run auth ─────────────────────────────
# Cloud Run workers are deployed --no-allow-unauthenticated, so Pub/Sub needs
# a service account that has roles/run.invoker on each service.
SA_EMAIL="pubsub-invoker@$PROJECT.iam.gserviceaccount.com"

# Create SA if it doesn't exist
if ! gcloud iam service-accounts describe $SA_EMAIL --project $PROJECT &>/dev/null; then
  echo ""
  echo "Creating service account $SA_EMAIL ..."
  gcloud iam service-accounts create pubsub-invoker \
    --project $PROJECT \
    --display-name "Pub/Sub Cloud Run Invoker"
fi

# Grant invoker role on each worker
echo ""
echo "Granting roles/run.invoker to $SA_EMAIL on workers..."
for SVC in cfo-inspect cfo-classify cfo-act; do
  gcloud run services add-iam-policy-binding $SVC \
    --project $PROJECT \
    --region $REGION \
    --member "serviceAccount:$SA_EMAIL" \
    --role roles/run.invoker
done

# Allow Pub/Sub to create tokens for this SA (needed for push auth)
gcloud projects add-iam-policy-binding $PROJECT \
  --member "serviceAccount:$SA_EMAIL" \
  --role roles/iam.serviceAccountTokenCreator 2>/dev/null || true

# ── Topics (create if missing) ────────────────────────────────────────────────
echo ""
echo "Ensuring Pub/Sub topics exist..."
for TOPIC in ingest-topic classify-topic act-topic; do
  if ! gcloud pubsub topics describe $TOPIC --project $PROJECT &>/dev/null; then
    echo "  Creating topic: $TOPIC"
    gcloud pubsub topics create $TOPIC --project $PROJECT
  else
    echo "  Topic exists:   $TOPIC"
  fi
done

# ── Subscriptions ─────────────────────────────────────────────────────────────
echo ""
echo "Creating push subscriptions..."

create_or_update_sub() {
  local SUB_NAME=$1
  local TOPIC=$2
  local PUSH_URL=$3

  if gcloud pubsub subscriptions describe $SUB_NAME --project $PROJECT &>/dev/null; then
    echo "  Updating subscription: $SUB_NAME"
    gcloud pubsub subscriptions modify-push-config $SUB_NAME \
      --project $PROJECT \
      --push-endpoint "$PUSH_URL" \
      --push-auth-service-account "$SA_EMAIL"
  else
    echo "  Creating subscription: $SUB_NAME"
    gcloud pubsub subscriptions create $SUB_NAME \
      --project $PROJECT \
      --topic $TOPIC \
      --push-endpoint "$PUSH_URL" \
      --push-auth-service-account "$SA_EMAIL" \
      --ack-deadline 60
  fi
}

create_or_update_sub "inspect-sub"  "ingest-topic"    "$INSPECT_URL/pubsub-push"
create_or_update_sub "classify-sub" "classify-topic"  "$CLASSIFY_URL/pubsub-push"
create_or_update_sub "act-sub"      "act-topic"       "$ACT_URL/pubsub-push"

echo ""
echo "✅ Pub/Sub wiring complete."
echo ""
echo "Topic → Subscription → Worker"
echo "  ingest-topic    → inspect-sub   → $INSPECT_URL/pubsub-push"
echo "  classify-topic  → classify-sub  → $CLASSIFY_URL/pubsub-push"
echo "  act-topic       → act-sub       → $ACT_URL/pubsub-push"
