from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Visitor
from visitors.schemas import VisitorStatusUpdate
from visitors.service import serialize

router=APIRouter(prefix="/visitors", tags=["Visitors / Leads"])
VALID={"Visitor","Needs Follow-Up","Meeting Scheduled"}

@router.get("/detail/{visitor_id}")
def detail(visitor_id: UUID, db: Session=Depends(get_db)):
    row=db.get(Visitor, visitor_id)
    if not row: raise HTTPException(404,"Visitor not found")
    return serialize(row)

@router.get("/{organization_id}")
def list_visitors(organization_id: UUID, status: str | None = Query(None), db: Session=Depends(get_db)):
    query=db.query(Visitor).filter(Visitor.organization_id==organization_id)
    if status: query=query.filter(Visitor.status==status)
    return [serialize(x) for x in query.order_by(Visitor.updated_at.desc()).all()]

@router.put("/{visitor_id}/status")
def update_status(visitor_id: UUID, payload: VisitorStatusUpdate, db: Session=Depends(get_db)):
    if payload.status not in VALID: raise HTTPException(400,"Invalid visitor status")
    row=db.get(Visitor, visitor_id)
    if not row: raise HTTPException(404,"Visitor not found")
    row.status=payload.status; db.commit(); db.refresh(row); return serialize(row)
