import os
import uuid

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from knowledge.schemas import KnowledgeBase


class VectorStore:
    def __init__(self):
        self.client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
        )

    def upsert(self, knowledge_base: KnowledgeBase):
        documents = []

        for source in knowledge_base.sources:
            for chunk in source.chunks:
                documents.append(
                    {
                        "id": str(uuid.uuid4()),
                        "organization_id": str(knowledge_base.organization_id),
                        "content": chunk.text,
                        "content_vector": chunk.embedding,
                        "source_type": chunk.source_type,
                        "source_name": source.source_name,
                    }
                )

        if documents:
            self.client.upload_documents(documents)

    @staticmethod
    def _as_dict(result):
        return {
            "content": result.get("content", ""),
            "source_name": result.get("source_name", ""),
            "source_type": result.get("source_type", ""),
            "search_score": float(result.get("@search.score", 0.0) or 0.0),
        }

    def search(
        self,
        organization_id: str,
        query: str,
        query_embedding: list,
        top_k: int = 12,
    ):
        """Hybrid text + vector retrieval for better exact-name and semantic recall."""
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        results = self.client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=f"organization_id eq '{organization_id}'",
            select=["content", "source_name", "source_type"],
            top=top_k,
        )

        return [self._as_dict(result) for result in results]

    def list_by_source_types(
        self,
        organization_id: str,
        source_types: list[str],
        top: int = 100,
    ):
        if not source_types:
            return []

        type_filter = " or ".join(
            f"source_type eq '{source_type}'"
            for source_type in source_types
        )

        results = self.client.search(
            search_text="*",
            filter=(
                f"organization_id eq '{organization_id}' and "
                f"({type_filter})"
            ),
            select=["content", "source_name", "source_type"],
            top=top,
        )

        return [self._as_dict(result) for result in results]

    def delete_by_filter(
        self,
        organization_id: str,
        source_types=None,
        source_name=None,
    ):
        clauses = [f"organization_id eq '{organization_id}'"]

        if source_types:
            clauses.append(
                "(" + " or ".join(
                    f"source_type eq '{source_type}'"
                    for source_type in source_types
                ) + ")"
            )

        if source_name:
            safe = source_name.replace("'", "''")
            clauses.append(f"source_name eq '{safe}'")

        results = self.client.search(
            search_text="*",
            filter=" and ".join(clauses),
            select=["id"],
            top=1000,
        )

        documents = [{"id": result["id"]} for result in results]

        if documents:
            self.client.delete_documents(documents=documents)
