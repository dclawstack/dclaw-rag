You are directing an iterative research agent for a RAG system. You have gathered
evidence for the user's question. Decide whether it is sufficient to answer, and if
not, propose focused follow-up search queries that would close the remaining gaps.

Original question: {{ question }}

Queries already searched:
{% for q in searched %}- {{ q }}
{% endfor %}

Evidence gathered so far (snippets):
{% for snippet in evidence %}[{{ loop.index }}] {{ snippet }}
{% endfor %}

Rules:
- If the evidence is enough to answer the original question, return an empty list.
- Otherwise return at most {{ max_new }} NEW queries targeting only what is still
  missing. Do not repeat queries already searched. Prefer concrete, specific terms.

Return ONLY a JSON array of strings, e.g. ["follow-up query"] or [].
