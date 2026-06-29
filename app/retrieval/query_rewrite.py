
from app.core.config import settings
from app.core.exceptions import RetrievalError


async def rewrite_query(question: str) -> str:
    """Optional query expansion / rewriting."""
    if settings.llm_provider == "openai":
        return await _openai_rewrite(question)
    # Fallback: no rewrite
    return question


async def _openai_rewrite(question: str) -> str:
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the user question to improve retrieval. "
                        "Expand acronyms, add synonyms, keep it concise."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        return response.choices[0].message.content or question
    except Exception as exc:
        raise RetrievalError(f"Query rewrite failed: {exc}") from exc
