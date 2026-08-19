from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Policy, Service
from knowledge.service import read_upload_text, sync_structured_knowledge
from knowledge.structured_parser import missing_required_fields, parse_labeled_records
from policies.schemas import PolicyCreate, PolicyUpdate
from policies.service import serialize

router = APIRouter(prefix="/policies", tags=["Policies"])

_POLICY_LABELS = {
    "policy_name": ["policy name"],
    "policy_description": ["policy description"],
    "related_service": ["related service"],
}

_POLICY_REQUIRED_FIELDS = (
    "policy_name",
    "policy_description",
    "related_service",
)

_POLICY_FORMAT = (
    "Policy Name: ... | Policy Description: ... | "
    "Related Service: ... (use General or None if it is not tied to a service)"
)


@router.post("")
def create(payload: PolicyCreate, db: Session = Depends(get_db)):
    item = Policy(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    sync_structured_knowledge(db, payload.organization_id)
    return serialize(item)


@router.get("/{organization_id}")
def list_policies(organization_id: UUID, db: Session = Depends(get_db)):
    return [
        serialize(x)
        for x in db.query(Policy)
        .filter(Policy.organization_id == organization_id)
        .order_by(Policy.created_at)
        .all()
    ]


@router.put("/{policy_id}")
def update(policy_id: UUID, payload: PolicyUpdate, db: Session = Depends(get_db)):
    item = db.get(Policy, policy_id)
    if not item:
        raise HTTPException(404, "Policy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    sync_structured_knowledge(db, item.organization_id)
    return serialize(item)


@router.delete("/{policy_id}")
def delete(policy_id: UUID, db: Session = Depends(get_db)):
    item = db.get(Policy, policy_id)
    if not item:
        raise HTTPException(404, "Policy not found")
    org_id = item.organization_id
    db.delete(item)
    db.commit()
    sync_structured_knowledge(db, org_id)
    return {"message": "Policy deleted"}


@router.post("/extract")
async def extract(
    organization_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    text = await read_upload_text(file)
    extracted = parse_labeled_records(text, _POLICY_LABELS, "policy_name")

    if not extracted:
        raise HTTPException(
            422,
            f"Invalid policy document format. Use: {_POLICY_FORMAT}",
        )

    for index, item in enumerate(extracted, start=1):
        missing = missing_required_fields(item, _POLICY_REQUIRED_FIELDS)
        if missing:
            readable = ", ".join(field.replace("_", " ").title() for field in missing)
            raise HTTPException(
                422,
                f"Policy record {index} is missing required field(s): {readable}. Use: {_POLICY_FORMAT}",
            )

    org_services = db.query(Service).filter(Service.organization_id == organization_id).all()

    def match_service_id(name):
        if not name:
            return None
        low = str(name).strip().lower()
        if low in {"none", "general", "n/a", "na", "not applicable"}:
            return None
        for service in org_services:
            service_name = service.service_name.lower()
            if service_name == low or service_name in low or low in service_name:
                return service.service_id
        return None

    created = []
    for item in extracted:
        payload = PolicyCreate(
            organization_id=organization_id,
            policy_name=item["policy_name"],
            policy_description=item["policy_description"],
            related_service_id=match_service_id(item["related_service"]),
        )
        obj = Policy(**payload.model_dump())
        db.add(obj)
        created.append(obj)

    db.commit()
    for obj in created:
        db.refresh(obj)
    sync_structured_knowledge(db, organization_id)

    return {"count": len(created), "policies": [serialize(x) for x in created]}
