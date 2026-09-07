# services/api/main.py

import os
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import firebase_admin
from firebase_admin import auth as firebase_auth
from google.cloud import storage, firestore

from common.config import GCP_PROJECT_ID

# -----------------------------------------------------------------------------
# App + CORS (for UI)
# -----------------------------------------------------------------------------

app = FastAPI(title="Cloud File Orchestrator API")

UI_ORIGINS = os.getenv("UI_ORIGINS", "*")  # e.g. "http://localhost:5173"
if UI_ORIGINS == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in UI_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Config / clients
# -----------------------------------------------------------------------------

SOURCE_BUCKET = os.getenv("SOURCE_BUCKET", "")  # set in Cloud Run / .env
if not SOURCE_BUCKET:
    print("[WARN] SOURCE_BUCKET is not set. /upload will fail until it is.")

storage_client = storage.Client()
db = firestore.Client(project=GCP_PROJECT_ID)

if not firebase_admin._apps:
    firebase_admin.initialize_app()


# -----------------------------------------------------------------------------
# Auth: verify Firebase ID tokens (Google Sign-In), scope every request to
# the caller's own uid. Cloud Run itself stays allow-unauthenticated at the
# IAM layer -- this dependency is the real gate.
# -----------------------------------------------------------------------------


async def require_uid(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")
    return decoded["uid"]


def user_rules_ref(uid: str):
    return db.collection("users").document(uid).collection("rules")


def user_jobs_ref(uid: str):
    return db.collection("users").document(uid).collection("jobs")


# -----------------------------------------------------------------------------
# Models: Rules & Activity
# -----------------------------------------------------------------------------

ConditionType = Literal["extension", "name_contains", "size_gt_mb", "size_lt_mb"]
ActionType = Literal["move_to_folder", "tag", "delete", "copy_to_bucket"]


class RuleCondition(BaseModel):
    type: ConditionType
    value: str


class RuleAction(BaseModel):
    type: ActionType
    value: str


class Rule(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    priority: int
    enabled: bool = True
    conditions: List[RuleCondition]
    actions: List[RuleAction]


class ActivityEvent(BaseModel):
    id: str
    timestamp: datetime
    bucket: str
    object: str
    status: Literal["pending", "processed", "error"]
    rule_name: Optional[str] = None
    actions: List[str] = []
    error_message: Optional[str] = None


class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int
    enabled: bool = True
    conditions: List[RuleCondition]
    actions: List[RuleAction]


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[RuleCondition]] = None
    actions: Optional[List[RuleAction]] = None


# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Rules API (Firestore-backed, scoped to users/{uid}/rules)
# -----------------------------------------------------------------------------


@app.get("/rules", response_model=List[Rule])
def list_rules(uid: str = Depends(require_uid)) -> List[Rule]:
    """
    List the caller's own rules, sorted by priority ascending.
    """
    docs = user_rules_ref(uid).order_by("priority").stream()
    rules: List[Rule] = []
    for d in docs:
        data = d.to_dict() or {}
        data["id"] = d.id
        rules.append(Rule(**data))
    return rules


@app.post("/rules", response_model=Rule)
def create_rule(rule: RuleCreate, uid: str = Depends(require_uid)) -> Rule:
    """
    Create a new rule under the caller's own rules subcollection.
    """
    doc_ref = user_rules_ref(uid).document()
    doc_ref.set(rule.dict())

    stored = doc_ref.get().to_dict() or {}
    stored["id"] = doc_ref.id
    return Rule(**stored)


@app.put("/rules/{rule_id}", response_model=Rule)
def update_rule(rule_id: str, patch: RuleUpdate, uid: str = Depends(require_uid)) -> Rule:
    """
    Update one of the caller's own rules (partial update). Ownership is
    enforced structurally: the path is always users/{uid}/rules/... where
    uid comes from the verified token, never from client input, so there's
    no rule_id namespace shared across users to accidentally cross into.
    """
    ref = user_rules_ref(uid).document(rule_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = patch.dict(exclude_unset=True)
    ref.set(updates, merge=True)

    data = ref.get().to_dict() or {}
    data["id"] = ref.id
    return Rule(**data)


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, uid: str = Depends(require_uid)):
    """
    Delete one of the caller's own rules by id.
    """
    ref = user_rules_ref(uid).document(rule_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Rule not found")
    ref.delete()
    return {"ok": True}


@app.post("/rules/reorder")
def reorder_rules(order: List[str] = Body(...), uid: str = Depends(require_uid)):
    """
    Reorder the caller's own rules by IDs.
    Body: ["rule-id-1", "rule-id-2", ...]
    Sets `priority` to index in list.
    """
    batch = db.batch()
    for idx, rid in enumerate(order):
        ref = user_rules_ref(uid).document(rid)
        batch.set(ref, {"priority": idx}, merge=True)
    batch.commit()
    return {"ok": True}


# -----------------------------------------------------------------------------
# Upload endpoint (GCS upload; GCS -> Pub/Sub -> workers)
#
# NOTE: still the proxy-upload design -- replaced by /upload-url (presigned,
# direct-to-GCS, auth-gated) in Phase C. Left as-is here deliberately, not
# an oversight.
# -----------------------------------------------------------------------------


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to the configured GCS bucket.

    Object name will include the original filename so
    name-based rules (e.g. "Name contains INFO 4602") can match.
    """
    if not SOURCE_BUCKET:
        raise HTTPException(
            status_code=500,
            detail="SOURCE_BUCKET is not configured on the server.",
        )

    try:
        # Original filename from the client
        original_name = file.filename or "upload"
        # Strip any path components just in case
        base_name = os.path.basename(original_name)
        # Avoid "/" in the final object name, but keep spaces etc.
        safe_name = base_name.replace("/", "_")

        # Prefix with a uuid to avoid collisions, but keep the human name
        blob_name = f"uploads/{uuid.uuid4().hex}__{safe_name}"

        bucket = storage_client.bucket(SOURCE_BUCKET)
        blob = bucket.blob(blob_name)

        # Optional: store original filename in metadata too
        blob.metadata = {"original_filename": original_name}

        # Upload file content
        blob.upload_from_file(file.file, content_type=file.content_type)

        return {
            "message": "uploaded",
            "bucket": SOURCE_BUCKET,
            "object": blob_name,
            "original_filename": original_name,
            "content_type": file.content_type,
            "public_url": blob.public_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


# -----------------------------------------------------------------------------
# Activity helpers
# -----------------------------------------------------------------------------


def _map_status_to_ui(
    status: Optional[str],
) -> Literal["pending", "processed", "error"]:
    """
    Map Firestore job.status -> UI status enum:
      pending | processed | error
    """
    if not status:
        return "processed"

    s = status.upper()

    if s in {"NEW", "PENDING", "QUEUED", "INSPECTED", "CLASSIFIED"} or s.endswith("_IN_PROGRESS"):
        return "pending"
    if s in {"ERROR", "FAILED"}:
        return "error"

    # COMPLETED and everything else -> processed
    return "processed"


# -----------------------------------------------------------------------------
# Root + Activity
# -----------------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "service": "cloud-file-orchestrator-api",
        "endpoints": ["/health", "/rules", "/upload", "/activity"],
    }


@app.get("/activity", response_model=List[ActivityEvent])
def list_activity(limit: int = 20, uid: str = Depends(require_uid)) -> List[ActivityEvent]:
    """
    Return the caller's own recent file processing events, from
    users/{uid}/jobs -- the same subcollection the workers will write to
    once Phase C threads user_id through the pipeline.
    """
    events: List[ActivityEvent] = []

    query = (
        user_jobs_ref(uid)
        .order_by("updated_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    for doc in query.stream():
        data = doc.to_dict() or {}
        job_id = doc.id

        ts_str = data.get("updated_at") or data.get("created_at")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", ""))
        else:
            ts = datetime.utcnow()

        source = data.get("source", {}) or {}
        action = data.get("action", {}) or {}
        classification = data.get("classification", {}) or {}

        bucket = (
            action.get("dest_bucket") or source.get("bucket") or SOURCE_BUCKET or ""
        )
        obj = action.get("dest_blob") or source.get("blob") or ""

        raw_status = data.get("status", "COMPLETED")
        ui_status = _map_status_to_ui(raw_status)

        rule_name = classification.get("matched_rule") or data.get("rule_name")

        actions_list: List[str] = []
        if classification.get("label"):
            actions_list.append(f"classified:{classification['label']}")
        if action.get("dest_folder"):
            actions_list.append(f"moved_to:{action['dest_folder']}")

        events.append(
            ActivityEvent(
                id=job_id,
                timestamp=ts,
                bucket=bucket,
                object=obj,
                status=ui_status,
                rule_name=rule_name,
                actions=actions_list,
                error_message=data.get("error_message"),
            )
        )

    return events
