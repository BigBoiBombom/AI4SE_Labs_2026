# Embedding and storage design

The script reads the JSON chunk list produced by Task 2 and builds a deterministic TF-IDF vector for each chunk. Tokenization lowercases text, splits snake_case and camelCase identifiers, and retains alphabetic words and numeric tokens. The term frequency uses `1 + ln(count)`, while inverse document frequency uses `ln((number of chunks + 1) / (document frequency + 1)) + 1`. Each vector is then L2-normalized.

TF-IDF is an appropriate teaching-level choice for this small code repository: it uses only Python's standard library, is repeatable, and gives less weight to terms found in many chunks while retaining distinctive code identifiers. Unlike a learned language model, it needs no downloads, credentials, or external services. Its limitation is that it captures shared words rather than semantic meaning, so synonyms and conceptually related code with different names may not match well.

The output, `chunk_embeddings.json`, stores all chunk metadata and content beside its numeric embedding. A shared, sorted vocabulary and aligned inverse-document-frequency values define what each vector coordinate means. This keeps the vectors directly comparable and allows a later task to embed a query with the same vocabulary and calculate cosine similarity (the stored chunk vectors are already L2-normalized). The vectors are dense and therefore repeat zero values, but the repository has only 149 chunks and a modest vocabulary; this simple JSON representation is easy to inspect and sufficient for the assignment.

To reproduce the output, run:

```powershell
python Week_06_Implementation/Assignments/Task_3/create_embeddings.py
```
