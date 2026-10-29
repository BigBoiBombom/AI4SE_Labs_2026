# ADR-001: Use a Modular Monolith Architecture for RecipeCove

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-29 |
| **Deciders** | Bombom (student / product owner), Claude Code (advisor) |
| **Source discussion** | [Task 1 conversation record](../Task_1/Task_1_conversation.md) |
| **Requirements** | [RecipeCove.txt](../Tasks/data/RecipeCove.txt) |

---

## 1. Context

RecipeCove is a web application for discovering recipes, viewing detailed recipe and ingredient information, and keeping a personal favorites list and a recipe calendar. Discovery happens through a **search bar** (by recipe name) and a **chatbot** that suggests recipes for a specific diet.

**Functional scope (14 user stories):**
- **Visitors:** register with a Google account (US1), search recipes by name (US2), view recipe details (US3), view ingredient details (US4), see diet-based suggestions (US5).
- **Registered users:** login/logout (US6–7), profile page (US8), create/delete a calendar (US9–10), add recipe events/reminders to the calendar (US11), add/remove/view favorites (US12–14).

**Assumptions:**
- Small team (2–5 developers), modest initial traffic, with the possibility of fast growth.
- The workload is **read-heavy**: search and recipe views dominate, and writes (favorites, calendar events) are rare.
- Recipe and ingredient data is **imported from an external source** (dataset or API) into our own database, so search is under our control and not rate-limited by a third party.
- The chatbot uses an **external LLM API with tool calling** and may only recommend recipes that exist in our catalog.
- Calendar reminders are delivered by **email** on the event day.

## 2. Decision Drivers

1. **Time to market and development effort** for a small team.
2. **Low and predictable infrastructure cost**, both at launch and under growth.
3. **Data integrity** for user-owned data (calendar ↔ events, favorites).
4. **Testability and simple local development.**
5. **Ability to scale** if the app booms, without a rewrite.
6. **Containing the chatbot/LLM**: it is the slowest, most expensive and least reliable dependency.
7. **Evolvability**: parts can be extracted later if metrics demand it.
8. **Low vendor lock-in.**

## 3. Considered Options

| | Option | Short description |
|---|---|---|
| **A** | **Modular Monolith** | One deployable app split into vertical modules with public APIs; one PostgreSQL database with a schema per module; separate background worker. |
| B | Microservices + API Gateway + Event Bus | Identity, Catalog, Chatbot, User Library and Calendar & Notification services, each with its own DB; broker for events. |
| C | Serverless / Backend-as-a-Service | Static frontend on a CDN; managed auth, managed DB with row-level security, hosted search; serverless functions for chatbot, import and reminders. |

### Comparison (1 = worst, 5 = best for RecipeCove)

| Metric | A | B | C |
|---|---|---|---|
| Initial development effort | 5 | 1 | 4 |
| Time to market | 4 | 1 | 5 |
| Operational burden | 4 | 1 | 5 |
| Infra cost at low traffic | 4 | 1 | 5 |
| Cost predictability at high scale | 4 | 3 | 2 |
| Independent scalability | 2 | 5 | 5 |
| Fault isolation | 2 | 5 | 4 |
| Data consistency / integrity | 5 | 2 | 3 |
| Testability & local development | 5 | 2 | 2 |
| Vendor independence | 5 | 4 | 1 |
| Fit for small team | 5 | 1 | 4 |
| Evolvability | 4 | 5 | 3 |
| **Total** | **49** | **31** | **43** |

## 4. Decision

**We choose Option A – Modular Monolith**, with the following binding rules:

1. **Modules = vertical slices of the domain:** `identity`, `catalog`, `chatbot`, `library` (profile + favorites), `calendar`.
2. **Public API per module.** Each module exposes only a facade + DTOs + events (`api/`); everything else is internal. Other modules may call only `api/`.
3. **Data ownership.** One PostgreSQL schema per module. A module never reads or writes another module's tables. Joins are allowed only within a module.
4. **Cross-module references by ID only (strict modularity).** No foreign keys across schemas (e.g. `library.favorites.recipe_id` is validated through `CatalogFacade.exists()` and cleaned up on the `RecipeRemoved` event). Foreign keys and transactions are used *inside* a module (e.g. `calendar` ↔ `calendar_event`).
   *Rejected alternative:* allowing FKs pointing into the stable `catalog` schema. It is simpler, but it couples other modules to Catalog's tables and blocks a later extraction of Catalog into a service.
5. **Acyclic dependencies:** `chatbot → catalog`, `library → catalog`, `calendar → catalog`. `catalog` and `identity` depend on nothing. Reverse notifications use in-process domain events (`UserDeleted`, `RecipeRemoved`).
6. **Boundaries enforced automatically in CI** (architecture tests such as ArchUnit / Spring Modulith / import-linter / dependency-cruiser, depending on the final stack). A violation fails the build.
7. **Stateless application instances** (sessions in Redis or signed cookies) behind a load balancer, so horizontal scaling is a configuration change.
8. **Background worker as a separate process** of the same codebase, for reminder emails and recipe import jobs.
9. **Chatbot behind a `ChatbotFacade`** with timeouts, streaming responses and per-user rate limits.
10. **Precomputed diet suggestions owned by Catalog.** A worker job periodically (e.g. nightly, and after each recipe import) computes suggestions per diet (vegan, vegetarian, keto, gluten-free, ...) into `catalog.diet_suggestions`, exposed as `CatalogFacade.getDietSuggestions(diet)`.
    - If the LLM is down, slow (timeout) or the user is rate-limited, the chatbot **falls back** to this list, so US5 always works.
    - The list is also the default, cheap way to show "suggested recipes for a diet" without starting a chat, which reduces LLM cost.
    - The fallback only goes through Catalog's public API, so the dependency direction `chatbot → catalog` stays unchanged.
11. **Caching:** CDN for static assets and public recipe/ingredient pages; Redis for popular searches.

### Architecture overview

```
                    ┌───────────── CDN (static assets, public recipe pages) ─────────────┐
Browser ──HTTPS──►  Load balancer ──► App instance 1..N (stateless, same codebase)
                                        ├─ identity  ── Google OAuth 2.0 / OIDC
                                        ├─ catalog   ── search (Postgres full-text),
                                        │               precomputed diet suggestions
                                        ├─ chatbot   ── LLM API (tool: catalog.search)
                                        ├─ library   ── profile, favorites
                                        └─ calendar  ── calendars, events
                                               │
                         PostgreSQL (schemas: identity, catalog, library, calendar)
                         + read replicas         Redis (cache, sessions, job queue)
                                               │
                         Worker process ──► Email provider (reminders)
                                        ├─► Recipe data import (external dataset/API)
                                        └─► Recompute diet suggestions (nightly / after import)
```

### User story → module mapping

| User stories | Module |
|---|---|
| US1, US6, US7 – register / login / logout | identity |
| US2, US3, US4 – search, recipe info, ingredient info | catalog |
| US5 – diet suggestions | catalog (precomputed list) + chatbot (conversational, falls back to catalog) |
| US8 – profile | library (+ identity for account data) |
| US9, US10, US11 – calendar and events | calendar (+ worker for reminders) |
| US12, US13, US14 – favorites | library |

## 5. Consequences

### Positive
- Fastest and cheapest option to build, test, deploy and operate for a small team.
- Single database: transactions and foreign keys inside modules; simple backups and local development.
- Lowest and most predictable infrastructure cost: an estimated **~$1.5k–4k/month at 1M daily active users** (excluding the LLM), compared with ~$4k–10k for B and a linear, potentially much higher bill for C.
- Clear growth path: any module can be extracted into a service (strangler pattern) by replacing its in-process facade with an HTTP/gRPC client and in-process events with a broker.
- No vendor lock-in beyond commodity components (PostgreSQL, Redis, email, LLM API behind an adapter).

### Negative
- Whole app is redeployed for every change; scaling is all-or-nothing (mitigated by stateless instances and the separate worker).
- No cross-module foreign keys: referential integrity between modules is maintained in application code and through events.
- Weaker fault isolation than microservices: a bug or memory leak in one module can affect the whole process.
- Keeping boundaries in place requires discipline and CI tooling. Without it, the system decays into a "big ball of mud".

## 6. When to Revisit This Decision

Re-evaluate (and possibly extract a module into a service) if any of these happens:
- Chatbot load or failures measurably affect the rest of the app (e.g. p95 latency of search > 500 ms during chatbot peaks).
- Search requirements outgrow Postgres full-text (fuzzy search, facets, multi-language) or catalog size > a few million recipes.
- The team grows to multiple independent teams that block each other's deployments.
- Infrastructure cost or scaling limits of the single write database become a measured problem.

## 7. Follow-up Decisions

- **ADR-002:** Chatbot design (LLM provider, tool calling over the catalog, diet taxonomy, cost controls).
- **ADR-003:** Reminder delivery (job queue vs. cron, email provider, time zones, idempotency).
- **ADR-004:** Technology stack (language/framework, architecture-test tooling).
- **ADR-005:** Recipe data source and licensing.

## 8. Revision History

| Version | Date | Change |
|---|---|---|
| v1 | 2026-10-29 | Initial version generated from the Task 1 discussion. |
| v2 | 2026-10-29 | Student confirmed strict ID-only cross-module references (rejected alternative recorded). Added rule 10: precomputed diet suggestions owned by Catalog as the LLM fallback and default for US5; updated diagram, US mapping and risks. |
| v3 | 2026-10-29 | Removed the "Pros and Cons of the Options" section; moved the scored comparison table into section 3 (Considered Options); renumbered sections 6–8. |
| v4 | 2026-10-29 | Removed the "Risks and mitigations" subsection from section 5 (not needed at this stage). |
