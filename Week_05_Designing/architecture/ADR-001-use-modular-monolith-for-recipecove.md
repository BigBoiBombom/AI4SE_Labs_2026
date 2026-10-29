# ADR-001: Use a Modular Monolith Architecture for RecipeCove

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-29 |
| **Deciders** | RecipeCove development team (Bombom), with Claude Code as architecture assistant |
| **Source discussion** | [discussion record](RecipeCove_discussion.md) |
| **Requirements** | [RecipeCove.txt](../Tasks/data/RecipeCove.txt) |

---

## 1. Context

RecipeCove is a web application for discovering, bookmarking and learning about recipes and ingredients. Discovery is the central focus. It happens through a search bar and a Chat-BOT that suggests recipes for a specific diet. Registered users also have a profile, a favorites list and an application calendar with recipe reminders.

**Functional scope (14 user stories):**
- **Visitor:**
  - registers with a Google account (US1);
  - searches recipes by name (US2);
  - views recipe details (US3) and ingredient details (US4);
  - sees diet-based suggestions (US5).
- **Registered user:**
  - logs in (US6) and logs out (US7);
  - views their profile (US8);
  - creates (US9) and deletes (US10) a calendar, and adds recipe events/reminders to it (US11);
  - adds (US12), removes (US13) and lists (US14) favorite recipes.

**Assumptions** (from the discussion, A1–A6):
- The team is 3–5 developers with one codebase and no dedicated ops person.
- Launch is at ~1k daily active users (DAU). The growth scenario is 100k DAU, which is ~115 req/s at peak and ~2–3 writes/s (estimate).
- Traffic is very read-heavy: catalog reads to writes are ≥ 50:1.
- Recipes and ingredients are **imported nightly** from an external dataset/API into our own database. They are not proxied live.
- The Chat-BOT is an **LLM with tool calling over our own catalog**. Diet suggestions (US5) are **precomputed daily**.
- Reminders are delivered by **email**.
- Google (OpenID Connect) is the only identity provider. There are no local passwords.

## 2. Decision Drivers

1. **Fit for a small team.** There are few deployables, a simple local setup, and low operational burden.
2. **Data consistency.** Favorites and calendar events reference recipes. Deleting a calendar (US10) and deleting an account (GDPR) must remove all related data reliably.
3. **Read-heavy, cacheable catalog traffic.** Search (US2) and detail pages (US3–4) are the main load.
4. **Isolation of the slow, expensive LLM path.** The Chat-BOT must not degrade search and browsing, and its cost must stay under control.
5. **Correct scheduled reminders** (US11). Each reminder is sent exactly once, at the right local time.
6. **Predictable cost and low vendor lock-in**, with a growth path if traffic booms.

## 3. Considered Options

| | Option | Short description |
|---|---|---|
| **A** | **Modular Monolith** | One deployable (+ worker process), one PostgreSQL DB with a schema per module, modules communicate via public APIs and in-process events. |
| B | Microservices + API Gateway + Event Bus | Identity, Catalog, Chat, Favorites, Calendar and Notification services, each with its own DB, connected by a message broker. |
| C | Serverless / Backend-as-a-Service | Managed auth + database (Firebase/Supabase), client accesses data via security rules, cloud functions for chat, import and reminders. |

### Comparison (1 = worst, 5 = best for RecipeCove)

| Metric | A | B | C |
|---|---|---|---|
| Initial development effort | 4 | 1 | 5 |
| Time to market | 4 | 1 | 5 |
| Operational burden | 4 | 1 | 5 |
| Infra cost at low traffic | 4 | 1 | 5 |
| Cost predictability at high scale | 4 | 3 | 2 |
| Independent scalability | 2 | 5 | 4 |
| Fault isolation | 2 | 5 | 3 |
| Data consistency / integrity | 5 | 2 | 3 |
| Testability & local development | 5 | 2 | 2 |
| Vendor independence | 5 | 4 | 1 |
| Fit for team size | 5 | 1 | 4 |
| Evolvability | 4 | 4 | 2 |
| **Total** | **48** | **30** | **41** |

## 4. Decision

**We choose Option A – Modular Monolith**, with the following binding rules:

1. **Five modules, one deployable.** The backend consists of the modules `identity` (incl. profile), `catalog` (recipes, ingredients, diets, search), `chat`, `favorites` and `calendar` (incl. reminders). It is built and deployed as one application. A separate **worker process** is started from the same codebase and build artifact.
   *Rejected alternative:* separate services per capability (Option B). It brings distributed consistency and ops overhead without a proven scaling need.
2. **Public module API only.** A module may call another module only through that module's public API package (interfaces/DTOs). Internal classes, repositories and entities are not visible outside the module. Architecture tests in CI enforce this, e.g. Spring Modulith / ArchUnit / import-linter / dependency-cruiser, depending on stack.
3. **One PostgreSQL schema per module, no cross-schema joins or foreign keys.** Each module owns its schema and has its own database role with write access only to that schema. Other modules reference recipes by `recipe_id` and resolve them through the `catalog` API using batch lookups.
   *Rejected alternative:* shared tables with cross-module foreign keys. They are easier at first, but they couple modules and block later extraction.
4. **Acyclic module dependencies.** Dependencies may only point in this direction: `favorites`, `calendar`, `chat` → `catalog`; all → `identity`. Reverse-direction notifications use **in-process domain events**, e.g. `UserDeleted` and `RecipeRemoved`. A CI check fails on cycles.
5. **Catalog data is imported, not proxied.** A nightly job in the worker upserts recipes and ingredients from the external source idempotently, keyed by source ID. Recipes removed upstream are **soft-deleted**, so existing favorites and calendar events still resolve.
6. **Catalog reads are public and cacheable.** `GET` endpoints for recipes, ingredients, search and diet suggestions carry `Cache-Control: public` headers and are served through a CDN. Diet suggestions (US5) are precomputed daily and use no LLM calls.
7. **Search uses PostgreSQL full-text search + `pg_trgm`** on recipe name in v1. It must be accessed only through the `catalog` search API, so that it can later be replaced by a dedicated engine.
   *Rejected alternative (for now):* Meilisearch/OpenSearch from day one. It adds a second datastore plus index synchronization before search quality has been measured.
8. **Chat-BOT is isolated and cost-limited.**
   - The LLM answers only through tools that call the `catalog` API (`search_recipes`, `get_recipe`). It never returns recipes that do not exist in the catalog.
   - Responses are streamed via SSE on a **separate thread pool/executor** from the regular API.
   - The LLM API key exists only on the server.
   - Requests are rate-limited per user and per IP for visitors.
   - On LLM failure or timeout, the UI falls back to the precomputed diet suggestions.
9. **Authentication via Google OIDC with server-side sessions.**
   - Login (US1, US6) uses the Authorization Code flow with PKCE.
   - The backend issues an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie. The session is stored in Redis/Postgres.
   - Logout (US7) deletes the server-side session immediately.
   *Rejected alternative:* stateless JWTs in the browser. They cannot be revoked at logout without an extra blocklist, and they are more exposed to XSS when kept in browser storage.
10. **Reminders are scheduled idempotently in UTC.**
    - A calendar event stores the local date/time and the user's IANA time zone, plus a computed `due_at_utc` that is recomputed on every edit.
    - The worker runs every 5 minutes. It selects due, unsent reminders with `FOR UPDATE SKIP LOCKED` and sets `sent_at` in the same transaction as enqueuing the email.
    - A reminder with `sent_at` set is never sent again.
11. **Deletes are transactional and complete.**
    - Deleting a calendar (US10) removes its events and pending reminders in one transaction.
    - Deleting an account publishes `UserDeleted`. Every module hard-deletes that user's data in the same transaction.
    - An integration test verifies that no row with the user's ID remains in any schema.

### Architecture overview

```
                     ┌──────────────── CDN (static SPA + cached public GET /api/catalog/*) ─────┐
 Browser (SPA) ──────┤                                                                         │
                     └────────────────────────────────┬────────────────────────────────────────┘
                                                      │ HTTPS (REST + SSE for chat), session cookie
                 ┌────────────────────────────────────▼─────────────────────────────────────┐
                 │                    RecipeCove Application (1 deployable)                 │
                 │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
                 │  │ identity │ │  catalog  │ │   chat   │ │ favorites │ │   calendar   │  │
                 │  │ +profile │ │ recipes,  │ │ LLM tool │ │           │ │ + reminders  │  │
                 │  │ (OIDC,   │ │ ingred.,  │ │ calling, │ │           │ │              │  │
                 │  │ sessions)│ │ diets,    │ │ own exec.│ │           │ │              │  │
                 │  │          │ │ search    │ │ pool     │ │           │ │              │  │
                 │  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬─────┘ └──────┬───────┘  │
                 │       │   public module APIs + in-process domain events (UserDeleted…)   │
                 └───────┼─────────────┼────────────┼─────────────┼──────────────┼──────────┘
                         │             │            │             │              │
             ┌───────────▼─────────────▼────────────▼─────────────▼──────────────▼───┐
             │ PostgreSQL – schemas: identity | catalog | chat | favorites | calendar │
             │             (FTS + pg_trgm index on catalog.recipe.name)               │
             └───────────────────────────────────────────────────────────────────────┘
   Redis (sessions, cache, rate limits)   Worker process (same codebase):
                                            • nightly catalog import ──► Recipe dataset/API
                                            • daily diet-suggestion precompute
                                            • reminder dispatcher (every 5 min) ──► Email provider
   External: Google OIDC ◄── identity          LLM API ◄── chat
```

### User story → component mapping

| User stories | Component |
|---|---|
| US1, US6, US7 | `identity` (Google OIDC, server-side sessions) |
| US8 | `identity` (profile) |
| US2, US3, US4 | `catalog` (search API, recipe/ingredient endpoints, CDN-cached) |
| US5 | `catalog` (precomputed diet suggestions) + `chat` (LLM tool calling over `catalog` API) |
| US9, US10, US11 | `calendar` (+ worker reminder dispatcher, email provider) |
| US12, US13, US14 | `favorites` (resolves recipe details via `catalog` batch API) |

## 5. Consequences

### Positive
- One build, one deployment and one database make local development, debugging and end-to-end testing simple for a 3–5 person team.
- Calendar deletion (US10) and account deletion are single transactions with no eventual consistency.
- The catalog is served largely from the CDN. The estimated 100k-DAU scenario (~115 req/s peak) fits on a few stateless app instances. Estimated infra cost is ~$200–500/month, excluding LLM; this is a list-price ballpark to be verified.
- Cost grows step-wise and predictably, with no vendor lock-in. Standard PostgreSQL, Redis and OIDC are used throughout.
- Module boundaries (rules 2–4) keep a path open to extract modules into services later (strangler pattern).

### Negative
- Limited fault isolation. A crash or memory leak in any module, e.g. chat, affects the whole application, which rule 8 only partly mitigates.
- All modules scale together. The slow LLM path cannot be scaled independently until `chat` is extracted.
- Every change redeploys the whole application.
- The "no cross-schema joins" rule removes database-level referential integrity between modules. Recipe references are resolved through the `catalog` API, and dangling references are handled by soft-delete (rule 5).
- PostgreSQL full-text search has a quality ceiling for typos, synonyms and ranking (rule 7).
- Module discipline depends on CI architecture tests. Without them the monolith decays.
- LLM usage remains the dominant running cost in every option. At 100k DAU it is estimated at ~$2k–9k/month (estimate).

## 6. When to Revisit This Decision

Re-evaluate if any of these happens (thresholds are initial proposals, to be calibrated against production metrics):
- Chat p95 time-to-first-token > 3 s, or chat load measurably degrades p95 latency of catalog endpoints. **Then extract `chat` first.**
- Search quality metrics, e.g. zero-result rate > 10 % or click-through on the first results page < 30 %, stay below target after tuning. **Then introduce a dedicated search engine fed by an outbox.**
- More than ~8 developers / 2+ teams work on the codebase and deployments block each other.
- Sustained traffic > ~500 req/s at the origin (after CDN), or DB CPU > 70 % at peak after adding read replicas.
- Monthly LLM spend exceeds the agreed budget despite the rate limits.

## 7. Follow-up Decisions

- **ADR-002:** Recipe/ingredient data source, licence and attribution, import mapping.
- **ADR-003:** LLM provider and model, prompt/tool design, rate limits and monthly budget for the Chat-BOT.
- **ADR-004:** Concrete technology stack (backend framework, SPA framework, hosting/PaaS, CDN).
- **ADR-005:** Reminder channels (email provider; whether to add web push) and user notification preferences.
- **ADR-006:** GDPR procedures: account deletion flow, data export, retention of chat logs.

## 8. Revision History

| Version | Date | Change |
|---|---|---|
| v1 | 2026-10-29 | Initial version generated from the architecture discussion. |
| v2 | 2026-10-29 | Deciders confirmed rules 7 (Postgres FTS in v1), 9 (server-side sessions), 10 (email reminders, 5-min dispatcher) and 11 (hard delete); section 6 thresholds marked as initial proposals. |
| v3 | 2026-10-29 | Status changed from Proposed to Accepted. |
