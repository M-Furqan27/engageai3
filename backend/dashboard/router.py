from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Conversation, Visitor

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/{organization_id}/summary")
def summary(organization_id: UUID, db: Session = Depends(get_db)):
    total_visitors = db.query(func.count(Visitor.visitor_id)).filter(Visitor.organization_id == organization_id).scalar() or 0
    total_conversations = db.query(func.count(Conversation.conversation_id)).filter(Conversation.organization_id == organization_id).scalar() or 0
    followups = db.query(func.count(Visitor.visitor_id)).filter(
        Visitor.organization_id == organization_id,
        Visitor.status == "Needs Follow-Up",
    ).scalar() or 0
    meetings = db.query(func.count(Visitor.visitor_id)).filter(
        Visitor.organization_id == organization_id,
        Visitor.meeting_datetime.isnot(None),
    ).scalar() or 0
    return {
        "total_visitors": total_visitors,
        "total_conversations": total_conversations,
        "needs_follow_up": followups,
        "meetings_scheduled": meetings,
    }


@router.get("/{organization_id}/recent-activity")
def recent(organization_id: UUID, db: Session = Depends(get_db)):
    rows = (
        db.query(Visitor)
        .filter(Visitor.organization_id == organization_id)
        .order_by(Visitor.updated_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "visitor_id": str(v.visitor_id),
            "visitor_name": v.visitor_name,
            "visitor_email": v.visitor_email,
            "interested_service": v.interested_service.service_name if v.interested_service else None,
            "status": v.status,
            "last_activity": v.updated_at,
        }
        for v in rows
    ]


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _period_dates(period: str, today: date, earliest: date | None, latest: date | None) -> tuple[date, date]:
    if period == "7d":
        return today - timedelta(days=6), today
    if period == "30d":
        return today - timedelta(days=29), today
    if period == "90d":
        return today - timedelta(days=89), today
    if period == "6m":
        return today - timedelta(days=182), today
    if period == "1y":
        return today - timedelta(days=364), today
    if period == "all":
        start = earliest or (today - timedelta(days=29))
        end = max(today, latest) if latest else today
        return start, end
    raise HTTPException(status_code=400, detail="Unsupported meeting trend period")


@router.get("/{organization_id}/meeting-trend")
def meeting_trend(
    organization_id: UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d|6m|1y|all|custom)$"),
    start_date: date | None = None,
    end_date: date | None = None,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    db: Session = Depends(get_db),
):
    """Daily meeting counts for meetings created through the chatbot booking flow.

    `meeting_datetime` is only populated when the agent's create_meeting_event tool
    succeeds, so this chart stays focused on chatbot-scheduled meetings.
    """
    # JavaScript getTimezoneOffset() returns UTC - local time. Invert it here.
    local_tz = timezone(timedelta(minutes=-tz_offset_minutes))
    today_local = datetime.now(timezone.utc).astimezone(local_tz).date()

    all_datetimes = [
        row[0]
        for row in db.query(Visitor.meeting_datetime)
        .filter(
            Visitor.organization_id == organization_id,
            Visitor.meeting_datetime.isnot(None),
        )
        .all()
        if row[0] is not None
    ]

    localized_dates = [
        _as_aware_utc(value).astimezone(local_tz).date()
        for value in all_datetimes
    ]
    earliest = min(localized_dates) if localized_dates else None
    latest = max(localized_dates) if localized_dates else None

    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Custom range requires start_date and end_date")
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
        range_start, range_end = start_date, end_date
    else:
        range_start, range_end = _period_dates(period, today_local, earliest, latest)

    # Limit counting to the selected local calendar dates while preserving timezone correctness.
    start_local = datetime.combine(range_start, time.min, tzinfo=local_tz)
    end_local_exclusive = datetime.combine(range_end + timedelta(days=1), time.min, tzinfo=local_tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local_exclusive.astimezone(timezone.utc)

    selected_datetimes = [
        row[0]
        for row in db.query(Visitor.meeting_datetime)
        .filter(
            Visitor.organization_id == organization_id,
            Visitor.meeting_datetime.isnot(None),
            Visitor.meeting_datetime >= start_utc,
            Visitor.meeting_datetime < end_utc,
        )
        .all()
        if row[0] is not None
    ]

    counts = Counter(
        _as_aware_utc(value).astimezone(local_tz).date()
        for value in selected_datetimes
    )

    number_of_days = (range_end - range_start).days + 1
    points = []
    for offset in range(number_of_days):
        day = range_start + timedelta(days=offset)
        points.append({"date": day.isoformat(), "count": counts.get(day, 0)})

    total = sum(point["count"] for point in points)
    peak_count = max((point["count"] for point in points), default=0)
    peak_day = next((point["date"] for point in points if point["count"] == peak_count and peak_count > 0), None)

    today_count = sum(1 for day in localized_dates if day == today_local)

    return {
        "period": period,
        "start_date": range_start.isoformat(),
        "end_date": range_end.isoformat(),
        "today": today_local.isoformat(),
        "today_count": today_count,
        "total": total,
        "peak_day": peak_day,
        "peak_count": peak_count,
        "points": points,
    }
