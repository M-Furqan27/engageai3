
# new

from typing import List

from google import genai

from knowledge.schemas import (
    Chunk,
    EmbeddedChunk,
)


class EmbeddingService:

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
    ):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        chunks: List[Chunk],
    ) -> List[EmbeddedChunk]:

        embedded_chunks: List[EmbeddedChunk] = []

        for chunk in chunks:

            try:
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=chunk.text,
                )

                embedded_chunks.append(
                    EmbeddedChunk(
                        source_type=chunk.source_type,
                        source_name=chunk.source_name,
                        section=chunk.section,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        embedding=response.embeddings[0].values,
                    )
                )

            except Exception as e:
                print(
                    f"Failed to embed chunk {chunk.chunk_index} "
                    f"from {chunk.source_name}: {e}"
                )
                continue

        return embedded_chunks