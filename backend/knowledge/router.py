import os
import re
import shutil
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import KnowledgeDocument
from knowledge.schemas import ManualKnowledgeCreate
from knowledge.service import (
    knowledge_service,
    read_upload_text,
    rebuild_organization_knowledge,
    resolve_knowledge_file_path,
    source_type_for_document_type,
)


router = APIRouter(
    prefix="/knowledge-documents",
    tags=["Knowledge Documents"],
)


# =========================================================
# Upload Directory
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def get_upload_directory() -> Path:
    configured = (os.getenv("UPLOAD_DIR") or "uploads").strip()
    configured_path = Path(configured).expanduser()

    if configured_path.is_absolute():
        upload_dir = configured_path
    else:
        upload_dir = PROJECT_ROOT / configured_path

    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir.resolve()


UPLOAD_DIR = get_upload_directory()
LEGACY_UPLOAD_DIR = BACKEND_ROOT / "uploads"


def migrate_legacy_uploads():
    if not LEGACY_UPLOAD_DIR.exists():
        return
    if LEGACY_UPLOAD_DIR.resolve() == UPLOAD_DIR.resolve():
        return

    for old_file in LEGACY_UPLOAD_DIR.iterdir():
        if not old_file.is_file():
            continue

        new_file = UPLOAD_DIR / old_file.name
        if new_file.exists():
            continue

        try:
            shutil.move(str(old_file), str(new_file))
        except OSError:
            pass

    try:
        if LEGACY_UPLOAD_DIR.exists() and not any(LEGACY_UPLOAD_DIR.iterdir()):
            LEGACY_UPLOAD_DIR.rmdir()
    except OSError:
        pass


migrate_legacy_uploads()


# =========================================================
# Helpers
# =========================================================


def sanitize_filename(filename: str | None) -> str:
    return Path(filename or "document").name


def build_file_path(organization_id: UUID, filename: str) -> Path:
    safe_filename = sanitize_filename(filename)
    return UPLOAD_DIR / f"{organization_id}_{safe_filename}"


def serialize_file_path(file_path: Path) -> str:
    try:
        return str(file_path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(file_path.resolve())


# =========================================================
# Routes
# =========================================================


@router.post("")
async def upload_document(
    organization_id: UUID = Form(...),
    document_type: str = Form("general"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    document_type = document_type.strip().lower()
    if document_type not in {"service", "policy", "general"}:
        raise HTTPException(status_code=400, detail="Invalid document_type")

    original_filename = sanitize_filename(file.filename)
    data = await file.read()

    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    path = build_file_path(organization_id, original_filename)

    try:
        path.write_bytes(data)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {exc}",
        ) from exc

    record = KnowledgeDocument(
        organization_id=organization_id,
        file_name=original_filename,
        file_type=file.content_type or "application/octet-stream",
        file_path=serialize_file_path(path),
        document_type=document_type,
    )

    try:
        db.add(record)
        db.commit()
        db.refresh(record)

        await file.seek(0)
        text = await read_upload_text(file)

        knowledge_service.vector_store.delete_by_filter(
            str(organization_id),
            source_name=record.file_name,
        )

        if text.strip():
            knowledge_service.upsert_text(
                organization_id,
                text,
                source_type_for_document_type(document_type),
                record.file_name,
            )

    except Exception:
        db.rollback()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return {
        "document_id": str(record.document_id),
        "file_name": record.file_name,
        "file_path": record.file_path,
        "document_type": record.document_type,
    }


@router.post("/manual")
def add_manual_knowledge(
    payload: ManualKnowledgeCreate,
    db: Session = Depends(get_db),
):
    """Add a manual knowledge note while keeping Project 1's RAG/indexing flow."""
    title = re.sub(r"[^A-Za-z0-9._ -]+", "_", payload.title).strip(" .") or "knowledge-note"
    display_name = f"{title}.txt"
    physical_name = f"manual-{uuid.uuid4().hex}_{display_name}"
    path = build_file_path(payload.organization_id, physical_name)

    try:
        path.write_text(payload.content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save manual knowledge note: {exc}",
        ) from exc

    record = KnowledgeDocument(
        organization_id=payload.organization_id,
        file_name=display_name,
        file_type="text/plain",
        file_path=serialize_file_path(path),
        document_type="general",
    )

    try:
        # Keep manual notes in the same authoritative uploaded-general path used
        # by Project 1's advanced RAG ranking and reindexing logic.
        knowledge_service.vector_store.delete_by_filter(
            str(payload.organization_id),
            source_name=display_name,
        )
        knowledge_service.upsert_text(
            payload.organization_id,
            payload.content,
            source_type_for_document_type("general"),
            display_name,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return {
        "document_id": str(record.document_id),
        "file_name": record.file_name,
        "file_path": record.file_path,
        "document_type": record.document_type,
        "message": "Manual knowledge note added and indexed successfully",
    }


@router.get("/{organization_id}")
def list_documents(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.organization_id == organization_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )

    return [
        {
            "document_id": str(row.document_id),
            "file_name": row.file_name,
            "file_type": row.file_type,
            "file_path": row.file_path,
            "document_type": row.document_type,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/{organization_id}/reindex")
def reindex_organization_knowledge(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    """Rebuild structured + uploaded RAG data using the current chunking rules."""
    return rebuild_organization_knowledge(db, organization_id)


@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    row = db.get(KnowledgeDocument, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    knowledge_service.vector_store.delete_by_filter(
        str(row.organization_id),
        source_name=row.file_name,
    )

    physical_path = resolve_knowledge_file_path(
        row.file_path,
        filename=row.file_name,
    )

    try:
        physical_path.unlink(missing_ok=True)
    except OSError:
        pass

    db.delete(row)
    db.commit()

    return {"message": "Knowledge document deleted"}
