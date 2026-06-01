# Sales domain logic (YAML)

Knowledge layer for the **Facts** lane — what to research and how to organise it,
kept separate from prompt/pipeline code so it can evolve on its own.

Loaded once at startup by [`salesbuff/domain/sales_logic.py`](../domain/sales_logic.py).

| File | Role |
|------|------|
| `categories/categories.yaml` | Fact categories: display name, render order, citation rule |
| `question_bank/questions.yaml` | Research questions by entity role x conversation job |
| `ranking/ranking.yaml` | Section order for the Facts tab |
| `compliance/compliance.yaml` | Sector overlays (general / healthcare / pharma) with wording guardrails |

Edit the YAML to change behaviour — no code changes needed.
