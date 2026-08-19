from azure.ai.projects.models import FunctionTool


def build_tools():

    return [

        FunctionTool(
            name="knowledge_search",
            description=(
                "Search this organization's authoritative structured offerings, "
                "policies, FAQs, and uploaded business information. Use before "
                "organization-related answers. Only structured service records "
                "should be treated as actual offerings. For catalogue/list/"
                "comparison requests, return complete structured offering results."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The visitor's organization-related question, preserving "
                            "important offering names, sub-services, pricing, "
                            "requirements, policies, routes, quantities, and intent."
                        ),
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            strict=True,
        ),

        FunctionTool(
            name="capture_visitor_interest",
            description=(
                "Silently save useful lead information after genuine purchase/use "
                "interest exists and visitor information is available. This is NOT "
                "representative escalation and NOT a service booking. Do not ask the "
                "visitor for permission to save the lead and do not mention internal "
                "lead storage/status. Continue helping the visitor after this call."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "visitor_id": {
                        "type": "string"
                    },
                    "name": {
                        "type": ["string", "null"]
                    },
                    "email": {
                        "type": ["string", "null"]
                    },
                    "service_name": {
                        "type": ["string", "null"]
                    },
                    "sub_service_name": {
                        "type": ["string", "null"]
                    },
                    "service_required_info": {
                        "type": ["string", "null"],
                        "description": (
                            "JSON object string containing only information the "
                            "visitor actually provided that relates to explicit "
                            "structured offering requirements. Do not invent values."
                        ),
                    },
                },
                "required": [
                    "visitor_id",
                    "name",
                    "email",
                    "service_name",
                    "sub_service_name",
                    "service_required_info",
                ],
                "additionalProperties": False,
            },
            strict=True,
        ),

        FunctionTool(
            name="check_available_slots",
            description=(
                "Check REPRESENTATIVE MEETING availability only after the visitor "
                "has clearly finalized a specific available offering. Never use for "
                "service/product booking, service availability, delivery/pickup "
                "availability, browsing, comparison, vague interest, guidance, or "
                "objections. Name, Email, finalized service/sub-service, and relevant "
                "visitor-providable structured requirement information must already "
                "be collected. offering_finalized must be true only after explicit "
                "visitor commitment."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "visitor_id": {
                        "type": "string"
                    },
                    "name": {
                        "type": "string"
                    },
                    "email": {
                        "type": "string"
                    },
                    "service_name": {
                        "type": "string"
                    },
                    "sub_service_name": {
                        "type": ["string", "null"]
                    },
                    "service_required_info": {
                        "type": "string",
                        "description": (
                            "JSON object string containing only collected "
                            "visitor-provided structured requirement values."
                        ),
                    },
                    "offering_finalized": {
                        "type": "boolean",
                        "description": (
                            "True only after explicit commitment to the selected "
                            "available offering."
                        ),
                    },
                },
                "required": [
                    "visitor_id",
                    "name",
                    "email",
                    "service_name",
                    "sub_service_name",
                    "service_required_info",
                    "offering_finalized",
                ],
                "additionalProperties": False,
            },
            strict=True,
        ),

        FunctionTool(
            name="create_meeting_event",
            description=(
                "Create a REPRESENTATIVE MEETING only after check_available_slots "
                "returned slots and the visitor selected one exact returned slot. "
                "This tool does not book or execute the organization's underlying "
                "product/service."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "visitor_id": {
                        "type": "string"
                    },
                    "name": {
                        "type": "string"
                    },
                    "email": {
                        "type": "string"
                    },
                    "service_name": {
                        "type": "string"
                    },
                    "sub_service_name": {
                        "type": ["string", "null"]
                    },
                    "service_required_info": {
                        "type": "string"
                    },
                    "offering_finalized": {
                        "type": "boolean"
                    },
                    "slot_start": {
                        "type": "string"
                    },
                    "slot_end": {
                        "type": "string"
                    },
                },
                "required": [
                    "visitor_id",
                    "name",
                    "email",
                    "service_name",
                    "sub_service_name",
                    "service_required_info",
                    "offering_finalized",
                    "slot_start",
                    "slot_end",
                ],
                "additionalProperties": False,
            },
            strict=True,
        ),
    ]