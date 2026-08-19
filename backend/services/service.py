from database.models import Service

def serialize(service):
    return {
        "service_id": str(service.service_id),
        "organization_id": str(service.organization_id),
        "service_name": service.service_name,
        "sub_service_name": service.sub_service_name,
        "service_description": service.service_description,
        "service_price": float(service.service_price) if service.service_price is not None else None,
        "service_requirements": service.service_requirements,
    }
