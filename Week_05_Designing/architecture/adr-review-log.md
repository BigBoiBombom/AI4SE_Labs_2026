# ADR Review Log – RecipeCove

Record of the conversation between the user and the coding assistant while creating and refining the ADR.
Not a 1:1 transcript – a running log of requests, ADR versions, feedback and changes.

- **Date:** 2026-10-29
- **Input:** [RecipeCove_discussion.md](RecipeCove_discussion.md)
- **Output:** [ADR-001-use-modular-monolith-for-recipecove.md](ADR-001-use-modular-monolith-for-recipecove.md)

---

### 1. ADR v1

**User:** Chose option 6 from the discussion menu, "the one with the highest amount of points" (Architecture A – Modular Monolith, 48/60), and asked to write the ADR.

**Assistant:** Created ADR v1. Structure: metadata · 1 Context · 2 Decision Drivers · 3 Considered Options (+ scored comparison, totals re-checked: A 48, B 30, C 41) · 4 Decision (11 binding rules, ASCII diagram, user story → component mapping) · 5 Consequences · 6 When to Revisit · 7 Follow-up Decisions (ADR-002 – ADR-006) · 8 Revision History.

**Decisions taken by the assistant that need confirmation** (open in the discussion; the stricter/safer option was picked):
1. Rule 9 – **server-side sessions with an HttpOnly cookie** instead of JWTs (logout must be immediate, US7).
2. Rule 7 – **PostgreSQL FTS + pg_trgm** for search in v1; dedicated engine only on a revisit trigger.
3. Rule 11 – **hard delete** of all user data on account deletion (not anonymization/soft delete).
4. Rule 10 – reminders by **email**, dispatcher every **5 minutes** (reminder precision ≤ 5 min).
5. Section 6 – the numeric revisit thresholds (3 s TTFT, 10 % zero-result rate, 30 % CTR, 500 req/s, 70 % DB CPU) are initial proposals, not measured values.

---

### 2. Review round 1 – Confirm open decisions → ADR v2

**User:** Chose menu item 1 (confirm or change the five open decisions). Asked via a 4-question dialog; the user confirmed all recommended options: server-side sessions, Postgres FTS in v1, hard delete on account deletion, email reminders with a 5-minute dispatcher, and the revisit thresholds kept as initial proposals.

**Assistant – changes:**
- Section 6: added the note that the thresholds are initial proposals to be calibrated against production metrics.
- Section 8: added revision row v2 recording the confirmations.
- Rules 7, 9, 10, 11 unchanged (confirmed as written).

**Side effects:** none – no information removed. The open-decision list from round 1 is now resolved (5/5 confirmed).

---

### 3. Review round 2 – Accept the ADR → ADR v3

**User:** Chose menu item 6: set the status to Accepted and close the review log.

**Assistant – changes:**
- Metadata: Status `Proposed` → `Accepted`.
- Section 8: added revision row v3.

**Side effects:** none – no content removed. Offered but not taken: risks & mitigations table, pros/cons per option, summary/Mermaid diagram, LLM cost section, shortening.

---

### Final

- **Final version:** v3 (Accepted)
- **Final sections:** metadata · 1 Context · 2 Decision Drivers · 3 Considered Options (+ scored comparison) · 4 Decision (11 binding rules, architecture overview, user story → component mapping) · 5 Consequences · 6 When to Revisit · 7 Follow-up Decisions (ADR-002 – ADR-006) · 8 Revision History

| Metric | Value |
|---|---|
| Review rounds | 2 |
| ADR versions | 3 |
| Sections removed / added | none removed; none added (one note added to section 6) |
| Open decisions confirmed by the user | 5 / 5 |
