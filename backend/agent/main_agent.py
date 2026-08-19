import json
import logging
import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput

from agent.prompt_builder import PromptBuilder
from agent.tools import build_tools
from conversations.service import add_message, history
from database.database import get_session
from database.models import Organization, Service, Visitor
from knowledge.service import knowledge_service
from visitors.service import set_meeting_scheduled
from workflows.n8n_client import n8n_client


logger = logging.getLogger(__name__)


class MainAgent:

    _agent_cache = {}

    def __init__(self):

        self.project_endpoint = os.getenv(
            "PROJECT_ENDPOINT"
        )

        self.model_deployment = os.getenv(
            "MODEL_DEPLOYMENT_NAME"
        )

        self.prompt_builder = PromptBuilder()

    # =====================================================
    # Organization Context
    # =====================================================

    def _context(
        self,
        db,
        organization_id,
    ):

        organization = db.get(
            Organization,
            organization_id,
        )

        if not organization:
            raise ValueError(
                "Organization not found"
            )

        return {
            "organization": {
                "organization_name":
                    organization.organization_name,

                "short_description":
                    organization.short_description,

                "organization_type":
                    organization.organization_type,
            }
        }

    # =====================================================
    # Agent Creation
    # =====================================================

    def create_agent(
        self,
        organization_id,
        force=False,
    ):

        cache_key = str(
            organization_id
        )

        if (
            cache_key in self._agent_cache
            and not force
        ):
            return self._agent_cache[
                cache_key
            ]

        db = get_session()

        try:

            context = self._context(
                db,
                organization_id,
            )

            instructions = (
                self.prompt_builder.build_prompt(
                    context
                )
            )

        finally:

            db.close()

        with DefaultAzureCredential() as credential:

            with AIProjectClient(
                endpoint=self.project_endpoint,
                credential=credential,
            ) as project_client:

                agent = (
                    project_client.agents
                    .create_version(
                        agent_name=(
                            f"organization-"
                            f"{organization_id}-agent"
                        ),
                        definition=PromptAgentDefinition(
                            model=self.model_deployment,
                            instructions=instructions,
                            tools=build_tools(),
                        ),
                    )
                )

        agent_reference = {
            "name": agent.name,
            "version": str(
                agent.version
            ),
        }

        self._agent_cache[
            cache_key
        ] = agent_reference

        return agent_reference

    # =====================================================
    # Helpers
    # =====================================================

    @staticmethod
    def _normalize(
        value,
    ):

        return (
            value or ""
        ).strip().lower()

    def _service_by_name(
        self,
        db,
        organization_id,
        service_name,
        sub_service_name=None,
    ):

        if not service_name:
            return None

        services = (
            db.query(Service)
            .filter(
                Service.organization_id
                == organization_id
            )
            .all()
        )

        service_value = (
            self._normalize(
                service_name
            )
        )

        sub_service_value = (
            self._normalize(
                sub_service_name
            )
        )

        # -------------------------------------------------
        # Exact Service + Sub-Service Match
        # -------------------------------------------------

        if sub_service_value:

            for service in services:

                if (
                    self._normalize(
                        service.service_name
                    )
                    == service_value
                    and
                    self._normalize(
                        service.sub_service_name
                    )
                    == sub_service_value
                ):
                    return service

        # -------------------------------------------------
        # Sub-Service Name Match
        # -------------------------------------------------

        for service in services:

            if (
                service.sub_service_name
                and
                self._normalize(
                    service.sub_service_name
                )
                == service_value
            ):
                return service

        # -------------------------------------------------
        # Service Name Match
        # -------------------------------------------------

        matches = [
            service
            for service in services
            if self._normalize(
                service.service_name
            ) == service_value
        ]

        if len(matches) == 1:
            return matches[0]

        # If multiple sub-services exist under the same
        # service, do not silently guess one.
        if len(matches) > 1:
            return None

        return None

    @staticmethod
    def _parse_required_info(
        value,
    ):

        if value is None:
            return None

        if isinstance(
            value,
            dict,
        ):
            return value

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            if not value:
                return None

            try:

                parsed = json.loads(
                    value
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

                return {
                    "details": parsed
                }

            except json.JSONDecodeError:

                return {
                    "details": value
                }

        return {
            "details": value
        }

    def _update_visitor(
        self,
        db,
        organization_id,
        visitor,
        args,
        mark_interested=False,
    ):

        name = args.get(
            "name"
        )

        email = args.get(
            "email"
        )

        service_name = args.get(
            "service_name"
        )

        sub_service_name = args.get(
            "sub_service_name"
        )

        if name:
            visitor.visitor_name = (
                name.strip()
            )

        if email:
            visitor.visitor_email = (
                email.strip()
            )

        service = None

        if service_name:

            service = self._service_by_name(
                db,
                organization_id,
                service_name,
                sub_service_name,
            )

            if service:

                visitor.interested_service_id = (
                    service.service_id
                )

                visitor.sub_service_name = (
                    sub_service_name
                    or
                    service.sub_service_name
                )

        required_info = (
            self._parse_required_info(
                args.get(
                    "service_required_info"
                )
            )
        )

        if required_info is not None:

            existing = (
                visitor.service_required_info
                or {}
            )

            if not isinstance(
                existing,
                dict,
            ):
                existing = {}

            visitor.service_required_info = {
                **existing,
                **required_info,
            }

        if (
            mark_interested
            and
            visitor.status == "Visitor"
        ):
            visitor.status = (
                "Needs Follow-Up"
            )

        db.commit()

        db.refresh(
            visitor
        )

        return service

    def _require_meeting_ready(
        self,
        visitor,
        service,
        args,
    ):

        if (
            args.get("offering_finalized")
            is not True
        ):
            raise ValueError(
                "The visitor has not clearly finalized "
                "the selected offering."
            )

        if not service:
            raise ValueError(
                "A valid finalized service must be selected "
                "before representative scheduling."
            )

        if not visitor.visitor_name:
            raise ValueError(
                "Visitor name is required before scheduling."
            )

        if not visitor.visitor_email:
            raise ValueError(
                "Visitor email is required before scheduling."
            )

        requirements = (
            service.service_requirements
            or ""
        ).strip()

        # Treat these values as NO requirements
        no_requirements = {
            "",
            "none",
            "not specified",
            "n/a",
            "na",
            "not required",
            "Not specified in the current knowledge base.",
            "Not specified in the document."
        }

        if requirements.lower() in no_requirements:
            return

        collected_requirements = (
            visitor.service_required_info
            or {}
        )

        if not collected_requirements:
            raise ValueError(
                "The selected service requirements must be "
                "collected before representative scheduling."
            )

    def _build_base_payload(
        self,
        organization_id,
        visitor,
        service=None,
    ):

        if (
            service is None
            and visitor.interested_service_id
        ):
            # Caller may populate service separately when needed.
            service_name = None
            sub_service_name = (
                visitor.sub_service_name
            )

        else:

            service_name = (
                service.service_name
                if service
                else None
            )

            sub_service_name = (
                visitor.sub_service_name
                or (
                    service.sub_service_name
                    if service
                    else None
                )
            )

        return {
            "organization_id":
                str(
                    organization_id
                ),

            "visitor_id":
                str(
                    visitor.visitor_id
                ),

            "name":
                visitor.visitor_name,

            "email":
                visitor.visitor_email,

            "service_name":
                service_name,

            "sub_service_name":
                sub_service_name,

            "service_required_info":
                visitor.service_required_info
                or {},
        }

    @staticmethod
    def _workflow_succeeded(
        result,
    ):

        if result is None:
            return False

        if isinstance(
            result,
            dict,
        ):

            if (
                result.get(
                    "success"
                )
                is False
            ):
                return False

            status = str(
                result.get(
                    "status",
                    "",
                )
            ).lower()

            if status in {
                "error",
                "failed",
                "failure",
            }:
                return False

        return True

    # =====================================================
    # Tool Dispatcher
    # =====================================================

    def _dispatch_tool(
        self,
        db,
        organization_id,
        visitor,
        name,
        args,
    ):

        # -------------------------------------------------
        # Knowledge Search
        # -------------------------------------------------

        if name == "knowledge_search":

            return knowledge_service.search(
                organization_id,
                args["query"],
            )

        # -------------------------------------------------
        # Active Visitor Context
        # -------------------------------------------------

        # The visitor identity is owned by the backend request, not by the
        # language model. A tool call may contain a stale/generated visitor_id
        # (especially after duplicate-email visitor reconciliation), so always
        # replace it with the canonical active visitor before dispatching.
        args = dict(args or {})
        args["visitor_id"] = str(visitor.visitor_id)

        # -------------------------------------------------
        # Capture Interest
        # -------------------------------------------------

        if name == "capture_visitor_interest":

            service = self._update_visitor(
                db=db,
                organization_id=organization_id,
                visitor=visitor,
                args=args,
                mark_interested=True,
            )

            return {
                "success": True,
                "visitor_id":
                    str(
                        visitor.visitor_id
                    ),
                "status":
                    visitor.status,
                "name":
                    visitor.visitor_name,
                "email":
                    visitor.visitor_email,
                "service_name":
                    (
                        service.service_name
                        if service
                        else args.get(
                            "service_name"
                        )
                    ),
                "sub_service_name":
                    visitor.sub_service_name,
                "service_required_info":
                    visitor.service_required_info
                    or {},
                "message":
                    "Visitor interest saved successfully.",
            }

        # -------------------------------------------------
        # Check Available Representative Slots
        # -------------------------------------------------

        if name == "check_available_slots":

            service = self._update_visitor(
                db=db,
                organization_id=organization_id,
                visitor=visitor,
                args=args,
                mark_interested=True,
            )

            self._require_meeting_ready(
                visitor=visitor,
                service=service,
                args=args,
            )

            payload = (
                self._build_base_payload(
                    organization_id,
                    visitor,
                    service,
                )
            )

            return n8n_client.check_slots(
                payload
            )

        # -------------------------------------------------
        # Create Representative Meeting
        # -------------------------------------------------

        if name == "create_meeting_event":

            service = self._update_visitor(
                db=db,
                organization_id=organization_id,
                visitor=visitor,
                args=args,
                mark_interested=True,
            )

            self._require_meeting_ready(
                visitor=visitor,
                service=service,
                args=args,
            )

            payload = {
                **self._build_base_payload(
                    organization_id,
                    visitor,
                    service,
                ),
                "slot_start":
                    args["slot_start"],
                "slot_end":
                    args["slot_end"],
            }

            result = (
                n8n_client.create_meeting(
                    payload
                )
            )

            if not self._workflow_succeeded(
                result
            ):
                raise RuntimeError(
                    "Representative meeting was not created."
                )

            set_meeting_scheduled(
                db,
                visitor,
                args["slot_start"],
            )

            db.refresh(
                visitor
            )

            return result

        raise ValueError(
            f"Unsupported tool: {name}"
        )

    # =====================================================
    # Safe Tool Error
    # =====================================================

    def _safe_tool_error(
        self,
        tool_name,
        error,
    ):

        logger.exception(
            "Agent tool failed: %s",
            tool_name,
        )

        if tool_name == "knowledge_search":

            return {
                "success": False,
                "error": (
                    "Organization knowledge is temporarily "
                    "unavailable. Do not invent an answer."
                ),
            }

        if tool_name in {
            "check_available_slots",
            "create_meeting_event",
        }:

            return {
                "success": False,
                "error": (
                    "Representative meeting scheduling is "
                    "currently unavailable. Do not invent "
                    "availability or claim that a meeting "
                    "was created."
                ),
            }

        if tool_name == "capture_visitor_interest":

            return {
                "success": False,
                "error": (
                    "Visitor interest could not be saved "
                    "at this time."
                ),
            }

        return {
            "success": False,
            "error": (
                "The requested action could not be completed."
            ),
        }

    # =====================================================
    # Chat
    # =====================================================

    def chat(
        self,
        organization_id,
        visitor_id,
        conversation_id,
        message,
    ):

        db = get_session()

        try:

            visitor = db.get(
                Visitor,
                visitor_id,
            )

            if (
                not visitor
                or
                visitor.organization_id
                != organization_id
            ):
                raise ValueError(
                    "Visitor not found for organization"
                )

            # ---------------------------------------------
            # Save Visitor Message
            # ---------------------------------------------

            add_message(
                db,
                conversation_id,
                "visitor",
                message,
            )

            # ---------------------------------------------
            # Build Conversation History
            # ---------------------------------------------

            messages = []

            for item in history(
                db,
                conversation_id,
            ):

                messages.append(
                    {
                        "role": (
                            "user"
                            if item.sender
                            == "visitor"
                            else "assistant"
                        ),
                        "content":
                            item.message,
                    }
                )

            # ---------------------------------------------
            # Get Agent
            # ---------------------------------------------

            agent_reference = (
                self.create_agent(
                    organization_id
                )
            )

            # ---------------------------------------------
            # Azure Agent Execution
            # ---------------------------------------------

            with DefaultAzureCredential() as credential:

                with AIProjectClient(
                    endpoint=self.project_endpoint,
                    credential=credential,
                ) as project_client:

                    with (
                        project_client
                        .get_openai_client()
                    ) as openai_client:

                        response = (
                            openai_client.responses
                            .create(
                                extra_body={
                                    "agent_reference": {
                                        "name":
                                            agent_reference[
                                                "name"
                                            ],
                                        "type":
                                            "agent_reference",
                                        "version":
                                            agent_reference[
                                                "version"
                                            ],
                                    }
                                },
                                input=messages,
                            )
                        )

                        # ---------------------------------
                        # Tool Loop
                        # ---------------------------------

                        for _ in range(8):

                            function_calls = [
                                output
                                for output
                                in response.output
                                if output.type
                                == "function_call"
                            ]

                            if not function_calls:
                                break

                            outputs = []

                            for call in function_calls:

                                try:

                                    arguments = (
                                        json.loads(
                                            call.arguments
                                        )
                                    )

                                    result = (
                                        self._dispatch_tool(
                                            db=db,
                                            organization_id=organization_id,
                                            visitor=visitor,
                                            name=call.name,
                                            args=arguments,
                                        )
                                    )

                                except Exception as exc:

                                    result = (
                                        self._safe_tool_error(
                                            call.name,
                                            exc,
                                        )
                                    )

                                outputs.append(
                                    FunctionCallOutput(
                                        type="function_call_output",
                                        call_id=call.call_id,
                                        output=json.dumps(
                                            result,
                                            default=str,
                                        ),
                                    )
                                )

                            response = (
                                openai_client.responses
                                .create(
                                    previous_response_id=response.id,
                                    input=outputs,
                                    extra_body={
                                        "agent_reference": {
                                            "name":
                                                agent_reference[
                                                    "name"
                                                ],
                                            "type":
                                                "agent_reference",
                                            "version":
                                                agent_reference[
                                                    "version"
                                                ],
                                        }
                                    },
                                )
                            )

                        text = (
                            response.output_text
                            or (
                                "I’m sorry, I couldn’t "
                                "generate a response."
                            )
                        )

            # ---------------------------------------------
            # Save Agent Response
            # ---------------------------------------------

            add_message(
                db,
                conversation_id,
                "agent",
                text,
            )

            return text

        finally:

            db.close()


main_agent = MainAgent()
