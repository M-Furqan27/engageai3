# new


from collections import Counter
from typing import List

import fitz  # PyMuPDF
from fastapi import UploadFile


class PDFReader:

    async def read_sections(self, file: UploadFile) -> List[dict]:
        """
        Splits a PDF into sections using font-size heuristics.
        Lines with a noticeably larger or bold font than the body
        text are treated as section headings; everything after a
        heading belongs to that section until the next one.
        """

        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Determine the body text size (the most common font size)
        sizes = []

        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        sizes.append(round(span["size"]))

        body_size = Counter(sizes).most_common(1)[0][0] if sizes else 0

        sections: List[dict] = []
        current_title = "Introduction"
        current_text = ""

        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):

                    spans = line["spans"]
                    line_text = "".join(span["text"] for span in spans).strip()

                    if not line_text:
                        continue

                    max_size = max(span["size"] for span in spans)
                    is_bold = any("Bold" in span["font"] for span in spans)

                    is_heading = (
                        len(line_text) < 100
                        and (
                            max_size > body_size + 1
                            or (is_bold and max_size >= body_size)
                        )
                    )

                    if is_heading:
                        if current_text.strip():
                            sections.append({
                                "title": current_title,
                                "text": current_text.strip(),
                            })
                        current_title = line_text
                        current_text = ""
                    else:
                        current_text += line_text + "\n"

        if current_text.strip():
            sections.append({
                "title": current_title,
                "text": current_text.strip(),
            })

        return sections