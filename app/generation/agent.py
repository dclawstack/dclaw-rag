import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

from app.core.config import settings
from app.generation.llm_gateway import LLMGateway
from app.generation.synthesis import (
    build_citations,
    parse_answer,
    render_rag_prompt,
    to_retrieved_chunk,
    verify_answer,
)
from app.models.schemas import AgentStep, Citation, DocumentChunk, RetrievedChunk
from app.retrieval.search import Searcher

PLAN_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_plan_v1.md"
REFLECT_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_reflect_v1.md"

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
        # Decompose, then iteratively retrieve → reflect → re-search until the
        # question is covered or the step budget (total searches) is spent.
        queue: list[str] = list(await self._plan(question, max_steps))
        steps: list[AgentStep] = []
        collected: dict[str, DocumentChunk] = {}
        searched: list[str] = []

        while queue and len(searched) < max_steps:
            sub_question = queue.pop(0)
            if sub_question in searched:
                continue
            hits = self.searcher.search(sub_question, top_k=top_k, filters=filters)
            searched.append(sub_question)
            for chunk in hits:
                collected.setdefault(str(chunk.id), chunk)
            steps.append(AgentStep(sub_question=sub_question, n_results=len(hits)))

            # Reflect once the planned queries are exhausted: given the evidence
            # so far, what's still missing? Add follow-ups within the budget.
            remaining = max_steps - len(searched)
            if (
                settings.agentic_reflection
                and not queue
                and remaining > 0
                and collected
            ):
                follow_ups = await self._reflect(
                    question, searched, list(collected.values()), remaining
                )
                queue.extend(q for q in follow_ups if q not in searched)

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

        # Abstain-aware: fact-check against the evidence and downgrade confidence
        # when the answer isn't grounded (reuses the /query verifier).
        if settings.verify_answers:
            faithfulness, _ = await verify_answer(answer, chunks, self.llm)
            if faithfulness == "unsupported":
                confidence = "low"

        return AgentResult(
            answer=answer,
            citations=build_citations(citation_indices, chunks),
            retrieved_chunks=[to_retrieved_chunk(c) for c in chunks],
            confidence=confidence,
            steps=steps,
        )

    async def _reflect(
        self,
        question: str,
        searched: list[str],
        evidence: list[DocumentChunk],
        max_new: int,
    ) -> list[str]:
        """Given evidence so far, propose follow-up queries (or [] if enough)."""
        snippets = [c.text[:200] for c in evidence[:8]]
        template = Template(REFLECT_PROMPT_PATH.read_text(encoding="utf-8"))
        prompt = template.render(
            question=question, searched=searched, evidence=snippets, max_new=max_new
        )
        messages = [
            {"role": "system", "content": "You decide what else to search for."},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = await self.llm.complete(messages, temperature=0.0)
        except Exception:
            return []  # reflection is best-effort; never break the answer
        return self._parse_plan(raw)[:max_new]

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
