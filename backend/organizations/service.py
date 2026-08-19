from sqlalchemy.orm import Session
from database.models import Organization, User


def create_organization(db: Session, payload):
    user = db.get(User, payload.user_id)
    if not user:
        raise ValueError("User not found.")
    if user.organization_id:
        raise ValueError("User already belongs to an organization.")
    org = Organization(
        organization_name=payload.organization_name,
        short_description=payload.short_description,
        organization_type=payload.organization_type,
    )
    db.add(org)
    db.flush()
    user.organization_id = org.organization_id
    db.commit()
    db.refresh(org)
    return org


def get_org(db, organization_id):
    org = db.get(Organization, organization_id)
    if not org:
        raise ValueError("Organization not found.")
    return org


def serialize(org):
    return {
        "organization_id": str(org.organization_id),
        "organization_type": org.organization_type,
        "organization_name": org.organization_name,
        "short_description": org.short_description,
        "landing_page_enabled": bool(org.landing_page_enabled),
    }
