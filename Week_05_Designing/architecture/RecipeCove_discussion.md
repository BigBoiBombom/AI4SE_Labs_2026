# Architecture Discussion – RecipeCove

Record of the conversation between the user and the coding assistant.
Not a 1:1 transcript – a running log of questions, proposals, explanations and decisions.

- **Date:** 2026-10-29
- **Project:** RecipeCove (`Week_05_Designing/Tasks/data/RecipeCove.txt`)
- **Goal:** Propose and discuss 3 architectures, understand trade-offs and painful implementation parts, choose one.

---

## Session 1

### 1. Requirements analysis and 3 architecture proposals

**User:** Read `RecipeCove.txt` and suggest an architecture for the software.

**Assistant:**

#### 1.1 Requirements summary

| Capability | User stories | Actor |
|---|---|---|
| Identity (Google sign-up, login, logout) | US1, US6, US7 | Visitor / registered user |
| Recipe & ingredient catalog (search by name, recipe detail, ingredient detail) | US2, US3, US4 | Visitor |
| Diet-based suggestions + Chat-BOT | US5 (+ system description) | Visitor |
| Profile | US8 | Registered user |
| Favorites (add, remove, list) | US12, US13, US14 | Registered user |
| Calendar & reminders (create/delete calendar, add recipe event) | US9, US10, US11 | Registered user |

**External integrations**
- **Google OAuth 2.0 / OpenID Connect**: the only sign-up path (US1).
- **Recipe/ingredient data source**: not specified. "A wide range of recipes" suggests a 3rd-party dataset/API (e.g. TheMealDB, Spoonacular, Edamam) or an imported open dataset.
- **LLM provider** for the Chat-BOT.
- **Reminder delivery** (US11 says "be reminded"): email and/or web push.

**Implicit non-functional concerns**
- **Very read-heavy:** search plus recipe/ingredient views are mostly anonymous traffic. Writes are only favorites, calendar, and profile. Estimated reads:writes is about 50:1 or higher.
- **Search quality matters** because it is the "central focus": typos, partial names, diacritics.
- **Slow, expensive external call:** the LLM takes 2–20 s and is billed per token. Visitors can use it too (US5), so it needs abuse/rate limiting.
- **Scheduled job:** reminders must fire on the right day in the user's time zone, exactly once.
- **Privacy/GDPR:** US10 explicitly wants to "remove the data gathered". Account deletion should also be expected.
- **3rd-party recipe API quotas and licensing:** catalog data should be imported or cached, not proxied on each request.

#### 1.2 Assumptions (can be challenged)

| # | Assumption | Drives |
|---|---|---|
| A1 | Team of 3–5 developers, one codebase, no dedicated ops person | Favors few deployables |
| A2 | Launch at ~1k DAU; "boom" scenario 100k DAU | Scale section |
| A3 | Recipes/ingredients are **imported** from an external dataset/API into our own DB (nightly sync), not proxied live | Catalog owns its data; no API quota on hot path |
| A4 | Diet suggestions (US5) are **precomputed** per diet (vegan, keto, gluten-free, ...) from tags. The Chat-BOT is an LLM with **tool calling over our own catalog** (search_recipes, get_recipe), so it never invents recipes | Cost control, correctness |
| A5 | Reminders are sent by **email** (optional web push), at a user-chosen time on the event day, in the user's time zone | Scheduler design |
| A6 | Google is the only identity provider; no local passwords | Auth is simple; no password storage |

#### 1.3 Architecture A – Modular Monolith

```
                     ┌──────────────── CDN (static SPA + cached GET /recipes/*) ───────────────┐
 Browser (SPA) ──────┤                                                                        │
                     └────────────────────────────────┬───────────────────────────────────────┘
                                                      │ HTTPS (REST + SSE for chat)
                 ┌────────────────────────────────────▼─────────────────────────────────────┐
                 │                    RecipeCove Application (1 deployable)                 │
                 │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
                 │  │ Identity │ │  Catalog  │ │   Chat   │ │ Favorites │ │  Calendar &  │  │
                 │  │ +Profile │ │ recipes,  │ │ LLM tool │ │           │ │  Reminders   │  │
                 │  │ (OIDC)   │ │ ingred.,  │ │ calling  │ │           │ │              │  │
                 │  │          │ │ diets,    │ │          │ │           │ │              │  │
                 │  │          │ │ search    │ │          │ │           │ │              │  │
                 │  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬─────┘ └──────┬───────┘  │
                 │       │ public module APIs + in-process domain events (UserDeleted…)     │
                 └───────┼─────────────┼────────────┼─────────────┼──────────────┼──────────┘
                         │             │            │             │              │
             ┌───────────▼─────────────▼────────────▼─────────────▼──────────────▼───┐
             │ PostgreSQL – one schema per module: identity | catalog | chat |       │
             │             favorites | calendar   (+ full-text / pg_trgm index)       │
             └──────────────────────────────────────────────────────────────────────┘
   Redis (cache, rate limits)      Worker process (same codebase):
                                     • nightly catalog import  ──► Recipe dataset/API
                                     • reminder dispatcher (every 5 min) ──► Email/Push provider
   External: Google OIDC ◄── Identity        LLM API ◄── Chat
```

- **What it is:** one deployable app and one PostgreSQL DB. The app is split internally into modules along the capabilities in 1.1, each with its own schema and public API. A second process from the same codebase runs background jobs.
- **Why it fits:**
  - 14 user stories are mostly CRUD plus search, which is a small domain for 3–5 devs (A1).
  - Favorites (US12–14) and calendar events (US11) both reference recipes. In one DB that reference is cheap and consistent (e.g. "list favorites with titles and images" is one query through Catalog's API).
  - US10 (delete calendar, remove data) is a single transaction.
  - Postgres full-text plus `pg_trgm` covers search by name (US2) without another system.
  - The Chat module calls Catalog in-process as its tool implementation (A4).
- **Painful parts:**
  - **The LLM call blocks request threads** for 2–20 s. Stream the reply over SSE from an async handler or a separate thread pool, or a few dozen concurrent chats can starve the normal API.
  - **Keeping it modular.** Without enforcement (architecture tests, no cross-schema joins), Favorites will start joining `catalog.recipe` directly, and it decays into a big ball of mud.
  - **Reminder dispatcher correctness.** Store the event as a local date and time plus the user's IANA time zone, and compute `due_at_utc`. The dispatcher selects due rows with `FOR UPDATE SKIP LOCKED` and marks `sent_at` in the same transaction. Retries must be idempotent so nobody gets two emails. DST shifts change `due_at_utc`, so recompute it on edit.
  - **Search quality ceiling.** Synonyms ("aubergine"/"eggplant"), typos, and ranking by popularity are hard in Postgres FTS. If needed later, add Meilisearch/OpenSearch, and then you must keep the index in sync (outbox pattern).
  - **Catalog import.** Upserts must be idempotent. Recipes deleted upstream may still be someone's favorite (soft-delete, keep a snapshot). Respect the data licence and attribution.
  - **Whole-app redeploy** for every change. One bad module can crash everything.

#### 1.4 Architecture B – Microservices + API Gateway + Event Bus

```
 Browser (SPA) ──► CDN ──► API Gateway (JWT validation, rate limiting, routing)
                                 │
   ┌──────────────┬──────────────┼──────────────┬───────────────┬────────────────┐
   ▼              ▼              ▼              ▼               ▼                ▼
┌────────┐  ┌──────────┐  ┌─────────────┐ ┌───────────┐  ┌────────────┐  ┌──────────────┐
│Identity│  │ Catalog  │  │ Chat/Suggest│ │ Favorites │  │  Calendar  │  │ Notification │
│Profile │  │ svc      │  │ svc         │ │ svc       │  │  svc       │  │ svc          │
└───┬────┘  └────┬─────┘  └──────┬──────┘ └─────┬─────┘  └─────┬──────┘  └──────┬───────┘
    │            │               │              │              │                │
 [Postgres]  [Postgres +     [Redis/ conv.  [Postgres]     [Postgres]       [Postgres:
  users]      OpenSearch]     store]         favs+recipe    calendars,       sent log]
    │            │               │           snapshot       events
    │            │  sync REST    │              │              │                │
    │            │◄──────────────┘ (tools)      │              │                │
    ▼            ▼                              ▼              ▼                ▼
 ═══════════════════════  Event bus (RabbitMQ / Kafka)  ═════════════════════════════
   UserDeleted, RecipeUpdated, RecipeRemoved, EventScheduled, ReminderDue ...
                 ▲
   Catalog Import job ── Recipe dataset/API         Scheduler ──► ReminderDue ──► Notification ──► Email/Push
   External: Google OIDC ◄── Identity        LLM API ◄── Chat
```

- **What it is:** each capability is an independently deployed service with its own database. The services sit behind an API gateway. Cross-service facts travel as events on a message broker.
- **Why it fits:**
  - The workloads really are different: catalog/search is read-heavy and cacheable, chat is slow and expensive, and reminders are batch/scheduled. Each could scale and fail independently. For example, an LLM outage must not take down search (US2–4).
  - Catalog can use a dedicated search engine (OpenSearch) without affecting the others.
- **Painful parts:**
  - **References across data boundaries.** Favorites and Calendar store `recipe_id` with no foreign key. "My favorites" (US14) needs titles and images, so you either call Catalog per item (N+1, latency, coupling) or keep a **recipe snapshot** in Favorites updated from `RecipeUpdated`/`RecipeRemoved` events (eventual consistency, extra code).
  - **User deletion propagation (GDPR).** `UserDeleted` must be consumed by Favorites, Calendar, Chat, and Notification. Each must be idempotent, and you need a way to prove that everything was deleted.
  - **Chat depends synchronously on Catalog** for its tools. Catalog latency adds to every LLM turn. You need timeouts and circuit breakers, or a replicated read model.
  - **Distributed reminder pipeline.** Scheduler, broker, and Notification each need at-least-once delivery plus a dedup key so nobody gets duplicate emails.
  - **Ops and local development:** 6–7 services, the broker, 4–5 databases, the search engine, the gateway, distributed tracing, and per-service CI/CD. Running everything locally needs a heavy docker-compose. That is a big overhead for 14 user stories and a small team (A1).
  - **Contract versioning** between services and events.

#### 1.5 Architecture C – Serverless / Backend-as-a-Service

```
 Browser (SPA, hosted on CDN: Firebase Hosting / Vercel)
   │  Firebase/Supabase Auth SDK (Google provider)  ──► Google OIDC
   │
   ├──► Firestore / Supabase DB  (direct reads/writes, guarded by SECURITY RULES / RLS)
   │       users/{uid}/favorites/{recipeId}   ← denormalized recipe snippet
   │       users/{uid}/calendars/{cid}/events/{eid}
   │       recipes/{id}, ingredients/{id}, diets/{diet}/suggestions (precomputed)
   │
   ├──► Search SaaS (Algolia / Typesense Cloud) ◄── sync extension / trigger on recipes
   │
   └──► Cloud Functions (HTTPS)
           • chat()  ──► LLM API  (API key server-side, rate limit per uid/IP)
        Scheduled Functions (Cloud Scheduler)
           • nightlyImport() ──► Recipe dataset/API ──► recipes, ingredients, diets
           • dispatchReminders() every 5–15 min ──► Email/Push (SendGrid / FCM)
        Trigger Functions
           • onCalendarDelete → recursive delete of events (US10)
           • onUserDelete     → delete users/{uid} subtree (GDPR)
```

- **What it is:** no own servers. A managed BaaS provides auth, database, and hosting. The client talks to the DB directly under security rules. Only the logic that must stay secret or run on a schedule lives in functions.
- **Why it fits:**
  - US1/6/7 (Google login and logout) are built in.
  - Most stories (US8–14) are per-user CRUD that maps naturally to `users/{uid}/...` documents protected by a single rule (`request.auth.uid == uid`).
  - Static recipe pages go through the CDN.
  - It costs almost nothing at launch traffic (A2), and is the fastest path to a working product.
- **Painful parts:**
  - **No full-text search** in Firestore, so you need Algolia/Typesense plus a sync, and that is a second paid vendor. Supabase (Postgres) avoids this.
  - **No joins, so you denormalize.** Each favorite holds a copy of the recipe title and image, and a recipe update must fan out to all copies, or you accept stale data.
  - **Security rules are your backend.** One wrong rule exposes every user's calendars. Rules need their own tests in the emulator, and complex rules (e.g. validating an event's `recipeId` exists) are awkward.
  - **LLM in a function:** cold starts, execution timeouts, streaming support that varies by platform, and per-invocation cost.
  - **Reminder dispatcher:** same idempotency and time-zone problems as in A. On top of that, the batch must fit within a function timeout, and you have to handle overlapping runs.
  - **Recursive deletes** (US10, account deletion) are not atomic. Large subcollections need batched deletes in a trigger.
  - **Vendor lock-in:** data model, rules, and SDK calls are provider-specific, and migrating out is a rewrite. EU data region must be chosen up front for GDPR.
  - **Cost scales linearly** with document reads, so a chatty UI can multiply the bill.

#### 1.6 Scored comparison (1 = worst, 5 = best for RecipeCove)

| Metric | A Modular Monolith | B Microservices | C Serverless/BaaS |
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
| Fit for team size (3–5 devs) | 5 | 1 | 4 |
| Evolvability | 4 | 4 | 2 |
| **Total (max 60)** | **48** | **30** | **41** |

(Re-added: A = 4+4+4+4+4+2+2+5+5+5+5+4 = 48; B = 1+1+1+1+3+5+5+2+2+4+1+4 = 30; C = 5+5+5+5+2+4+3+3+2+1+4+2 = 41.)

#### 1.7 User story → component mapping

| US | A Modular Monolith | B Microservices | C Serverless/BaaS |
|---|---|---|---|
| 1 Register with Google | Identity module (OIDC) | Identity svc + Gateway | BaaS Auth (Google provider) |
| 2 Search by name | Catalog module (Postgres FTS/trgm) | Catalog svc (OpenSearch) | Algolia/Typesense + sync |
| 3 Recipe info | Catalog module (+CDN cache) | Catalog svc (+CDN) | `recipes/{id}` doc read |
| 4 Ingredient info | Catalog module | Catalog svc | `ingredients/{id}` doc read |
| 5 Diet suggestions / Chat-BOT | Chat module → Catalog API; precomputed diet lists in Catalog | Chat svc → Catalog svc (REST) | `diets/{d}` docs + `chat()` function |
| 6 Login | Identity module (session cookie) | Identity svc issues JWT, Gateway validates | Auth SDK |
| 7 Logout | Identity module (invalidate session) | Identity svc (revoke/short TTL JWT) | Auth SDK `signOut()` |
| 8 Profile | Identity/Profile module | Identity/Profile svc | `users/{uid}` doc |
| 9 Create calendar | Calendar module | Calendar svc | `users/{uid}/calendars` |
| 10 Delete calendar | Calendar module (1 transaction, cascades events + pending reminders) | Calendar svc + `CalendarDeleted` → Notification | Trigger: recursive delete |
| 11 Add event / reminder | Calendar module + worker dispatcher | Calendar svc → Scheduler → Notification svc | Event doc + scheduled `dispatchReminders()` |
| 12 Add favorite | Favorites module | Favorites svc (stores recipe snapshot) | `users/{uid}/favorites/{rid}` (denormalized) |
| 13 Remove favorite | Favorites module | Favorites svc | delete doc |
| 14 List favorites | Favorites module → Catalog API (batch) | Favorites svc (snapshot) or N+1 to Catalog | read subcollection |

#### 1.8 Scale and cost: "what if it booms?"

**Workload at 100k DAU (assumption A2)**

| Quantity | Estimate |
|---|---|
| API requests | ~20 per user/day → 2M/day → **~23 req/s avg, ~115 req/s peak (5×)** |
| Writes (favorites, calendar, profile) | ~2 per user/day → 200k/day → **~2–3 writes/s** (trivial) |
| Searches | ~5 per user/day → 500k/day → ~6/s avg, ~30/s peak |
| Chat | 20 % of DAU × 5 messages → 100k messages/day; ~3k tokens each (system prompt + tool results + answer) → **~300M tokens/day ≈ 9B tokens/month** |
| Reminder emails | ~5 % of DAU have an event that day → ~5k emails/day (trivial) |

- **Dominant cost driver: the LLM.** This holds for every architecture. Even a small, cheap model at ~$0.25–1 per 1M blended tokens gives **~$2k–9k/month**, more than all infra in A.
  - Precompute US5 diet suggestions daily so they cost no tokens.
  - Use the cheapest model that handles tool calling well.
  - Keep the system prompt short and use prompt caching.
  - Return compact tool results (IDs and titles, not full recipes).
  - Cap turns per conversation.
  - Rate-limit visitors per IP and require login after N messages.
  - Cache answers to identical first questions.
- **Cheapest universal lever: CDN plus cache for catalog reads.** Recipe and ingredient pages are public and change once a day after the import. With `Cache-Control: public, max-age=…`, most of the ~115 req/s peak never reaches the backend.
- **Secondary driver:** search SaaS (C) or search cluster (B), and BaaS per-document read pricing (C).

**Per-architecture scaling**

| | A Modular Monolith | B Microservices | C Serverless/BaaS |
|---|---|---|---|
| How it scales | Stateless app replicas behind a load balancer; Postgres read replica; Redis cache | Scale each service independently (HPA on k8s); Catalog/OpenSearch scales separately from Chat | Automatic (managed DB, functions, CDN) |
| Time to add capacity | Minutes (add replica) | Minutes per service (autoscaling) | Seconds (automatic) |
| Prerequisites | Stateless sessions (Redis/cookie), SSE-capable LB, connection pooler (PgBouncer) | k8s/ECS, observability, autoscaling policies per service | Quotas raised; budget alerts; efficient query/document design |
| First bottleneck | Chat streaming connections and DB connections; FTS ranking cost on large catalogs | Synchronous Chat→Catalog calls; broker throughput is a non-issue at this scale | Search SaaS bill; function concurrency limits/timeouts on chat |
| Monthly infra ballpark @1k DAU | ~$20–60 (1 small VM/PaaS + managed Postgres) | ~$300–600 (cluster, broker, several DBs, search) | ~$0–30 (free tiers) |
| Monthly infra ballpark @100k DAU | ~$200–500 (2–4 instances, Postgres + replica, Redis, CDN) | ~$1,000–2,500 | ~$500–3,000+ (dominated by search SaaS + doc reads) |
| Cost-curve shape | Step-wise (add instances) | Step-wise, higher baseline | Linear per request/read |

All prices are **list-price ballparks to be verified** against current provider pricing. LLM cost comes on top in all three.

#### 1.9 Recommendation

**Choose A – Modular Monolith** (React/Vue SPA + one backend, e.g. Spring Boot/Spring Modulith, Django, NestJS, or ASP.NET).
- It has the best fit for a small team and 14 mostly-CRUD user stories.
- It gives true consistency for favorites, calendar, and recipe references, and transactional deletes (US10, GDPR).
- It is easy to run locally and test, and cost stays predictable when traffic grows. With CDN caching it handles the 100k-DAU scenario on a handful of instances.

**When another option wins**
- **C** wins if the goal is a prototype/demo in a few weeks, the team is 1–2 people with no ops experience, and lock-in is acceptable. Prefer **Supabase** over Firestore to keep Postgres (FTS, joins, RLS) and a migration path.
- **B** wins only with several independent teams, or proven, very different scaling needs. Example: the chatbot becomes the main product, with heavy traffic and its own release cadence.

**Growth path (strangler pattern, only when metrics show the need)**
1. Put the CDN in front of catalog GETs from day one.
2. Run Chat in a separate process or thread pool. It is the first module to **extract** into its own service, because its latency, cost, and scaling profile differ most.
3. Add a dedicated search engine (Meilisearch/OpenSearch) fed by an outbox, when Postgres FTS ranking stops being good enough.
4. Extract the reminder worker as a separate deployable; it already runs as a separate process.

**Decision / open question:** none yet; awaiting user choice or deep dive.

---
### 2. Outcome

**User:** Chose option 6 – "the one with the highest amount of points" (Architecture A, 48/60), and asked to continue with the ADR.

- **Chosen:** A – Modular Monolith. Key rules:
  - One deployable (plus a worker process from the same codebase) and one PostgreSQL database with **one schema per module** (identity, catalog, chat, favorites, calendar).
  - Modules talk only via public module APIs and in-process domain events (e.g. `UserDeleted`); no cross-module joins; acyclic dependencies, enforced by architecture tests in CI.
  - Catalog is imported nightly from an external dataset into our own DB; public catalog GETs are cached on a CDN.
  - Chat-BOT = LLM with tool calling over the Catalog API, streamed via SSE on a separate thread pool, rate-limited for visitors; diet suggestions (US5) are precomputed daily.
  - Reminders: events stored as local date/time + IANA time zone with computed `due_at_utc`; worker dispatches with `FOR UPDATE SKIP LOCKED` and an idempotent `sent_at` marker.
  - Growth path: extract Chat first, then add a dedicated search engine (via outbox), then split out the reminder worker – only when metrics show the need.
- **Rejected:**
  - B – Microservices: operational and consistency overhead (cross-service references, deletion propagation, 7 deployables) far exceeds what 14 user stories and a 3–5 person team need.
  - C – Serverless/BaaS: fastest to launch, but vendor lock-in, security-rules-as-backend risk, no native full-text search and linear cost growth.
- **Open topics / follow-up ADRs:** search engine choice (Postgres FTS vs. Meilisearch/OpenSearch); LLM provider/model and cost limits; recipe data source and licence; reminder channel (email vs. web push); session vs. JWT authentication; GDPR account-deletion procedure.

### Session metrics

| Metric | Value |
|---|---|
| User prompts until a decision | 2 |
| Clarification questions asked by the assistant | 0 (assumptions A1–A6 stated instead) |
| Corrections of earlier claims | 0 |
| Deep dives done | none |
