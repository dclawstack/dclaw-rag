You are a strict fact-checker. Decide whether every claim in ANSWER is directly
supported by the CONTEXT below. Do not use outside knowledge — judge only against
the context.

Context:
{% for chunk in context %}
[{{ loop.index }}] {{ chunk.text }}
{% endfor %}

Answer: {{ answer }}

Return ONLY valid JSON of this shape:
{
  "faithfulness": "grounded | partial | unsupported",
  "unsupported_claims": ["verbatim each claim from the answer that the context does NOT support"]
}

Rules:
- A claim is SUPPORTED if its facts, numbers, or names appear in the context or follow
  directly from it — even if the wording differs. A figure quoted from the context (e.g. a
  revenue number that appears in a chunk) is supported. Judge meaning, not exact wording.
- Only list a claim as unsupported if the context does NOT contain it or contradicts it.
- "grounded": every claim in the answer is supported by the context.
- "partial": at least one claim is supported and at least one is genuinely absent.
- "unsupported": the answer is not supported by the context (or contradicts it).
- If faithfulness is "grounded", "unsupported_claims" must be an empty list.
