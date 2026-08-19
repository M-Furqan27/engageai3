 
    
# new
    
from typing import List

from fastapi import UploadFile

from knowledge.schemas import ExtractedDocument
from knowledge.pdf_reader import PDFReader
from knowledge.web_scraper import WebScraper


class Extractor:

    def __init__(self):
        self.pdf_reader = PDFReader()
        self.web_scraper = WebScraper()

    async def extract(
        self,
        text: str | None,
        urls: List[str],
        pdfs: List[UploadFile],
    ) -> List[ExtractedDocument]:

        documents: List[ExtractedDocument] = []

        # Process Text
        if text and text.strip():
            documents.append(
                ExtractedDocument(
                    source_type="text",
                    source_name="Text Input",
                    content=text.strip()
                )
            )

        # Process PDFs — section-wise
        for pdf in pdfs:

            sections = await self.pdf_reader.read_sections(pdf)

            for section in sections:

                documents.append(
                    ExtractedDocument(
                        source_type="pdf",
                        source_name=pdf.filename or "Unnamed PDF",
                        section=section["title"],
                        content=section["text"],
                    )
                )

        # Process URLs
        for url in urls:

            website_text = await self.web_scraper.scrape(url)

            documents.append(
                ExtractedDocument(
                    source_type="url",
                    source_name=url,
                    content=website_text
                )
            )

        return documents
    
    
    