import httpx

from bs4 import BeautifulSoup


class WebScraper:

    async def scrape(self, url: str) -> str:

        async with httpx.AsyncClient(timeout=15) as client:

            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                follow_redirects=True,
            )

            response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        return soup.get_text(separator="\n", strip=True)