def serialize(policy):
    return {
        "policy_id": str(policy.policy_id),
        "organization_id": str(policy.organization_id),
        "policy_name": policy.policy_name,
        "policy_description": policy.policy_description,
        "related_service_id": str(policy.related_service_id) if policy.related_service_id else None,
    }
