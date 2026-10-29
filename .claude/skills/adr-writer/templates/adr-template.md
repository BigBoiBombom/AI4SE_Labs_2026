# ADR-<NNN>: <Decision title, e.g. "Use a Modular Monolith Architecture for X">

| | |
|---|---|
| **Status** | Proposed / Accepted / Superseded by ADR-<NNN> |
| **Date** | <YYYY-MM-DD> |
| **Deciders** | <names / roles> |
| **Source discussion** | [discussion record](<relative path>) |
| **Requirements** | [<file>](<relative path>) |

---

## 1. Context

<2–4 sentences: what the system is and its main goal.>

**Functional scope (<n> user stories):**
- **<Actor>:** <capability> (US1), ...
- **<Actor>:** ...

**Assumptions:**
- <team size, traffic, read/write ratio>
- <data source, external services, how notifications and AI features work>

## 2. Decision Drivers

1. <most important driver>
2. ...

## 3. Considered Options

| | Option | Short description |
|---|---|---|
| **A** | **<chosen option>** | <one line> |
| B | <option> | <one line> |
| C | <option> | <one line> |

### Comparison (1 = worst, 5 = best for <system>)

| Metric | A | B | C |
|---|---|---|---|
| Initial development effort | | | |
| Time to market | | | |
| Operational burden | | | |
| Infra cost at low traffic | | | |
| Cost predictability at high scale | | | |
| Independent scalability | | | |
| Fault isolation | | | |
| Data consistency / integrity | | | |
| Testability & local development | | | |
| Vendor independence | | | |
| Fit for team size | | | |
| Evolvability | | | |
| **Total** | | | |

## 4. Decision

**We choose Option A – <name>**, with the following binding rules:

1. **<Rule>.** <checkable statement>
   *Rejected alternative:* <alternative> – <one-line reason>.
2. ...

### Architecture overview

```
<ASCII diagram: clients, components, data stores, external systems, async paths>
```

### User story → component mapping

| User stories | Component |
|---|---|
| US1, ... | <component> |

## 5. Consequences

### Positive
- ...

### Negative
- ...

## 6. When to Revisit This Decision

Re-evaluate if any of these happens:
- <measurable trigger, e.g. p95 latency > X ms, team > N teams, cost > $Y/month>

## 7. Follow-up Decisions

- **ADR-<NNN+1>:** <topic>

## 8. Revision History

| Version | Date | Change |
|---|---|---|
| v1 | <YYYY-MM-DD> | Initial version generated from the architecture discussion. |
