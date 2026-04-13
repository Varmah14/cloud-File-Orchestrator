#!/bin/bash
# deploy.sh — Cloud File Orchestrator full deploy
# Run from repo root: bash deploy.sh
# Requires: gcloud CLI authenticated

set -e

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT=file-orchestrator-2025
REGION=us-central1
UPLOAD_BUCKET=file-uploads
PROCESSED_BUCKET=file-organized
INGEST_TOPIC=ingest-topic
CLASSIFY_TOPIC=classify-topic
ACT_TOPIC=act-topic
JOBS_COLLECTION=jobs
RULES_COLLECTION=rules

ENV_VARS="GCP_PROJECT_ID=$PROJECT,\
UPLOAD_BUCKET=$UPLOAD_BUCKET,\
PROCESSED_BUCKET=$PROCESSED_BUCKET,\
INGEST_TOPIC=$INGEST_TOPIC,\
CLASSIFY_TOPIC=$CLASSIFY_TOPIC,\
ACT_TOPIC=$ACT_TOPIC,\
JOBS_COLLECTION=$JOBS_COLLECTION,\
RULES_COLLECTION=$RULES_COLLECTION"

echo "========================================"
echo " Cloud File Orchestrator — Full Deploy"
echo " Project : $PROJECT"
echo " Region  : $REGION"
echo "========================================"

# ── Step 1: Set project ───────────────────────────────────────────────────────
echo ""
echo "▶ Setting gcloud project..."
gcloud config set project $PROJECT

# ── Step 2: Enable APIs ───────────────────────────────────────────────────────
echo ""
echo "▶ Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  --project $PROJECT

# ── Step 3: Create Firestore database ─────────────────────────────────────────
echo ""
echo "▶ Creating Firestore database (skip if exists)..."
gcloud firestore databases create \
  --project $PROJECT \
  --location $REGION 2>/dev/null || echo "  Firestore already exists, skipping."

# ── Step 4: Create GCS buckets ────────────────────────────────────────────────
echo ""
echo "▶ Creating GCS buckets..."
gsutil mb -p $PROJECT -l $REGION gs://$UPLOAD_BUCKET 2>/dev/null || echo "  gs://$UPLOAD_BUCKET already exists."
gsutil mb -p $PROJECT -l $REGION gs://$PROCESSED_BUCKET 2>/dev/null || echo "  gs://$PROCESSED_BUCKET already exists."

# ── Step 5: Create Pub/Sub topics ────────────────────────────────────────────
echo ""
echo "▶ Creating Pub/Sub topics..."
for TOPIC in $INGEST_TOPIC $CLASSIFY_TOPIC $ACT_TOPIC; do
  gcloud pubsub topics create $TOPIC --project $PROJECT 2>/dev/null || echo "  Topic $TOPIC already exists."
done

# ── Step 6: Grant GCS → Pub/Sub publish permission ───────────────────────────
echo ""
echo "▶ Granting GCS service agent Pub/Sub publisher role..."
GCS_SA="service-$(gcloud projects describe $PROJECT --format='value(projectNumber)')@gs-project-accounts.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$GCS_SA" \
  --role="roles/pubsub.publisher" 2>/dev/null || true

# ── Step 7: GCS notification → ingest-topic ──────────────────────────────────
echo ""
echo "▶ Creating GCS notification on upload bucket..."
gsutil notification create \
  -t projects/$PROJECT/topics/$INGEST_TOPIC \
  -f json \
  gs://$UPLOAD_BUCKET 2>/dev/null || echo "  Notification may already exist."

# ── Step 8: Create Pub/Sub invoker service account ───────────────────────────
echo ""
echo "▶ Setting up Pub/Sub invoker service account..."
SA_EMAIL="pubsub-invoker@$PROJECT.iam.gserviceaccount.com"
gcloud iam service-accounts create pubsub-invoker \
  --project $PROJECT \
  --display-name "Pub/Sub Cloud Run Invoker" 2>/dev/null || echo "  Service account already exists."

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountTokenCreator" 2>/dev/null || true

# ── Step 9: Grant compute SA Firestore access ─────────────────────────────────
echo ""
echo "▶ Granting Firestore access to compute service account..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
COMPUTE_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/datastore.user" 2>/dev/null || true

# ── Step 10: Deploy services ──────────────────────────────────────────────────
echo ""
echo "▶ [1/4] Deploying API..."
gcloud run deploy cfo-api \
  --project $PROJECT \
  --region $REGION \
  --source ./services/api \
  --allow-unauthenticated \
  --set-env-vars "$ENV_VARS,SOURCE_BUCKET=$UPLOAD_BUCKET,UI_ORIGINS=*"

echo ""
echo "▶ [2/4] Deploying inspect worker..."
gcloud run deploy cfo-inspect \
  --project $PROJECT \
  --region $REGION \
  --source ./services/inspect_worker \
  --no-allow-unauthenticated \
  --set-env-vars "$ENV_VARS"

echo ""
echo "▶ [3/4] Deploying classify worker..."
gcloud run deploy cfo-classify \
  --project $PROJECT \
  --region $REGION \
  --source ./services/classify_worker \
  --no-allow-unauthenticated \
  --set-env-vars "$ENV_VARS"

echo ""
echo "▶ [4/4] Deploying act worker..."
gcloud run deploy cfo-act \
  --project $PROJECT \
  --region $REGION \
  --source ./services/act_worker \
  --no-allow-unauthenticated \
  --set-env-vars "$ENV_VARS"

# ── Step 11: Wire Pub/Sub subscriptions ───────────────────────────────────────
echo ""
echo "▶ Wiring Pub/Sub subscriptions..."

INSPECT_URL=$(gcloud run services describe cfo-inspect \
  --project $PROJECT --region $REGION --format "value(status.url)")
CLASSIFY_URL=$(gcloud run services describe cfo-classify \
  --project $PROJECT --region $REGION --format "value(status.url)")
ACT_URL=$(gcloud run services describe cfo-act \
  --project $PROJECT --region $REGION --format "value(status.url)")

create_or_update_sub() {
  local SUB=$1 TOPIC=$2 ENDPOINT=$3
  if gcloud pubsub subscriptions describe $SUB --project $PROJECT &>/dev/null; then
    gcloud pubsub subscriptions modify-push-config $SUB \
      --project $PROJECT \
      --push-endpoint "$ENDPOINT" \
      --push-auth-service-account "$SA_EMAIL"
    echo "  Updated: $SUB → $ENDPOINT"
  else
    gcloud pubsub subscriptions create $SUB \
      --project $PROJECT \
      --topic $TOPIC \
      --push-endpoint "$ENDPOINT" \
      --push-auth-service-account "$SA_EMAIL" \
      --ack-deadline 60
    echo "  Created: $SUB → $ENDPOINT"
  fi
}

# Grant invoker role on each worker
for SVC in cfo-inspect cfo-classify cfo-act; do
  gcloud run services add-iam-policy-binding $SVC \
    --project $PROJECT --region $REGION \
    --member "serviceAccount:$SA_EMAIL" \
    --role roles/run.invoker 2>/dev/null || true
done

create_or_update_sub "inspect-sub"  "$INGEST_TOPIC"   "$INSPECT_URL/pubsub-push"
create_or_update_sub "classify-sub" "$CLASSIFY_TOPIC" "$CLASSIFY_URL/pubsub-push"
create_or_update_sub "act-sub"      "$ACT_TOPIC"      "$ACT_URL/pubsub-push"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "✅ Deployment complete!"
echo ""
echo "API URL: $(gcloud run services describe cfo-api --project $PROJECT --region $REGION --format 'value(status.url)')"
echo ""
echo "Pipeline:"
echo "  Upload → gs://$UPLOAD_BUCKET"
echo "      ↓ $INGEST_TOPIC"
echo "  cfo-inspect → $CLASSIFY_TOPIC"
echo "      ↓"
echo "  cfo-classify → $ACT_TOPIC"
echo "      ↓"
echo "  cfo-act → gs://$PROCESSED_BUCKET + Firestore"
echo ""
echo "Next: update ui/.env with the API URL above"
echo "========================================"
