# Task 3 – Creating Architecture Skills and Comparing Before/After

Record of the conversation between the student and the coding assistant (Claude Code).

- **Date:** 2026-10-29
- **Inputs:** `Week_05_Designing/Task_1/Task_1_conversation.md`, `Week_05_Designing/Task_2/Task_2_conversation.md`, `Week_05_Designing/Task_2/ADR-001-recipecove-architecture.md`
- **Outputs:** skills in `.claude/skills/`, comparison report (after the new session)

---

## Session 1

### 1. Inspection of the Task 1 and Task 2 records

**Student:** Carefully inspect the recorded discussions from Task 1 and Task 2, then create a new Skill (or set of Skills) for proposing architectures based on requirements, choosing one, and creating an ADR.

**Assistant – baseline metrics (without a skill):**

| Metric | Task 1 (architecture discussion) | Task 2 (ADR) |
|---|---|---|
| Student prompts | 5 (read context · propose 3 · scalability/cost · how to stay modular · "let's go with that option") | 4 (confirm open decisions · remove pros/cons + move table · remove risks · move on) |
| Clarification questions by the assistant | 1 (ambiguous "that option") + 3 upfront questions that the student skipped | 0 |
| Corrections of earlier claims | 1 ("one DB gives FKs" was only true inside a module) | 0 |
| Output versions | – | ADR v1 → v4 (3 review rounds) |
| Not covered in depth | B and C deep dives, chatbot, scheduler, tech stack | – |

**Assistant – observations (what worked / what caused extra rounds):**

| # | Observation | Lesson → built into the skill |
|---|---|---|
| 1 | Upfront clarifying questions (data source, chatbot type, reminders) were ignored; the student just asked for proposals. | State assumptions and continue instead of blocking (architecture-proposal, Step 1). |
| 2 | Diagrams + "why" + "painful parts" + scored table + US mapping worked well; no corrections requested. | Kept as the fixed output format (Steps 2–3). |
| 3 | The first follow-up was "what if it booms? how fast, how expensive?". It was predictable. | Scale & cost section is included proactively (Step 4). |
| 4 | Key insight: the dominant cost (LLM) was architecture-independent; CDN caching was the cheapest lever. | Step 4 asks for the dominant cost driver and the universal lever. |
| 5 | "How do we keep the monolith modular?" required a dedicated answer (rules, enforcement tools, warning signs). | Stored as deep dive #1 in the catalogue (Step 6). |
| 6 | A claim had to be corrected (FK integrity vs. ID-only cross-module references). | Consistency check before every answer + explicit Correction entries (Step 7). |
| 7 | The reply "let's go with that option" was ambiguous and needed a clarification question. | Numbered menu at the end of every answer; AskUserQuestion when ambiguous (Step 6). |
| 8 | The assistant had to decide two open topics while writing ADR v1, and flagged them; the student confirmed both. Worked well. | adr-writer: pick the stricter option, flag it, ask for confirmation. |
| 9 | ADR v1 was too heavy: the student removed "Pros and Cons of the Options" and "Risks and mitigations", and moved the comparison table into "Considered Options". | adr-writer uses the **final v4 structure** as the default template; heavier sections are only offered. |
| 10 | Removing sections silently lost information (rejection reasons, LLM cost, reminder details); the assistant pointed this out. | adr-writer reports side effects after every change and suggests follow-up ADRs. |
| 11 | The record files created before each task were useful for this inspection. | Both skills create their record file first and include a session-metrics table, so before/after comparison is easy. |

### 2. Skills created

**Assistant:** Created a set of 2 skills (one per task phase) in the project's `.claude/skills/` folder, so Claude Code discovers them automatically:

```
.claude/skills/
├── architecture-proposal/            (Task 1 phase)
│   ├── SKILL.md                      workflow: record → requirements + assumptions → 3 fundamentally
│   │                                 different architectures → comparison + US mapping → scale & cost
│   │                                 → recommendation → deep-dive menu → consistency check → outcome
│   └── templates/discussion-record.md
└── adr-writer/                       (Task 2 phase)
    ├── SKILL.md                      workflow: review log → gather inputs → lean ADR v1 → review loop
    │                                 (minimal change, revision history, side effects) → close
    └── templates/
        ├── adr-template.md           = final structure of ADR-001 v4, with placeholders
        └── adr-review-log.md
```

Why two skills instead of one: each phase has its own trigger ("propose architectures" vs. "write/revise an ADR"), and an ADR can be requested for a decision made outside this workflow.

**Next step (student):** Start a **new session** and redo Task 1 and Task 2 with the skills, saving the outputs in a separate folder (e.g. `Week_05_Designing/Task_3/with_skill/`). Then ask the assistant to compare the recordings and write the report.

---

### 3. New session with the skills → comparison report

**Student:** Ran a new session and finished both tasks in 4 prompts:
1. *"Read the RecipeCove.txt in Week_05_Designing\Tasks\data\RecipeCove.txt. Suggest an architecture for this software."*
2. *"Lets choose the one with highest amount of points"*
3. Menu item 1: confirm the open decisions.
4. Menu item 6: accept the ADR.

Outputs are in `Week_05_Designing/architecture/`: the discussion record, the ADR review log and ADR-001 v3 (Accepted). Asked the assistant to do the Task 3 comparison.

**Assistant:** Compared the new outputs with the baseline and wrote `Task_3/Task_3_report.md`. Key findings:
- **4 prompts instead of 9.** No clarification, no correction, and no content changes to the ADR: 2 review rounds with confirmations only, against 3 editing rounds before.
- The same 3 architectures, the same ranking A > C > B and the same choice A (48/30/41 vs 49/31/43).
- Better: stated assumptions, more concrete technical risks, ADR v1 already in the final structure, more checkable rules, measurable revisit thresholds, built-in metrics tables.
- Trade-offs: 5 decisions proposed by the assistant and simply confirmed; no modularity deep dive; small inconsistencies between the discussion record and the ADR; different boom scenarios and no timestamps.
- Suggested 4 skill improvements in the report.

---
