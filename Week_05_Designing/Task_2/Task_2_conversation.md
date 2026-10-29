# Task 2 – Architecture Decision Record (ADR) for RecipeCove

Record of the conversation between the student and the coding assistant (Claude Code).
Not a 1:1 transcript – a running log of requests, ADR versions, feedback and changes.

- **Date:** 2026-10-29
- **Project:** RecipeCove (`Week_05_Designing/Tasks/data/RecipeCove.txt`)
- **Input:** Task 1 discussion (`Week_05_Designing/Task_1/Task_1_conversation.md`)
- **Output:** `Week_05_Designing/Task_2/ADR-001-recipecove-architecture.md`

---

## Session 1

### 1. Start of Task 2 – ADR v1

**Student:** Choose Architecture A (Modular Monolith) and move on to Task 2.

**Assistant:** Created this record file and the first version of the ADR (`ADR-001-recipecove-architecture.md`, **v1**).

**v1 structure** (based on the MADR / Nygard ADR templates):
1. Metadata table (status, date, deciders, links to the Task 1 record and requirements)
2. Context: system summary, the 14 user stories, assumptions
3. Decision drivers (8, ordered by importance)
4. Considered options (A, B, C, one line each)
5. Decision: Modular Monolith + 10 binding rules (modules, public API, schema ownership, IDs-only cross-module references, acyclic dependencies, CI enforcement, stateless instances, worker, chatbot facade + fallback, caching), ASCII architecture diagram, user story → module table
6. Consequences: positive, negative, risks and mitigations table
7. Pros/cons of every option + scored comparison table (with totals)
8. When to revisit (measurable triggers)
9. Follow-up ADRs (chatbot, reminders, tech stack, data source)

**Decisions taken by the assistant while writing (open in Task 1, to be confirmed by the student):**
- Cross-module references: **IDs only, no cross-schema FKs** (the stricter of the two options discussed).
- US5 must work without the LLM: **precomputed diet suggestion list as fallback**.

**Waiting for student review:** Is it informative enough? Missing / extra content? Structure OK? Need a different overview table or a visual diagram?

---

### 2. Review round 1 – confirming the open decisions → ADR v2

**Student:** Modules should store recipe IDs only, keeping the app strictly modular. If the chatbot is down, we should fall back to a precomputed list in Catalog, as suggested.

**Assistant – changes in v2:**
- Rule 4 (ID-only references) marked as **strict modularity** and confirmed. Added the **rejected alternative** (FKs into the stable `catalog` schema) and why it was rejected: it couples modules to Catalog's tables and blocks a later extraction of Catalog.
- New **rule 10**: precomputed diet suggestions are **owned by the Catalog module** (`catalog.diet_suggestions`, exposed via `CatalogFacade.getDietSuggestions(diet)`), recomputed by the worker nightly and after each import.
  - Used as the **fallback** when the LLM is down, times out, or the user is rate-limited.
  - Also the **default, cheap** way to serve US5 without a chat, which lowers LLM cost.
  - Keeps the dependency direction `chatbot → catalog`, so no new coupling.
- Updated the diagram (Catalog + worker job), the US5 row in the mapping table, and the risks table (new risk: stale suggestions).
- Added a **Revision History** section to the ADR.

**Waiting for further student review.**

---

### 3. Review round 2 – restructure options → ADR v3

**Student:** Remove section 6 "Pros and Cons of the Options", keep only the Comparison table, and move it into section 3 "Considered Options".

**Assistant – changes in v3:**
- Deleted the per-option pros/cons bullet lists (A, B, C).
- Moved the scored **Comparison table** (12 metrics + totals A 49 / B 31 / C 43) directly under the options table in **section 3**.
- Renumbered: 6 "When to Revisit", 7 "Follow-up Decisions", 8 "Revision History"; added a v3 row.
- Side effect noted to the student: the written reasons why B and C were rejected (e.g. "overkill for 14 user stories", per-request search cost) are no longer in the ADR; only the scores remain.

**Waiting for further student review.**

---

### 4. Review round 3 – remove risks → ADR v4

**Student:** Remove "Risks and mitigations", it is not needed currently.

**Assistant – changes in v4:**
- Deleted the "Risks and mitigations" table from section 5 (Consequences). Section 5 now has only Positive and Negative consequences.
- Added a v4 row to the Revision History.
- Note: the main risk-related facts still appear elsewhere (LLM fallback in rule 10, boundary enforcement in rule 6, revisit triggers in section 6). The LLM cost estimate and the reminder idempotency/time-zone notes are no longer in the ADR. They are candidates for the follow-up ADR-002 (chatbot) and ADR-003 (reminders).

**Waiting for further student review.**

---

### 5. End of Task 2

**Student:** Move on to Task 3.

**Outcome of Task 2:** Final ADR = **v4** (`ADR-001-recipecove-architecture.md`).
Final structure: metadata · 1 Context · 2 Decision Drivers · 3 Considered Options (+ scored comparison table) · 4 Decision (11 binding rules, ASCII diagram, user story → module mapping) · 5 Consequences (positive / negative) · 6 When to Revisit · 7 Follow-up Decisions · 8 Revision History.

*End of Task 2 record. The discussion continues in `Week_05_Designing/Task_3/Task_3_conversation.md`.*
