from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Policy, Service, User
from knowledge.service import sync_structured_knowledge
from organizations.schemas import CompleteOnboardingRequest, OrganizationCreate, OrganizationUpdate
from organizations.service import create_organization, get_org, serialize

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("")
def create(payload: OrganizationCreate, db: Session = Depends(get_db)):
    try: return serialize(create_organization(db, payload))
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@router.get("/{organization_id}")
def get_profile(organization_id: UUID, db: Session = Depends(get_db)):
    try: return serialize(get_org(db, organization_id))
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc

@router.put("/{organization_id}")
def update_profile(organization_id: UUID, payload: OrganizationUpdate, db: Session = Depends(get_db)):
    try:
        org = get_org(db, organization_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(org, field, value.strip() if isinstance(value, str) else value)
        db.commit(); db.refresh(org)
        from agent.main_agent import MainAgent
        MainAgent._agent_cache.pop(str(organization_id), None)
        return serialize(org)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc

@router.post("/{organization_id}/complete-onboarding")
def complete_onboarding(organization_id: UUID, payload: CompleteOnboardingRequest, db: Session = Depends(get_db)):
    org = get_org(db, organization_id)
    user = db.get(User, payload.user_id)
    if not user or user.organization_id != org.organization_id:
        raise HTTPException(400, "User does not belong to this organization.")

    has_service = db.query(Service.service_id).filter(
        Service.organization_id == organization_id
    ).first()
    if not has_service:
        raise HTTPException(400, "Onboarding requires at least one saved service.")

    has_policy = db.query(Policy.policy_id).filter(
        Policy.organization_id == organization_id
    ).first()
    if not has_policy:
        raise HTTPException(400, "Onboarding requires at least one saved policy.")

    sync_structured_knowledge(db, organization_id)
    user.onboarding_completed = True
    db.commit()
    return {"message": "Onboarding completed", "onboarding_completed": True}
