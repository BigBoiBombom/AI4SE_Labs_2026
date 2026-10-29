---
name: architecture-proposal
description: Analyze software requirements (system description, user stories) and propose 3 fundamentally different candidate architectures with ASCII diagrams, rationale, painful implementation parts, a scored comparison, user-story mapping, scale/cost estimates and a recommendation, while keeping a running conversation record. Use when the user asks to propose, compare or discuss architectures for a system based on its requirements, or wants an architecture discussion before writing an ADR.
---

# Architecture Proposal

Lead an architecture discussion from requirements to a chosen architecture. The output is (1) a running **discussion record** file and (2) a clear decision that the `adr-writer` skill can turn into an ADR.

## Step 0 – Create the discussion record FIRST

Before analyzing anything, create the record file and tell the user its path.
- Location: where the user says. Otherwise, a folder next to the requirements, e.g. `<project_dir>/architecture/discussion.md`.
- Use the template in [templates/discussion-record.md](templates/discussion-record.md).
- **Append to it after every exchange.** It is not a 1:1 transcript. Each entry holds: the user's request (paraphrased), the key content of your answer (diagrams, tables, numbers), and any decisions.
- If you contradict something you said earlier, add an explicit **"Correction"** note instead of silently changing it.

## Step 1 – Understand the requirements

Read all requirement files and summarize in the record:
- actors and their user stories, grouped by capability;
- external integrations (identity providers, 3rd-party data, AI/LLM, email/push, payments);
- implicit non-functional concerns (read/write ratio, latency-sensitive parts, slow or expensive external calls, scheduled jobs, privacy/GDPR).

**State assumptions instead of blocking on questions.** List the assumptions that drive the architecture (team size, traffic, read/write ratio, data source, how AI features work, how notifications are delivered), say they can be challenged, and continue. Only ask first if the requirements are truly unusable.

## Step 2 – Propose exactly 3 architectures that differ fundamentally

The three must differ in **deployment unit, data ownership, or who operates the infrastructure**. Not 3 variants of the same idea.
- Default trio for small-to-medium web apps: **Modular Monolith**, **Microservices + API Gateway + Event Bus**, **Serverless / Backend-as-a-Service**.
- Swap one in when the requirements call for it: event-driven / streaming (real-time feeds, IoT, high-volume events), CQRS + event sourcing (audit-heavy domains), hexagonal/clean (complex domain logic, many integrations), space-based (extreme spikes, e.g. ticket sales), offline-first/edge (mobile, poor connectivity).

For **each** architecture, give:
1. **ASCII diagram**: clients, components/modules/services, data stores, external systems, async paths (queues, schedulers, events).
2. **What it is**: 1–2 sentences.
3. **Why it fits**: tied to *specific* requirements or user stories, not generic praise.
4. **Painful parts**: concrete low-level pain, e.g. references across data boundaries, eventual consistency, slow external calls blocking workers, idempotent schedulers and time zones, user-deletion propagation, local development, cold starts and timeouts, testing security rules, vendor lock-in, keeping a search index in sync.

## Step 3 – Compare

1. **Scored comparison table** (1 = worst, 5 = best *for this system*) with this default metric set: initial development effort, time to market, operational burden, infra cost at low traffic, cost predictability at high scale, independent scalability, fault isolation, data consistency/integrity, testability & local development, vendor independence, fit for team size, evolvability. Add a **Total** row and **re-add the numbers to check them** before sending.
2. **User story → component mapping** table: one column per architecture.

## Step 4 – Scale and cost (include proactively)

Users almost always ask "what if it booms?", so answer it up front with a back-of-envelope scenario:
- Workload: daily active users → requests/s (average and ~5× peak), writes/s, calls to expensive external services (e.g. LLM tokens/day).
- Name the **dominant cost driver**, especially when it is architecture-independent (e.g. LLM cost), and its mitigations.
- Name the **cheapest universal lever** (usually CDN/cache for read-heavy data).
- Per architecture, give a table of: how it scales, time to add capacity, prerequisites, first bottleneck, monthly infra cost ballpark, cost-curve shape (step-wise vs linear per request).
- Label all prices as **list-price ballparks to be verified**.

## Step 5 – Recommend

Give one recommendation with the conditions under which another option wins, plus the growth path (e.g. strangler pattern: extract the most volatile modules first, only when metrics show the need).

## Step 6 – Deep dives on request

End every answer with a **numbered menu** of next steps so the user can reply with a number. If the reply is still ambiguous ("let's go with that option"), ask with AskUserQuestion and list the menu items; never guess. Deep-dive catalogue:
1. **Keeping a modular monolith modular**: the 4 rules (vertical slices, public API per module, schema per module with no cross-module joins, acyclic dependencies with domain events for reverse direction), folder structure, an enforcement table (build units, visibility, architecture tests in CI such as ArchUnit / Spring Modulith / import-linter / dependency-cruiser, DB schemas/roles, CODEOWNERS), and warning signs of decay.
2. Data model and ownership: which component owns which entity, and how references across boundaries work.
3. The hardest component, e.g. the AI/chatbot (tool calling over own data, fallback, cost control) or the scheduler (idempotency, time zones, retries).
4. Security and privacy (auth flow, GDPR deletion).
5. The same depth for a non-recommended option.

## Step 7 – Consistency check before every answer

Re-read your previous claims. If a new rule weakens an earlier benefit (e.g. "one DB gives FKs" vs. "no FKs across modules"), say so explicitly in the answer and add a Correction entry to the record.

## Step 8 – Close

When the user chooses, append an **Outcome** entry: chosen architecture with its key rules, rejected options with one-line reasons, open topics (candidates for follow-up ADRs), and the session metrics from the template. Then suggest continuing with the `adr-writer` skill.

## Chat style

The chat answer is a condensed version of the record entry: recommendation first, then diagrams and tables. Full details go in the record. Link the record file in every answer.
