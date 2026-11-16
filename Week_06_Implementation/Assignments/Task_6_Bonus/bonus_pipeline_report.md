# Bonus Task 1: Repository-aware code-generation pipeline

## Recommendation

For completing missing methods in the cloned AI4SE_Playground repository, use a
language-aware, hybrid retrieval pipeline rather than relying on one embedding
search and a fixed number of chunks. Resolve the requested target precisely,
retrieve evidence from complementary indexes, assemble only the context that
fits the task, generate a scoped patch, and validate it before accepting it.
This is a design recommendation; it does not describe a new implementation or
evaluation.

## Retrieval: combine methods

Embedding matching is useful, but is not the best standalone strategy for
repository code. Semantic/vector search can find code that expresses a
behavior in different words, while lexical search such as BM25 is often better
for exact identifiers, error messages, literals, and domain terms. Symbol-aware
search should resolve named classes, methods, imports, and references directly.
Structural navigation through a code graph can then follow calls, inheritance,
and imports to understand how a target participates in the program.

Use these methods together: resolve explicit file/class/method names first;
use BM25 and vector search to find textual and behavioral matches; and use
symbol relationships to expand promising results to definitions, callers,
tests, and relevant neighboring files. Rerank the combined candidates using
target overlap, query relevance, symbol relationships, and test relevance.
This reduces dependence on any single retrieval signal and puts behavior
contracts near the code they describe.

## Adaptive context and code-aware chunks

Do not treat a fixed top-*k* as universally optimal. Start from the task's
explicit target and complexity, then add high-relevance, non-redundant context
until the token budget is reached or additional results no longer help. Favor
diverse evidence (implementation, callers, tests, and dependencies) over
several near-duplicate excerpts. Preserve dependencies by retrieving a symbol
with its signature, docstring, imports or necessary class/module context, and
by linking excerpts to their parent module and related symbols. A starting
range such as 5–10 candidates before reranking can be evaluated on the
assignment's missing-method tasks; it is not a universal optimum or a measured
result.

Prefer language-aware units—functions, methods, classes, modules, and tests—
over arbitrary character windows. Split oversized units at syntax boundaries
and retain their shared parent and symbol metadata; use limited overlap only
where a split would otherwise separate a definition from essential logic.
Keep language boundaries explicit, linking (rather than merging) related
source, configuration, and test files. Record paths, line ranges, language,
symbol/type, signatures, imports, and links such as calls, tests, and
inheritance. Exclude irrelevant generated, vendored, binary, and environment
files. Smaller chunks improve precision but can lose necessary context; larger
chunks preserve relationships but add noise and consume more of the model's
context budget. Preserve links so either size can be assembled into coherent
context when needed.

## End-to-end workflow

1. **Index the repository.** Filter files, detect languages, parse source into
   symbols, and build lexical, vector, and relationship indexes. Refresh
   affected indexes after accepted changes.
2. **Understand the task.** Extract the requested file, class, method, expected
   behavior, constraints, and likely edge cases. Verify the target exists and
   inspect its surrounding class/module and existing tests.
3. **Retrieve and rerank.** Resolve target symbols, search exact terms and
   behavioral descriptions, follow useful code relationships, and rerank
   candidates for relevance and diversity.
4. **Assemble context.** Fit the target, necessary definitions, callers,
   tests, and related files into a token budget. Prefer compact excerpts with
   provenance over unrelated full files.
5. **Generate a constrained change.** Ask for a patch limited to the specified
   method and permitted files, preserving public signatures and project
   conventions. Require the model to identify assumptions or missing evidence
   rather than inventing APIs.
6. **Apply safely and validate.** Apply the patch in a working copy only after
   checking its paths and scope. Inspect the diff; run formatting and syntax or
   static checks, then focused tests, followed by the broader test suite.
   Reject or revise changes that escape scope or fail checks, and leave final
   review/acceptance to a person.

## Coursework baseline versus proposal

Tasks 2–4 implemented line-based chunks targeting roughly 1,200 characters,
sublinear TF-IDF vectors, and cosine-similarity retrieval. The chunk and
embedding files remain the pre-Task-5 snapshot used for the recorded generation
run; they were not refreshed after Task 5 changed the clone. Task 5 requested
five chunks and a method-body-only response. Its run record reports a successful
connectivity check and approved-model generation for all ten tasks. The
generated methods were validated and applied after the positive-on-hand
membership contract was resolved in the test. The Task 5 report and run record
report 481 passing tests in both staging and the actual clone.

The hybrid indexes, adaptive context selection, and code-graph expansion above
are recommendations only; they were not implemented or evaluated for this
assignment. The guarded apply workflow is implemented in the Task 5 runner.
No measurements for the proposed alternative retrieval approaches are claimed.
