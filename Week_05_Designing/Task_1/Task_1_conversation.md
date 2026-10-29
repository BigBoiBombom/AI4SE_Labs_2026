# Task 1 – Architecture Discussion for RecipeCove

Record of the conversation between the student and the coding assistant (Claude Code).
Not a 1:1 transcript – a running log of questions, proposals, explanations and decisions.

- **Date:** 2026-10-29
- **Project:** RecipeCove (`Week_05_Designing/Tasks/data/RecipeCove.txt`)
- **Goal:** Discuss at least 3 different architectures for the system, understand their trade-offs and the painful parts of the low-level implementation.

---

## Session 1

### 1. Setup / context reading

**Student:** Asked the assistant to read all three task descriptions (Task 1, 2, 3) and the RecipeCove requirements, and to create a record file before each task.

**Assistant:** Read `Tasks/Task_1.md`, `Tasks/Task_2.md`, `Tasks/Task_3.md` and `Tasks/data/RecipeCove.txt`. Created this file to log the Task 1 discussion.

**Summary of RecipeCove requirements (as understood by the assistant):**
- Web app for recipe discovery, bookmarking, and recipe/ingredient information.
- Discovery via **search bar** (by recipe name) and a **Chat-BOT** suggesting recipes for a specific diet.
- **Visitors:** register via Google (external OAuth), search recipes, view recipe details, view ingredient details, see diet-based suggestions.
- **Registered users:** login/logout, profile page, create/delete a calendar, add recipe events (reminders) to the calendar, add/remove/view favorites.
- Implicit non-functional concerns: external identity provider, a recipe/ingredient data source (own DB or 3rd-party API), an LLM or rule-based chatbot, reminder delivery for calendar events.

---

### 2. Request: propose 3 architectures and compare them

**Student:** Review the requirements and propose 3 architectures best suited for RecipeCove. Be precise, explain each, why it was chosen, and compare them on different metrics.

**Assistant – working assumptions** (stated so they can be challenged):
- Small team (student / 2–5 devs), modest traffic, **read-heavy** workload (search + view details dominate).
- Recipe/ingredient data is **imported from an external source** (dataset or API such as Spoonacular) into our own store, so we control search and are not rate-limited per request.
- Chatbot = **LLM API with tool calling** that can only recommend recipes that exist in our catalog (filtered by diet tags), so it does not invent recipes.
- Reminders = email (or push) sent by a scheduler on the event day.

#### Architecture A – Modular Monolith (layered inside each module)

```
Browser (SPA / SSR) ──HTTPS──► Monolith app
                                ├─ Identity module (Google OAuth, sessions)
                                ├─ Catalog module (recipes, ingredients, search)
                                ├─ Chatbot module (LLM adapter + tools → Catalog API)
                                ├─ Library module (profile, favorites)
                                └─ Calendar module (calendars, events)
                                        │
                     PostgreSQL (one DB, schema per module, full-text search)
                                        │
                     Background worker (job queue) ──► Email provider (reminders)
External: Google OAuth, LLM API, recipe data import job
```
- One deployable unit, internally split into modules with explicit public interfaces; no module reads another module's tables.
- **Why:** 14 user stories, small and tightly related domain (favorites and calendar events both reference recipes). One DB gives foreign keys and transactions (for example, deleting a calendar removes its events atomically). Fastest to build, test and deploy. Module boundaries make it possible to split out services later.
- **Painful parts:** keeping module boundaries in place (it's tempting to join across modules); slow LLM calls tying up web workers (needs async/streaming and timeouts); the whole app is redeployed for every change; scaling is all-or-nothing; the reminder scheduler needs idempotency and correct time zones.

#### Architecture B – Microservices + API Gateway + Event Bus

```
Browser ──► API Gateway (JWT validation, rate limiting, routing)
              ├─► Identity Service ── users DB
              ├─► Catalog Service ── recipes DB + OpenSearch index
              ├─► Chatbot/Recommendation Service ── LLM API, calls Catalog
              ├─► User Library Service (profile, favorites) ── library DB
              └─► Calendar & Notification Service ── calendar DB + scheduler ──► Email
        Message broker (RabbitMQ/Kafka): UserRegistered, UserDeleted,
        RecipeUpdated, CalendarDeleted ...
```
- Each service owns its data and is deployed and scaled independently. Services communicate over REST synchronously and through events asynchronously.
- **Why:** the load profiles are very different: Catalog is cheap and read-heavy, while Chatbot is slow and expensive. Independent scaling and **fault isolation** mean an LLM outage doesn't take search down. Each service can use its own tech (for example, Python for the LLM service).
- **Painful parts:** no foreign keys across services (a favorite holds a recipeId owned by another service, so you either keep a denormalized snapshot or make a call at read time); eventual consistency; propagating a user deletion to every service (GDPR); distributed tracing and debugging; contract versioning; running 6+ containers locally; much higher ops cost. **Overkill for the current scope.**

#### Architecture C – Serverless / Backend-as-a-Service (JAMstack)

```
Browser ◄── CDN (static React/Next.js build)
   │
   ├─► Managed Auth (Firebase Auth / Cognito / Supabase) – Google provider
   ├─► Managed DB (Firestore/DynamoDB or Supabase Postgres) + row-level security
   │      (favorites, calendars, events, profiles)
   ├─► Hosted search (Algolia / Typesense Cloud) ◄── sync function on recipe change
   └─► Serverless functions
          ├─ /chat → LLM API (with catalog lookup tool)
          ├─ recipe import job
          └─ scheduled function (cron) → find today's events → send reminders
```
- No servers to manage. Login, CRUD and search are mostly commodity managed services; custom code lives only in functions.
- **Why:** most of the requirements are standard needs: Google login, user-owned CRUD (favorites, calendar) and search. At low traffic, pay-per-use costs close to nothing, scaling is automatic, and Google login is mostly configuration.
- **Painful parts:** vendor lock-in; access rules (security rules/RLS) are business logic that's hard to test; with a NoSQL store, recipe↔ingredient many-to-many and diet filters have to be denormalized; keeping DB and search index in sync; cold starts plus function timeouts with long or streamed LLM answers; local emulation is imperfect; costs are unpredictable if the chatbot gets abused, so per-user rate limits are needed.

#### Comparison (1 = worst, 5 = best for RecipeCove)

| Metric | A: Modular Monolith | B: Microservices | C: Serverless/BaaS |
|---|---|---|---|
| Initial development effort | 5 | 1 | 4 |
| Time to market | 4 | 1 | 5 |
| Operational burden | 4 | 1 | 5 |
| Infra cost at low traffic | 4 | 1 | 5 |
| Cost predictability at high scale | 4 | 3 | 2 |
| Independent scalability | 2 | 5 | 5 |
| Fault isolation (LLM down ≠ app down) | 2 | 5 | 4 |
| Data consistency / integrity | 5 | 2 | 3 |
| Testability & local development | 5 | 2 | 2 |
| Vendor independence | 5 | 4 | 1 |
| Fit for small team | 5 | 1 | 4 |
| Evolvability (path to growth) | 4 | 5 | 3 |

#### User story → component mapping

| US | A (module) | B (service) | C (managed piece / function) |
|---|---|---|---|
| 1, 6, 7 register/login/logout | Identity | Identity Svc | Managed Auth |
| 2 search by name | Catalog (Postgres FTS) | Catalog Svc + OpenSearch | Algolia/Typesense |
| 3, 4 recipe / ingredient info | Catalog | Catalog Svc | DB read (public rules) |
| 5 diet suggestions (chatbot) | Chatbot → Catalog | Chatbot Svc → Catalog Svc | `/chat` function |
| 8 profile | Library | User Library Svc | DB + Auth profile |
| 9–11 calendar + events | Calendar + worker | Calendar & Notification Svc | DB + scheduled function |
| 12–14 favorites | Library | User Library Svc | DB (RLS: owner only) |

**Assistant's preliminary recommendation:** **A (Modular Monolith)** for the current scope and team. Keep the Chatbot behind an interface and run the reminder sender as a separate worker process. Those are the two parts most likely to be split out first if load grows. C is a strong alternative if time to market matters most and vendor lock-in is acceptable. B only makes sense with several teams or much higher, uneven load.

**Open question for the student:** which architecture to go deeper on first (low-level implementation, data model, painful parts).

---

### 3. Scalability if the app booms – speed and cost

**Student:** What about scalability if the app booms? How fast can we scale, and how expensive would it be?

**Assistant – boom scenario used for estimates** (back-of-envelope, list-price ballparks; real prices must be checked):
- 1,000,000 daily active users (DAU), ~20 page views/searches each → **~20M requests/day ≈ 230 req/s average, ~1,200 req/s peak**.
- Writes (favorites, calendar events) ≈ 1 per user per day → **~12 writes/s**: trivial for any database.
- Chatbot: 10% of users × 3 messages = **300k LLM calls/day**, ~3k input + 300 output tokens each (prompt + tool results).

**Key insight #1 – the workload is read-heavy and the catalog is almost static.**
Recipe/ingredient pages and popular search results can be cached at a **CDN / Redis** (expected 90%+ hit rate). That one lever cuts origin load ~10× and works for **all three** architectures. Calendar and favorites writes never become the bottleneck.

**Key insight #2 – the dominant cost in a boom is the LLM, not the architecture.**
300k calls/day ≈ 900M input + 90M output tokens/day → roughly **$7k–40k/month** depending on the model. No architecture changes this. Mitigations: smaller/cheaper model, prompt caching, caching answers to common "diet X" questions, per-user rate limits, and serving US5 ("suggested recipes for a diet") from a **precomputed list**, with the LLM chat as an optional extra.

#### How each architecture scales

| | A: Modular Monolith | B: Microservices | C: Serverless/BaaS |
|---|---|---|---|
| How it scales | Horizontally: N stateless app instances behind a load balancer; Postgres primary + read replicas; Redis; CDN | Each service scales on its own (Kubernetes HPA); separate DBs; OpenSearch cluster | Automatically per request; managed DB/search scale for you |
| Speed to add capacity | App instances: **1–5 min** (autoscaling). Read replica: **~10–30 min**. Bigger DB primary: minutes of failover | Pods: **seconds**; new nodes: **1–5 min** | **Seconds**, no planning, but provider **quotas** (e.g. Lambda concurrency ~1,000 by default) need a support request (hours to days) |
| Prerequisites before a boom | Stateless app (sessions in Redis/signed cookies), connection pooling (PgBouncer), CDN, worker as separate process | Already built for it (but a lot of up-front work) | Request quota increases; design DB keys to avoid hot spots |
| Ceiling / first bottleneck | Single write primary (far away at ~12 writes/s); Postgres full-text search with millions of recipes → move search to OpenSearch | Practically none for this domain | Per-request pricing; NoSQL hot-key limits; search pricing |
| Est. infra cost at 1M DAU (excl. LLM) | **~$1.5k–4k/month** (6–10 app VMs, managed Postgres + 2 replicas, Redis, CDN) | **~$4k–10k/month** (cluster, gateway, broker, several DBs, OpenSearch, observability) + DevOps salary | **~$3k–5k/month** for functions + DB reads; **hosted search priced per request can explode** (e.g. Algolia-style ~$0.50/1k searches × 150M searches/month ≈ **$75k/month**); a self-sized Typesense/OpenSearch cluster is far cheaper |
| Cost curve | Step-wise, flat and predictable | Step-wise, high base | Near $0 at start, **linear with traffic**; above a few hundred thousand DAU it usually becomes more expensive than A |

**Notes:**
- B's "scale the chatbot independently" advantage is smaller than it looks: the heavy lifting happens at the external LLM provider, so the chatbot service itself is lightweight and mostly waits on I/O. The real reason to isolate it is **fault isolation** and **cost control**, not CPU.
- C wins on *speed* of scaling (zero effort), but loses on *cost per request* at high volume and has hidden limits (quotas, hot keys).
- A can handle ~1M DAU with the prerequisites in place. The growth path is the **strangler pattern**: extract Chatbot and Search into their own services first, only when metrics show the need.

**Assistant's conclusion:** A boom doesn't change the recommendation. **A + CDN caching + read replicas + LLM cost controls** covers realistic growth at the lowest, most predictable cost. Design A to be stateless from day one so horizontal scaling is a configuration change, not a rewrite.

---

### 4. What makes the monolith *modular*, and how to keep it that way

**Student:** I understand the monolith, but what exactly makes it modular? Or better: how can we ensure it will stay modular?

**Assistant – what "modular" means concretely (4 rules):**
1. **Each module is a vertical slice of the domain** (Identity, Catalog, Chatbot, Library, Calendar) with its own controllers, services, domain model and persistence. It is not a horizontal layer like "all controllers".
2. **Each module exposes a small public API** (a facade interface + DTOs). Everything else is internal. Other modules may only call the public API, never internal classes or the module's tables.
3. **Each module owns its data:** its own Postgres schema (`catalog.*`, `library.*`, `calendar.*`, ...). No module reads or writes another module's tables. Joins are only allowed *inside* a module.
4. **Dependencies form a one-way graph with no cycles:**
   ```
   Chatbot ──► Catalog ◄── Library        Identity (depends on nothing)
                  ▲                          │  publishes UserDeleted
                  └──── Calendar             ▼  (Library & Calendar subscribe)
   ```
   Catalog and Identity depend on nothing. When a direction would point "upwards" (Identity needs Library/Calendar to delete user data), we use an **in-process domain event** (`UserDeleted`) instead of a direct call, so no cycle appears.

**Correction/clarification of an earlier claim (section 2):** "one DB gives foreign keys" is fully true only **inside a module** (calendar ↔ events: FK + transaction). Across modules (`library.favorites.recipe_id` → `catalog.recipes`) we deliberately **don't** use a FK. We store the ID, validate it via `Catalog.exists(id)` on write, and react to a `RecipeRemoved` event. This is the price of modularity. The pragmatic alternative is to allow cross-schema FKs only towards the stable Catalog, accepting extra coupling, and to record that decision in the ADR.

**Example folder structure (stack-agnostic):**
```
src/
  modules/
    catalog/
      api/          ← PUBLIC: CatalogFacade, RecipeSummaryDto, events
      internal/     ← domain, repositories, search, controllers
    library/
      api/
      internal/     ← may import catalog/api only
    calendar/ ...
  shared/kernel/    ← tiny: UserId, RecipeId, Clock, event bus interface
```
Read-side composition example: the favorites page calls `catalog.getRecipeSummaries(ids[])` **in one batch call** (to avoid N+1 calls) instead of a SQL join, with caching if needed.

**How to *enforce* it (so it doesn't decay) – from strongest to weakest:**

| Level | Mechanism | Example tools | Cost |
|---|---|---|---|
| Build | Each module is a separate build unit; the build fails if a dependency is undeclared | Gradle/Maven multi-module, .NET projects, npm workspaces / Nx with `enforce-module-boundaries`, Python packages | Medium |
| Language | `internal` / package-private visibility; only `api/` is exported | Java package-private + JPMS, Kotlin/C# `internal`, TS `exports` in package.json | Low |
| Architecture tests in CI | Rules like "nothing imports `*/internal/*` from another module" and "no cycles" | ArchUnit, Spring Modulith (`ApplicationModules.verify()`), NetArchTest, import-linter (Python), dependency-cruiser / eslint-plugin-boundaries (TS) | Low, **highest value** |
| Database | One Postgres schema per module; optionally one DB role per module with `GRANT` only on its own schema (costs separate connection pools) | Postgres schemas + roles; or a test checking that ORM entities only map to their own schema | Low–Medium |
| Process | CODEOWNERS per module; ADR for every new cross-module dependency; review checklist | GitHub CODEOWNERS | Low |
| Monitoring | Track the module dependency graph and cross-module calls over time; alert on new edges | dependency-cruiser graph, Spring Modulith docs | Low |

**Warning signs that modularity is decaying:** a `shared/` or `utils/` folder that keeps growing; a single PR regularly touching 3+ modules; "just this once" SQL joins across schemas; modules that cannot be tested without starting the others.

**Assistant's takeaway:** a modular monolith stays modular only if the boundaries are **checked automatically in CI** (architecture tests + build units + schema ownership). Conventions alone will erode. With that in place, any module can be extracted to a service later by replacing the in-process facade with an HTTP/gRPC client and the in-process events with a broker.

---

### 5. Decision and end of Task 1

**Assistant:** Asked for clarification on "let's go with that option" (offered: A–chatbot design, A–reminder scheduler, deeper on B, deeper on C).

**Student:** Choose **A (Modular Monolith)** and move on to Task 2.

**Outcome of Task 1:**
- Chosen architecture: **A – Modular Monolith** (stateless app, Postgres schema per module, background worker for reminders, chatbot behind a facade, CDN/Redis caching, module boundaries enforced in CI).
- Rejected: **B – Microservices** (too much operational and distributed-data complexity for 14 user stories / a small team); **C – Serverless/BaaS** (vendor lock-in, per-request cost growth, hard-to-test security rules, LLM timeouts).
- Topics not explored in depth (possible follow-up ADRs): chatbot design, reminder scheduler, concrete tech stack.

*End of Task 1 record. The discussion continues in `Week_05_Designing/Task_2/Task_2_conversation.md`.*
