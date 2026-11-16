from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


TASK_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_STORE_PATH = TASK_DIRECTORY.parent / "Task_3" / "chunk_embeddings.json"
TOKEN_PATTERN = re.compile(r"[a-z]+|[0-9]+")
REQUIRED_CHUNK_FIELDS = (
    "chunk_id",
    "source_file",
    "start_line",
    "end_line",
    "content",
    "embedding",
)


def tokenize(text: str) -> list[str]:
    """Split identifiers using the same tokenization as Task 3."""
    split_camel_case = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return TOKEN_PATTERN.findall(split_camel_case.replace("_", " ").lower())


def embed_query(query: str, store: dict[str, Any]) -> list[float]:
    """Build an L2-normalized TF-IDF vector using the Task 3 vocabulary and IDF."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")

    vocabulary = store.get("vocabulary")
    inverse_document_frequency = store.get("inverse_document_frequency")
    if not isinstance(vocabulary, list) or not isinstance(inverse_document_frequency, list):
        raise ValueError("Embedding store must include vocabulary and inverse_document_frequency")
    if len(vocabulary) != len(inverse_document_frequency):
        raise ValueError("Vocabulary and inverse-document-frequency sizes differ")

    term_indexes = {term: index for index, term in enumerate(vocabulary)}
    term_counts = Counter(tokenize(query))
    weighted_terms: dict[int, float] = {}
    for term, count in term_counts.items():
        index = term_indexes.get(term)
        if index is not None:
            weighted_terms[index] = (
                (1.0 + math.log(count)) * inverse_document_frequency[index]
            )

    magnitude = math.sqrt(math.fsum(weight * weight for weight in weighted_terms.values()))
    if magnitude == 0:
        raise ValueError("Query contains no terms from the embedding vocabulary")

    return [
        weighted_terms.get(index, 0.0) / magnitude
        for index in range(len(vocabulary))
    ]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity for two vectors of equal, non-zero length."""
    if len(left) != len(right):
        raise ValueError("Vectors must have the same number of dimensions")
    if not left:
        raise ValueError("Vectors must not be empty")

    left_magnitude = math.sqrt(math.fsum(value * value for value in left))
    right_magnitude = math.sqrt(math.fsum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        raise ValueError("Cosine similarity is undefined for a zero vector")

    dot_product = math.fsum(a * b for a, b in zip(left, right))
    return dot_product / (left_magnitude * right_magnitude)


def load_embedding_store(path: Path = DEFAULT_STORE_PATH) -> dict[str, Any]:
    """Read and validate the chunk embeddings created by Task 3."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Embedding store must be a JSON object")

    vocabulary = data.get("vocabulary")
    inverse_document_frequency = data.get("inverse_document_frequency")
    chunks = data.get("chunks")
    if not isinstance(vocabulary, list) or not isinstance(inverse_document_frequency, list):
        raise ValueError("Embedding store must include vocabulary and inverse_document_frequency")
    if len(vocabulary) != len(inverse_document_frequency):
        raise ValueError("Vocabulary and inverse-document-frequency sizes differ")
    if not all(isinstance(term, str) for term in vocabulary):
        raise ValueError("Embedding vocabulary must contain only strings")
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in inverse_document_frequency
    ):
        raise ValueError("Inverse document frequencies must be finite numbers")
    if not isinstance(chunks, list):
        raise ValueError("Embedding store must include a chunks list")

    seen_chunk_ids: set[str] = set()
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk at index {index} must be a JSON object")
        missing_fields = [field for field in REQUIRED_CHUNK_FIELDS if field not in chunk]
        if missing_fields:
            raise ValueError(
                f"Chunk at index {index} is missing required fields: "
                f"{', '.join(missing_fields)}"
            )
        if not isinstance(chunk["chunk_id"], str) or not chunk["chunk_id"]:
            raise ValueError(f"Chunk at index {index} has an invalid chunk_id")
        if chunk["chunk_id"] in seen_chunk_ids:
            raise ValueError(f"Duplicate chunk_id: {chunk['chunk_id']}")
        if not isinstance(chunk["source_file"], str) or not chunk["source_file"]:
            raise ValueError(f"Chunk {chunk['chunk_id']} has an invalid source_file")
        if (
            type(chunk["start_line"]) is not int
            or type(chunk["end_line"]) is not int
            or chunk["start_line"] < 1
            or chunk["end_line"] < chunk["start_line"]
        ):
            raise ValueError(f"Chunk {chunk['chunk_id']} has invalid line metadata")
        embedding = chunk["embedding"]
        if (
            not isinstance(embedding, list)
            or len(embedding) != len(vocabulary)
            or not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in embedding
            )
        ):
            raise ValueError(f"Chunk {chunk['chunk_id']} has an invalid embedding")
        seen_chunk_ids.add(chunk["chunk_id"])

    return data


def retrieve_chunks(
    query: str,
    store: dict[str, Any],
    n: int = 5,
) -> list[dict[str, Any]]:
    """Return the top n chunks, including their metadata and similarity scores."""
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")

    query_embedding = embed_query(query, store)
    scored_chunks = []
    for chunk in store["chunks"]:
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored_chunks.append({**chunk, "similarity_score": score})

    scored_chunks.sort(
        key=lambda chunk: (-chunk["similarity_score"], chunk["chunk_id"])
    )
    return scored_chunks[:n]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrieve repository chunks relevant to a textual query."
    )
    parser.add_argument("--query", required=True, help="Natural-language task or query")
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of chunks to return (default: 5)",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE_PATH,
        help=f"Task 3 embedding store (default: {DEFAULT_STORE_PATH})",
    )
    args = parser.parse_args()

    store = load_embedding_store(args.store)
    results = retrieve_chunks(args.query, store, args.top_n)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
