import io
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
from dotenv import load_dotenv
from fastapi import UploadFile
from sqlalchemy.orm import Session

from database.models import KnowledgeDocument, Policy, Service
from knowledge.chunker import TextChunker
from knowledge.embedding import EmbeddingService
from knowledge.knowledge_builder import KnowledgeBuilder
from knowledge.schemas import Chunk, ExtractedDocument
from knowledge.vector_store import VectorStore

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

UPLOADED_SOURCE_TYPES = {
    "service": "uploaded_service",
    "policy": "uploaded_policy",
    "general": "uploaded_general",
}

ALL_UPLOADED_SOURCE_TYPES = [
    "uploaded_document",   # legacy source type
    "uploaded_service",
    "uploaded_policy",
    "uploaded_general",
]


class KnowledgeService:
    def __init__(self):
        self.chunker = TextChunker()
        self.embedding = EmbeddingService(api_key=os.getenv("GEMINI_API_KEY"))
        self.builder = KnowledgeBuilder()
        self.vector_store = VectorStore()

    def _index_documents(self, organization_id, documents):
        chunks = self.chunker.split(documents)
        embedded = self.embedding.generate(chunks)
        kb = self.builder.build(str(organization_id), embedded)
        self.vector_store.upsert(kb)
        return kb

    def upsert_text(
        self,
        organization_id,
        text,
        source_type,
        source_name,
        section=None,
    ):
        if not text or not text.strip():
            return None

        document = ExtractedDocument(
            source_type=source_type,
            source_name=source_name,
            section=section,
            content=text.strip(),
        )

        return self._index_documents(organization_id, [document])

    @staticmethod
    def _tokens(text: str) -> set[str]:
        stop_words = {
            "the", "a", "an", "and", "or", "to", "of", "for", "in",
            "on", "is", "are", "do", "does", "did", "can", "could",
            "would", "should", "i", "me", "my", "we", "you", "your",
            "what", "how", "when", "where", "why", "which", "with",
            "about", "tell", "please", "all", "any", "our", "their",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(token) > 1 and token not in stop_words
        }

    @staticmethod
    def _query_intent(query: str) -> str:
        low = (query or "").lower()

        policy_terms = {
            "policy", "refund", "cancel", "cancellation", "reschedule",
            "return", "guarantee", "warranty", "eligible", "eligibility",
            "deduct", "penalty", "weather", "rain", "rule", "terms",
        }
        service_terms = {
            "service", "services", "price", "cost", "fee", "requirement",
            "requirements", "package", "packages", "catalogue", "catalog",
            "offering", "offerings", "book", "booking", "inspection",
        }

        if any(term in low for term in policy_terms):
            return "policy"
        if any(term in low for term in service_terms):
            return "service"
        return "general"

    @staticmethod
    def _is_service_enumeration(query: str) -> bool:
        low = (query or "").lower()
        phrases = (
            "all services",
            "all paid services",
            "how many services",
            "list services",
            "list the services",
            "compare services",
            "compare all",
            "service catalogue",
            "service catalog",
            "what services",
            "which services",
            "your services",
            "your offerings",
            "all offerings",
            "all packages",
        )
        return any(phrase in low for phrase in phrases)

    @staticmethod
    def _is_policy_enumeration(query: str) -> bool:
        low = (query or "").lower()
        phrases = (
            "all policies",
            "list policies",
            "list the policies",
            "what policies",
            "your policies",
            "business policies",
        )
        return any(phrase in low for phrase in phrases)

    @staticmethod
    def _effective_kind(result: dict) -> str:
        source_type = (result.get("source_type") or "").lower()
        source_name = (result.get("source_name") or "").lower()

        if source_type == "structured_service":
            return "structured_service"
        if source_type == "structured_policy":
            return "structured_policy"
        if source_type == "uploaded_service":
            return "uploaded_service"
        if source_type == "uploaded_policy":
            return "uploaded_policy"
        if source_type == "uploaded_general":
            return "uploaded_general"

        # Backward compatibility for already indexed legacy uploaded_document
        # entries. Filename hints improve ranking until the user reindexes.
        if source_type == "uploaded_document":
            if any(word in source_name for word in ("policy", "policies", "refund", "cancellation")):
                return "uploaded_policy"
            if any(word in source_name for word in ("service", "package", "catalog", "catalogue")):
                return "uploaded_service"
            return "uploaded_general"

        return source_type or "unknown"

    def _priority(self, result: dict, intent: str) -> int:
        kind = self._effective_kind(result)

        if intent == "policy":
            priorities = {
                "structured_policy": 120,
                "uploaded_policy": 105,
                "structured_service": 85,
                "uploaded_service": 70,
                "uploaded_general": 65,
            }
        elif intent == "service":
            priorities = {
                "structured_service": 120,
                "uploaded_service": 100,
                "structured_policy": 80,
                "uploaded_policy": 70,
                "uploaded_general": 65,
            }
        else:
            priorities = {
                "uploaded_general": 105,
                "structured_service": 95,
                "structured_policy": 95,
                "uploaded_service": 90,
                "uploaded_policy": 90,
            }

        return priorities.get(kind, 50)

    def _rerank(self, query: str, results: list[dict], intent: str) -> list[dict]:
        query_tokens = self._tokens(query)
        reranked = []

        for original_rank, result in enumerate(results):
            content_tokens = self._tokens(result.get("content", ""))
            overlap = len(query_tokens & content_tokens)
            source_priority = self._priority(result, intent)
            search_score = float(result.get("search_score", 0.0) or 0.0)

            # Source authority is intentionally strong, but lexical overlap and
            # the Azure hybrid rank still preserve semantic relevance.
            ranking_score = (
                source_priority
                + (overlap * 8)
                + min(search_score, 10.0)
                + max(0, 10 - original_rank)
            )

            enriched = dict(result)
            enriched["authority"] = self._effective_kind(result)
            enriched["ranking_score"] = round(ranking_score, 4)
            reranked.append(enriched)

        reranked.sort(key=lambda item: item["ranking_score"], reverse=True)
        return reranked

    @staticmethod
    def _deduplicate(results: list[dict]) -> list[dict]:
        seen = set()
        unique = []

        for result in results:
            key = (
                result.get("source_type"),
                result.get("source_name"),
                result.get("content"),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(result)

        return unique

    def search(self, organization_id, query):
        query_chunk = Chunk(
            text=query,
            chunk_index=0,
            source_type="query",
            source_name="user_query",
        )

        embedded = self.embedding.generate([query_chunk])
        if not embedded:
            return {
                "query": query,
                "intent": "unknown",
                "results": [],
            }

        intent = self._query_intent(query)

        candidates = self.vector_store.search(
            str(organization_id),
            query=query,
            query_embedding=embedded[0].embedding,
            top_k=18,
        )

        # Broad catalogue/policy questions need complete authoritative records,
        # not only the nearest vector matches.
        if self._is_service_enumeration(query):
            candidates = (
                self.vector_store.list_by_source_types(
                    str(organization_id),
                    ["structured_service"],
                    top=100,
                )
                + candidates
            )

        if self._is_policy_enumeration(query):
            candidates = (
                self.vector_store.list_by_source_types(
                    str(organization_id),
                    ["structured_policy"],
                    top=100,
                )
                + candidates
            )

        candidates = self._deduplicate(candidates)
        ranked = self._rerank(query, candidates, intent)

        # Keep enough context for comparisons while limiting prompt noise.
        result_limit = 50 if (
            self._is_service_enumeration(query)
            or self._is_policy_enumeration(query)
        ) else 8

        final_results = ranked[:result_limit]

        # Remove internal ranking mechanics before returning tool context.
        clean_results = []
        for item in final_results:
            clean_results.append(
                {
                    "source_type": item.get("source_type"),
                    "source_name": item.get("source_name"),
                    "authority": item.get("authority"),
                    "content": item.get("content"),
                }
            )

        return {
            "query": query,
            "intent": intent,
            "source_priority": (
                "service/catalogue for service facts; policy for policy facts; "
                "FAQ/general knowledge only as supporting context"
            ),
            "results": clean_results,
        }


knowledge_service = KnowledgeService()


def source_type_for_document_type(document_type: str) -> str:
    return UPLOADED_SOURCE_TYPES.get(
        (document_type or "general").strip().lower(),
        "uploaded_general",
    )


def sync_structured_knowledge(db: Session, organization_id):
    services = (
        db.query(Service)
        .filter(Service.organization_id == organization_id)
        .order_by(Service.created_at)
        .all()
    )
    policies = (
        db.query(Policy)
        .filter(Policy.organization_id == organization_id)
        .order_by(Policy.created_at)
        .all()
    )

    knowledge_service.vector_store.delete_by_filter(
        str(organization_id),
        source_types=["structured_service", "structured_policy"],
    )

    for service in services:
        text = (
            f"Service Name: {service.service_name}\n"
            f"Sub-Service Name: {service.sub_service_name or 'None'}\n"
            f"Service Description: {service.service_description}\n"
            f"Service Price: {service.service_price if service.service_price is not None else 'Not specified'}\n"
            f"Service Requirements: {service.service_requirements}"
        )

        knowledge_service.upsert_text(
            organization_id,
            text,
            "structured_service",
            f"service:{service.service_id}",
            section=service.sub_service_name or service.service_name,
        )

    for policy in policies:
        related = (
            policy.related_service.service_name
            if policy.related_service
            else "General"
        )

        text = (
            f"Policy Name: {policy.policy_name}\n"
            f"Policy Description: {policy.policy_description}\n"
            f"Related Service: {related}"
        )

        knowledge_service.upsert_text(
            organization_id,
            text,
            "structured_policy",
            f"policy:{policy.policy_id}",
            section=policy.policy_name,
        )


def _extract_text_from_bytes(data: bytes, filename: str) -> str:
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        document = fitz.open(stream=data, filetype="pdf")
        try:
            return "\n".join(page.get_text() for page in document)
        finally:
            document.close()

    if name.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))

        namespace = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

        return "\n".join(
            "".join(text.text or "" for text in paragraph.findall(".//w:t", namespace))
            for paragraph in root.findall(".//w:p", namespace)
        )

    return data.decode("utf-8", errors="ignore")


async def read_upload_text(file: UploadFile) -> str:
    data = await file.read()
    return _extract_text_from_bytes(data, file.filename or "")


def read_file_text(path: Path) -> str:
    return _extract_text_from_bytes(path.read_bytes(), path.name)


def resolve_knowledge_file_path(saved_path: str, filename: str | None = None) -> Path:
    raw = Path(saved_path)

    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend(
            [
                PROJECT_ROOT / raw,
                BACKEND_ROOT / raw,
            ]
        )

    if filename:
        candidates.extend(
            [
                PROJECT_ROOT / "uploads" / filename,
                BACKEND_ROOT / "uploads" / filename,
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    # Return the canonical root-relative location even if the file is missing,
    # so callers can report a useful path.
    return (PROJECT_ROOT / raw).resolve() if not raw.is_absolute() else raw


def sync_uploaded_knowledge(db: Session, organization_id):
    documents = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.organization_id == organization_id)
        .order_by(KnowledgeDocument.created_at)
        .all()
    )

    knowledge_service.vector_store.delete_by_filter(
        str(organization_id),
        source_types=ALL_UPLOADED_SOURCE_TYPES,
    )

    indexed = 0
    missing_files = []

    for document in documents:
        path = resolve_knowledge_file_path(
            document.file_path,
            filename=document.file_name,
        )

        if not path.exists():
            missing_files.append(document.file_name)
            continue

        text = read_file_text(path)
        if not text.strip():
            continue

        knowledge_service.upsert_text(
            organization_id,
            text,
            source_type_for_document_type(document.document_type),
            document.file_name,
        )
        indexed += 1

    return {
        "indexed_documents": indexed,
        "missing_files": missing_files,
    }


def rebuild_organization_knowledge(db: Session, organization_id):
    sync_structured_knowledge(db, organization_id)
    uploaded = sync_uploaded_knowledge(db, organization_id)

    return {
        "organization_id": str(organization_id),
        **uploaded,
    }


def extract_labeled_fields(text: str, labels: dict[str, list[str]]):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {key: None for key in labels}
    normalized = [(line, line.lower()) for line in lines]

    for key, aliases in labels.items():
        for index, (line, low) in enumerate(normalized):
            for alias in aliases:
                if low.startswith(alias.lower() + ":"):
                    result[key] = (
                        line.split(":", 1)[1].strip()
                        or (lines[index + 1] if index + 1 < len(lines) else None)
                    )
                    break
            if result[key] is not None:
                break

    return result
