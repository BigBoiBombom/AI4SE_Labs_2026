# Task 3 Report – Architecture Work With and Without Skills

- **Project:** RecipeCove (`Tasks/data/RecipeCove.txt`)
- **Skills under test:** `.claude/skills/architecture-proposal` (Task 1 phase), `.claude/skills/adr-writer` (Task 2 phase)
- **Without skills (baseline):** `Task_1/Task_1_conversation.md`, `Task_2/Task_2_conversation.md`, `Task_2/ADR-001-recipecove-architecture.md`
- **With skills (new session):** `architecture/RecipeCove_discussion.md`, `architecture/adr-review-log.md`, `architecture/ADR-001-use-modular-monolith-for-recipecove.md`

## 1. Setup

| | Without skills | With skills |
|---|---|---|
| Student prompts | 5 in Task 1, 4 in Task 2 | 4 in total:<br>1. *"Read the RecipeCove.txt … Suggest an architecture for this software."*<br>2. *"Lets choose the one with highest amount of points"*<br>3. Menu item 1: confirm the open decisions (answered in a 4-question dialog)<br>4. Menu item 6: accept the ADR |
| Prompt style | Free text, steered step by step (scalability, modularity, which ADR sections to remove) | A short request, then picks from numbered menus |

## 2. Metrics

| Metric | Without skills | With skills |
|---|---|---|
| **Task 1 – architecture discussion** | | |
| Prompts until a decision | 5 | **2** |
| Clarification questions by the assistant | 1 + 3 upfront questions the student skipped | **0** (6 assumptions stated instead) |
| Corrections of earlier claims | 1 (foreign-key integrity across modules) | **0** |
| Scale & cost covered | Only after a follow-up question | Included in the first answer |
| Architectures / ranking / choice | Monolith, Microservices, Serverless · A > C > B · **A** | Same 3 · A > C > B · **A** |
| Scored totals | 49 / 31 / 43 | 48 / 30 / 41 (sums shown) |
| **Task 2 – ADR** | | |
| Prompts after choosing until Accepted | 4 | **2** |
| Review rounds | 3 (v1 → v4) | **2** (v1 → v3) |
| Content changes requested by the student | 3: remove pros/cons, move the comparison table, remove risks | **0**: only confirmations and acceptance |
| Open decisions flagged and confirmed | 2 / 2 | 5 / 5 (all recommended options accepted) |
| Final status | Accepted | Accepted |
| Final ADR size | 153 lines, 11 rules | 189 lines, 11 rules |
| **Overall** | | |
| Student prompts for both tasks | **9** | **4** |

## 3. Findings

**Faster and smoother.** Both tasks were finished in 4 prompts instead of 9. Every round that was spent fixing something in the baseline disappeared:
- the scalability question came up as a follow-up before, and is now answered in the first response;
- the ambiguous "that option" reply is now a pick from a numbered menu;
- the foreign-key claim no longer needed a correction;
- the 2 ADR sections are no longer removed, because ADR v1 already had the final structure from the baseline.

The ADR review rounds were only confirmations, not edits.

**Same decision.** The same three architectures, the same ranking and the same choice came out, with nearly identical scores. The skills changed the process, not the conclusion.

**Better quality:**
- **Discussion:**
  - stated assumptions instead of asking questions;
  - more concrete technical risks: duplicate or mistimed reminders around daylight-saving changes, keeping a search index in sync, favorites pointing to recipes that were removed, recipe data licensing;
  - says when B or C would win;
  - a growth path for later.
- **ADR:**
  - v1 already contained what the student had to confirm in the baseline's first round: recipe IDs only, and the precomputed diet suggestions when the chatbot is down.
  - Rules are more specific and checkable: database role per schema, cookie flags, an integration test that no user data is left after account deletion.
  - "When to Revisit" uses measurable thresholds.
  - Every record ends with a metrics table, which made this comparison easy.

**Weaker / trade-offs:**
- **Less active involvement from the student.** The assistant made 5 decisions on its own (sessions vs tokens, search engine, hard delete, reminder channel, revisit thresholds). The student accepted all of them as recommended. This is quick, but they are confirmed decisions, not discussed ones.
- **No deep dive.** The baseline's "how to keep the monolith modular" discussion produced the reasoning behind the modularity rules. In the new run those rules appear without discussion.
- **Small inconsistencies:**
  - The recommendation claims "true consistency for recipe references", but the ADR lists the loss of cross-module referential integrity as a negative.
  - The Outcome's "open topics" still lists sessions vs JWT and the search engine, which the ADR has since decided.
- **Limits of this comparison:**
  - the boom scenarios differ (100k vs 1M daily users), so the cost figures can't be compared;
  - there are no timestamps, so time can't be compared;
  - there was a single run on a project the skills were built from.

## 4. Conclusion

The skills cut the work from **9 prompts to 4** and produced an accepted ADR with no content rework, reaching the same architecture decision. The trade-off is that the student is less involved: more decisions are proposed by the assistant and simply confirmed, and less of the reasoning is discussed.

## 5. Suggested skill improvements

1. **architecture-proposal:** Add a timestamp to each record entry, and write the numbered menu into the record.
2. **architecture-proposal:** Use fixed scale scenarios (launch, 10×, 100×) so runs can be compared.
3. **adr-writer:** Before writing v1, ask about high-impact open decisions (security, data deletion) with AskUserQuestion instead of deciding them first.
4. **adr-writer:** When the ADR is accepted, update the discussion record's open topics and check that the ADR does not contradict it.
