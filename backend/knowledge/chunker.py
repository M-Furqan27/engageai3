import re
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from knowledge.schemas import Chunk, ExtractedDocument


class TextChunker:
    """Source-aware chunking that keeps authoritative records intact and
    prevents unrelated FAQ answers from being embedded together.
    """

    STRUCTURED_SOURCE_TYPES = {
        "structured_service",
        "structured_policy",
    }

    def __init__(
        self,
        chunk_size: int = 900,
        chunk_overlap: int = 80,
    ):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    @staticmethod
    def _faq_pairs(text: str) -> list[tuple[str, str]]:
        """Return individual Q/A pairs when a document uses Q:/A: format."""
        pattern = re.compile(
            r"(?ims)^\s*Q(?:uestion)?\s*:\s*(.*?)\s*\n"
            r"\s*A(?:nswer)?\s*:\s*(.*?)"
            r"(?=^\s*Q(?:uestion)?\s*:|\Z)"
        )

        pairs = []
        for match in pattern.finditer(text):
            question = re.sub(r"\s+", " ", match.group(1)).strip()
            answer = match.group(2).strip()

            # Avoid swallowing a trailing FAQ usage/rules section into the
            # final answer when the document contains one.
            answer = re.split(
                r"(?im)^\s*(?:FAQ\s+Usage\s+Rules?|Usage\s+Rules?)\s*$",
                answer,
                maxsplit=1,
            )[0].strip()

            if question and answer:
                pairs.append((question, answer))

        return pairs

    @staticmethod
    def _section_name(text: str, fallback: str | None = None) -> str | None:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if 0 < len(first_line) <= 120:
            return first_line[:120]
        return fallback

    def split(self, documents: List[ExtractedDocument]) -> List[Chunk]:
        chunks: List[Chunk] = []

        for document in documents:
            content = (document.content or "").strip()
            if not content:
                continue

            # One DB service/policy record is already an ideal atomic chunk.
            if document.source_type in self.STRUCTURED_SOURCE_TYPES:
                chunks.append(
                    Chunk(
                        source_type=document.source_type,
                        source_name=document.source_name,
                        section=document.section,
                        chunk_index=1,
                        text=content,
                    )
                )
                continue

            # FAQ documents are chunked one Q/A pair at a time to prevent
            # cross-question leakage and hallucinated combinations.
            faq_pairs = self._faq_pairs(content)
            if faq_pairs:
                for index, (question, answer) in enumerate(faq_pairs, start=1):
                    chunks.append(
                        Chunk(
                            source_type=document.source_type,
                            source_name=document.source_name,
                            section=question,
                            chunk_index=index,
                            text=f"Question: {question}\nAnswer: {answer}",
                        )
                    )
                continue

            document_chunks = self.splitter.split_text(content)

            for index, chunk in enumerate(document_chunks, start=1):
                chunks.append(
                    Chunk(
                        source_type=document.source_type,
                        source_name=document.source_name,
                        section=document.section or self._section_name(chunk),
                        chunk_index=index,
                        text=chunk,
                    )
                )

        return chunks
