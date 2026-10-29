---
name: adr-writer
description: Write and iteratively refine an Architecture Decision Record (ADR) from a finished architecture discussion, using a lean MADR-style template with binding decision rules, a scored options comparison, a diagram and a revision history, while flagging decisions that still need confirmation and logging every review round. Use when the user has chosen an architecture and asks for an ADR, or asks to revise or restructure an existing ADR.
---

# ADR Writer

Turn a finished architecture discussion (usually produced with the `architecture-proposal` skill) into an ADR, then refine it with the user until they are satisfied.

## Step 0 – Create the review log FIRST

Before writing the ADR, create a review log next to it (e.g. `<project_dir>/architecture/adr-review-log.md`, or where the user says) from [templates/adr-review-log.md](templates/adr-review-log.md). Append one entry per review round: the user's request (paraphrased), the changes made, and any side effects. Tell the user the path.

## Step 1 – Gather inputs

Read the discussion record and the requirements. Extract:
- the chosen option and its rules; rejected options with their reasons;
- the scored comparison table (copy it exactly) and the user-story mapping;
- numbers (cost and scale estimates) and assumptions;
- **topics left open** in the discussion.

## Step 2 – Write ADR v1 from the lean template

Use [templates/adr-template.md](templates/adr-template.md). File name: `ADR-<NNN>-<kebab-title>.md`.

Default sections (lean by design, because users tend to remove heavier sections):
metadata table · 1 Context (scope, user stories, assumptions) · 2 Decision Drivers · 3 Considered Options (short table **+ scored comparison table with totals**) · 4 Decision (numbered **binding rules**, ASCII diagram, user story → component mapping) · 5 Consequences (Positive / Negative) · 6 When to Revisit (measurable triggers) · 7 Follow-up Decisions · 8 Revision History.

**Do not include by default; offer them in the menu instead:** pros/cons per option, a risks & mitigations table, a "why not chosen" column, a Mermaid diagram, a one-paragraph summary at the top, cost estimates for the AI/LLM part.

Writing rules:
- Each binding rule must be **checkable** (someone can verify that the code follows it). For contested rules, add the **rejected alternative** inline with a one-line reason.
- If a topic was left **open** in the discussion and you had to decide it, pick the stricter/safer option, mark it in the review log, and **ask the user to confirm it** in your answer.
- Keep facts consistent with the discussion. Label estimates as estimates. Re-add the comparison totals to check them.
- Topics that are too detailed for this ADR go to **Follow-up Decisions** (ADR-002, ...), not into the main body.

## Step 3 – Review loop

For each user request:
1. Make the **smallest change** that does what was asked; renumber sections if needed.
2. Add a row to **Revision History** (`vN | date | change`).
3. Log the round in the review log.
4. Tell the user the **side effects**: which information is now gone, where it still lives (another rule, section, or the discussion record), and where it could go (e.g. a follow-up ADR). Do not re-add removed content unless asked.
5. End with a short, numbered menu of possible next changes.

## Step 4 – Close

When the user is satisfied or moves on, append the final entry to the review log: final version number, final section list, and session metrics (number of review rounds, number of ADR versions, sections added/removed).
