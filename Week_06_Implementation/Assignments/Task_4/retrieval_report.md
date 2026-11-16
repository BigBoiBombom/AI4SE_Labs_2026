# Retrieval design

`retrieve_chunks.py` reads the chunk and embedding records produced by Task 3.
It embeds a textual query with Task 3's tokenizer, sorted vocabulary, sublinear
term-frequency formula, inverse-document-frequency weights, and L2
normalization. It does not create a new vocabulary or use an external model, so
the query and stored chunks occupy the same vector space.

The script ranks chunks by cosine similarity. This metric is appropriate for
the L2-normalized TF-IDF vectors because it compares their direction, and thus
the relative weighted terms, rather than favoring longer chunks by vector
magnitude. Each chunk's similarity is calculated against the query; results
are sorted from highest to lowest score and the first `n` are returned. Ties
are ordered by `chunk_id` to make output deterministic.

Every result retains its original chunk data, including `chunk_id`,
`source_file`, `start_line`, `end_line`, and `content`, and adds a
`similarity_score`. By default, the script reads Task 3's
`chunk_embeddings.json` and returns five results:

```text
python Week_06_Implementation\Assignments\Task_4\retrieve_chunks.py --query "Find the user authentication flow"
```

Use `--top-n` to change the number of results or `--store` to select another
compatible embedding-store file.

This is a lightweight lexical retrieval method, not semantic search. It may
miss relevant code when the query uses synonyms or concepts that do not share
tokens with the code, and it cannot infer behavior from context outside a
chunk. A query with no vocabulary terms in common with the Task 3 vocabulary is
reported as an error rather than returning an arbitrary ranking.
