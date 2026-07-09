You are checking a set of retrieved source snippets for **factual
contradictions** — places where two sources make claims that cannot both be true
(different numbers/dates/names for the same thing, opposite statements, etc.).

Sources:
{% for snippet in snippets %}{{ snippet }}
{% endfor %}

Report only genuine contradictions between DIFFERENT sources. Do not flag mere
differences in wording, detail, or scope. If there are none, return an empty list.

Return ONLY JSON of the form:
{"contradictions": ["<one-sentence description citing the source numbers>", ...]}
