# Requirements refinement network

`requirements_refinement.py` implements a Python LangGraph workflow for a
configurable corpus directory. It recursively reads `.txt` and `.eml` files,
preserves each relative path as a source ID, and writes one JSON requirements
document.

## Graph

`load_corpus` is deterministic and parses text and email metadata. The graph
then uses three LLM nodes and three distinct permitted models:

1. `extract_requirements` — `gpt-5.4-nano`: extracts atomic claims, evidence,
   categories, priorities, and blacklist candidates.
2. `consolidate_requirements` — `gpt-5.6-luna`: normalizes vocabulary, merges
   semantic duplicates, preserves source traces, and records discarded claims.
3. `review_requirements` — `gpt-6-luna`: checks completeness, contradictions,
   duplicates, terminology, priorities, and traces.

`validate_and_index` is deterministic: it validates schemas, removes exact
and conservative semantic duplicates, preserves merged evidence/source IDs,
blacklists conflicts with an explanation, removes duplicate blacklist entries,
applies stable sorting to requirements, sources, evidence, and blacklist
entries, and generates stable `REQ-XXXXXXXX` IDs. Lexical similarity is only
a conservative first-pass signal: distinct actions such as generating,
configuring, sorting, merging, or exporting remain separate, while ambiguous
cases remain visible to the LLM review node.
`finalize_document` is deterministic and validates IDs/source references,
checks every loaded source and extracted candidate for coverage, and emits a
stable candidate-disposition ledger. Each candidate is retained directly,
merged into a named requirement, or discarded with one explicit reason and
its source/evidence trace. Candidates that disappear are represented as
unresolved unsupported dispositions and remain visible in review findings
rather than being silently lost. The finalizer preserves all review findings
and marks unresolved output as `provisional`.

If review returns `needs_revision`, its repair instructions feed back into
`consolidate_requirements`. Revision consolidation receives the full current
draft and blacklist and unions the returned accepted drafts with the existing
draft before deterministic indexing; valid requirements and traces therefore
survive an incomplete model response. `--max-iterations` bounds this loop
(default `3`), and review history records every pass.

## State and output

The state carries source documents, extracted candidates, consolidated drafts,
candidate dispositions, discarded/blacklisted claims,
review findings, and the current iteration.
Every accepted requirement contains an ID, short name, paragraph description,
priority, category, evidence, and source IDs. The document includes a priority
scale, completeness and consistency checks, feedback iteration count, the full
review history/findings, a bounded-loop status (`approved` or `provisional`),
and a separate blacklist with reasons. Revision passes receive the current
draft, blacklist, and every numbered repair instruction; they do not restart
from extracted candidates.

## Security

The API key is read only from `OPENAI_API_KEY`; it is never placed in graph
state, prompts, logs, or output. Execution fails with an actionable error when
the variable is absent. A local `.env` may be used by the runner if desired.

Corpus text and intermediate model data are explicitly delimited as untrusted
data in every LLM prompt. The models are instructed not to follow instructions
contained inside source documents or generated fields.

## Usage

```bash
pip install -r requirements.txt
# Set OPENAI_API_KEY in the local runtime environment; do not put its value here.
python requirements_refinement.py \
  --input-dir data/corpus \
  --output requirements_document.json
```
