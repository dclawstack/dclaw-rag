import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

from app.generation.llm_gateway import LLMGateway
from app.generation.synthesis import (
    build_citations,
    parse_answer,
    render_rag_prompt,
    to_retrieved_chunk,
)
from app.models.schemas import AgentStep, Citation, RetrievedChunk
from app.retrieval.search import Searcher

PLAN_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_plan_v1.md"

NO_ANSWER = "I don't have enough information to answer that."


@dataclass
class AgentResult:
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    confidence: str
    steps: list[AgentStep]


class AgenticRAG:
    """Plan-and-execute RAG: decompose the question, retrieve per sub-question,
    then synthesize one cited answer over the merged evidence."""

    def __init__(self, searcher: Searcher, llm: LLMGateway) -> None:
        self.searcher = searcher
        self.llm = llm

    async def run(
        self,
        question: str,
        top_k: int = 5,
        filters: dict | None = None,
        max_steps: int = 4,
    ) -> AgentResult:
        sub_questions = await self._plan(question, max_steps)

        steps: list[AgentStep] = []
        collected: dict[str, object] = {}
        for sub_question in sub_questions:
            hits = self.searcher.search(sub_question, top_k=top_k, filters=filters)
            for chunk in hits:
                collected.setdefault(str(chunk.id), chunk)
            steps.append(AgentStep(sub_question=sub_question, n_results=len(hits)))

        chunks = list(collected.values())
        if not chunks:
            return AgentResult(
                answer=NO_ANSWER,
                citations=[],
                retrieved_chunks=[],
                confidence="low",
                steps=steps,
            )

        prompt = render_rag_prompt(chunks, question)
        messages = [
            {"role": "system", "content": "You are a helpful RAG assistant."},
            {"role": "user", "content": prompt},
        ]
        raw = await self.llm.complete(messages, temperature=0.2)
        answer, citation_indices, confidence = parse_answer(raw)

        return AgentResult(
            answer=answer,
            citations=build_citations(citation_indices, chunks),
            retrieved_chunks=[to_retrieved_chunk(c) for c in chunks],
            confidence=confidence,
            steps=steps,
        )

    async def _plan(self, question: str, max_steps: int) -> list[str]:
        template = Template(PLAN_PROMPT_PATH.read_text(encoding="utf-8"))
        prompt = template.render(question=question, max_steps=max_steps)
        messages = [
            {"role": "system", "content": "You decompose questions into search queries."},
            {"role": "user", "content": prompt},
        ]
        raw = await self.llm.complete(messages, temperature=0.0)
        sub_questions = self._parse_plan(raw)
        return sub_questions[:max_steps] or [question]

    @staticmethod
    def _parse_plan(raw: str) -> list[str]:
        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw.strip())
            if isinstance(data, dict):
                data = data.get("queries", [])
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except Exception:
            pass
        return []
