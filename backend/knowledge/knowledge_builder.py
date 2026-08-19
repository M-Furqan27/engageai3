from collections import defaultdict

from knowledge.schemas import (
    EmbeddedChunk,
    KnowledgeBase,
    KnowledgeSource,
)


class KnowledgeBuilder:

    def build(
        self,
        organization_id: str,
        embedded_chunks: list[EmbeddedChunk],
    ) -> KnowledgeBase:

        grouped_sources = defaultdict(list)

        for chunk in embedded_chunks:

            key = (
                chunk.source_type,
                chunk.source_name,
            )

            grouped_sources[key].append(chunk)

        sources = []

        for (
            source_type,
            source_name,
        ), chunks in grouped_sources.items():

            sources.append(

                KnowledgeSource(
                    source_type=source_type,
                    source_name=source_name,
                    chunks=chunks,
                )

            )

        return KnowledgeBase(

            organization_id=organization_id,

            sources=sources,

        )