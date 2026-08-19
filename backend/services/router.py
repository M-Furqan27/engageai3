from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Service
from knowledge.service import read_upload_text, sync_structured_knowledge
from knowledge.structured_parser import missing_required_fields, parse_labeled_records
from services.schemas import ServiceCreate, ServiceUpdate
from services.service import serialize

router = APIRouter(prefix="/services", tags=["Services"])

_SERVICE_LABELS = {
    "service_name": ["service name"],
    "sub_service_name": ["sub-service name", "sub service name"],
    "service_description": ["service description"],
    "service_price": ["service price"],
    "service_requirements": ["service requirements"],
}

_SERVICE_REQUIRED_FIELDS = (
    "service_name",
    "sub_service_name",
    "service_description",
    "service_price",
    "service_requirements",
)

_SERVICE_FORMAT = (
    "Service Name: ... | Sub-Service Name: ... (use None for a standalone service) | "
    "Service Description: ... | Service Price: ... (use None if there is no price) | "
    "Service Requirements: ..."
)


@router.post("")
def create(payload: ServiceCreate, db: Session = Depends(get_db)):
    item = Service(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    sync_structured_knowledge(db, payload.organization_id)
    return serialize(item)


@router.get("/{organization_id}")
def list_services(organization_id: UUID, db: Session = Depends(get_db)):
    return [
        serialize(x)
        for x in db.query(Service)
        .filter(Service.organization_id == organization_id)
        .order_by(Service.created_at)
        .all()
    ]


@router.put("/{service_id}")
def update(service_id: UUID, payload: ServiceUpdate, db: Session = Depends(get_db)):
    item = db.get(Service, service_id)
    if not item:
        raise HTTPException(404, "Service not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    sync_structured_knowledge(db, item.organization_id)
    return serialize(item)


@router.delete("/{service_id}")
def delete(service_id: UUID, db: Session = Depends(get_db)):
    item = db.get(Service, service_id)
    if not item:
        raise HTTPException(404, "Service not found")
    org_id = item.organization_id
    db.delete(item)
    db.commit()
    sync_structured_knowledge(db, org_id)
    return {"message": "Service deleted"}


@router.post("/extract")
async def extract(
    organization_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    text = await read_upload_text(file)
    extracted = parse_labeled_records(text, _SERVICE_LABELS, "service_name")

    if not extracted:
        raise HTTPException(
            422,
            f"Invalid service document format. Use: {_SERVICE_FORMAT}",
        )

    normalized = []
    for index, item in enumerate(extracted, start=1):
        missing = missing_required_fields(item, _SERVICE_REQUIRED_FIELDS)
        if missing:
            readable = ", ".join(field.replace("_", " ").title() for field in missing)
            raise HTTPException(
                422,
                f"Service record {index} is missing required field(s): {readable}. Use: {_SERVICE_FORMAT}",
            )

        sub_service = str(item["sub_service_name"]).strip()
        if sub_service.lower() in {"none", "n/a", "na", "not applicable"}:
            sub_service = None

        price_raw = str(item["service_price"]).strip()
        price = None
        if price_raw.lower() not in {"none", "n/a", "na", "not applicable", "free"}:
            cleaned_price = price_raw.replace(",", "")
            cleaned_price = cleaned_price.replace("PKR", "").replace("pkr", "").strip()
            try:
                price = Decimal(cleaned_price)
            except (InvalidOperation, ValueError):
                raise HTTPException(
                    422,
                    f"Service record {index} has an invalid Service Price. Use a number or None.",
                )

        normalized.append(
            ServiceCreate(
                organization_id=organization_id,
                service_name=item["service_name"],
                sub_service_name=sub_service,
                service_description=item["service_description"],
                service_price=price,
                service_requirements=item["service_requirements"],
            )
        )

    created = []
    for payload in normalized:
        obj = Service(**payload.model_dump())
        db.add(obj)
        created.append(obj)

    db.commit()
    for obj in created:
        db.refresh(obj)
    sync_structured_knowledge(db, organization_id)

    return {"count": len(created), "services": [serialize(x) for x in created]}
