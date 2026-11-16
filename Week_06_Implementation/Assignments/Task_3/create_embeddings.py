from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


TASK_DIRECTORY = Path(__file__).resolve().parent
INPUT_PATH = TASK_DIRECTORY.parent / "Task_2" / "repository_chunks.json"
OUTPUT_PATH = TASK_DIRECTORY / "chunk_embeddings.json"
REQUIRED_FIELDS = ("chunk_id", "source_file", "start_line", "end_line", "content")
TOKEN_PATTERN = re.compile(r"[a-z]+|[0-9]+")


def tokenize(text: str) -> list[str]:
    """Split code identifiers into lowercase words and numeric tokens."""
    split_camel_case = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return TOKEN_PATTERN.findall(split_camel_case.replace("_", " ").lower())


def embed_text(
    text: str,
    vocabulary: Sequence[str],
    inverse_document_frequency: Sequence[float],
) -> list[float]:
    """Create an L2-normalized TF-IDF vector using a previously built vocabulary."""
    if len(vocabulary) != len(inverse_document_frequency):
        raise ValueError("Vocabulary and inverse-document-frequency sizes differ")

    term_indexes = {term: index for index, term in enumerate(vocabulary)}
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * len(vocabulary)

    term_counts = Counter(tokens)
    weighted_terms: dict[int, float] = {}
    for term, count in term_counts.items():
        index = term_indexes.get(term)
        if index is not None:
            weighted_terms[index] = (1.0 + math.log(count)) * inverse_document_frequency[index]

    magnitude = math.sqrt(sum(weight * weight for weight in weighted_terms.values()))
    if magnitude == 0:
        return [0.0] * len(vocabulary)

    return [
        weighted_terms.get(index, 0.0) / magnitude
        for index in range(len(vocabulary))
    ]


def validate_chunks(chunks: Any) -> list[dict[str, Any]]:
    if not isinstance(chunks, list):
        raise ValueError("Chunk input must be a JSON list")

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk at index {index} must be a JSON object")
        missing_fields = [field for field in REQUIRED_FIELDS if field not in chunk]
        if missing_fields:
            raise ValueError(
                f"Chunk at index {index} is missing required fields: "
                f"{', '.join(missing_fields)}"
            )
        if not isinstance(chunk["chunk_id"], str) or not chunk["chunk_id"]:
            raise ValueError(f"Chunk at index {index} has an invalid chunk_id")
        if chunk["chunk_id"] in seen_ids:
            raise ValueError(f"Duplicate chunk_id: {chunk['chunk_id']}")
        if not isinstance(chunk["source_file"], str) or not chunk["source_file"]:
            raise ValueError(f"Chunk {chunk['chunk_id']} has an invalid source_file")
        if not isinstance(chunk["content"], str):
            raise ValueError(f"Chunk {chunk['chunk_id']} has non-text content")
        if (
            type(chunk["start_line"]) is not int
            or type(chunk["end_line"]) is not int
            or chunk["start_line"] < 1
            or chunk["end_line"] < chunk["start_line"]
        ):
            raise ValueError(f"Chunk {chunk['chunk_id']} has invalid line metadata")

        seen_ids.add(chunk["chunk_id"])
        validated.append(chunk)

    return validated


def build_embedding_store(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    document_tokens = [tokenize(chunk["content"]) for chunk in chunks]
    vocabulary = sorted({term for terms in document_tokens for term in terms})
    document_frequency = Counter(
        term for terms in document_tokens for term in set(terms)
    )
    document_count = len(chunks)
    inverse_document_frequency = [
        math.log((document_count + 1) / (document_frequency[term] + 1)) + 1
        for term in vocabulary
    ]

    embedded_chunks = []
    for chunk in chunks:
        embedded_chunks.append(
            {
                **chunk,
                "embedding": embed_text(
                    chunk["content"], vocabulary, inverse_document_frequency
                ),
            }
        )

    return {
        "embedding_method": "sublinear TF-IDF with L2 normalization",
        "vocabulary": vocabulary,
        "inverse_document_frequency": inverse_document_frequency,
        "chunks": embedded_chunks,
    }


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Task 2 chunk data not found: {INPUT_PATH}")

    chunks = validate_chunks(json.loads(INPUT_PATH.read_text(encoding="utf-8")))
    store = build_embedding_store(chunks)
    OUTPUT_PATH.write_text(
        json.dumps(store, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Embedded {len(chunks)} chunks at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
