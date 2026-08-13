import os

from dotenv import load_dotenv
from langchain_tavily import TavilySearch


load_dotenv()


def search_web(
    queries: list[str],
    max_results: int = 5
):
    """
    Search the web using Tavily.
    """

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not configured. "
            "Add it to the .env file."
        )

    search_tool = TavilySearch(
        max_results=max_results,
        tavily_api_key=api_key
    )

    evidence = []

    for query in queries:

        try:
            results = search_tool.invoke(
                {
                    "query": query
                }
            )

            if isinstance(results, list):
                evidence.extend(results)

            elif isinstance(results, dict):
                evidence.append(results)

        except Exception as e:
            print(f"Tavily search error for '{query}': {e}")

    return evidence