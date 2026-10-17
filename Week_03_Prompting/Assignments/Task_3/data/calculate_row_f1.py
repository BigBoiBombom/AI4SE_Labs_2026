# Calculates row-level F1 / Jaccard similarity between predicted and expected
# result rows for each question in a predictions CSV, as a partial-credit
# complement to the strict exact-match accuracy used by
# evaluate_retrieval_predictions.py (Task 2).
#
# Unlike exact match (which scores a question 0 or 1), this script treats the
# expected and predicted rows as multisets and scores each question by how
# much they overlap:
#   precision = |predicted ∩ expected| / |predicted|
#   recall    = |predicted ∩ expected| / |expected|
#   F1        = harmonic mean of precision and recall
#   Jaccard   = |predicted ∩ expected| / |predicted ∪ expected|
#
# Edge cases:
#   - both predicted and expected are empty -> perfect score (1.0)
#   - predicted SQL fails to execute -> score 0.0 for that question (the run
#     continues; unlike the strict evaluator this script never aborts)
#
# Usage:
#   python calculate_row_f1.py <predictions_csv> [<predictions_csv> ...]
#
# Reuses the schema/database loading logic from
# Task_2/data/evaluate_retrieval_predictions.py.

import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
TASK2_DATA_DIR = DATA_DIR.parent.parent / "Task_2" / "data"
LABELS_PATH = TASK2_DATA_DIR / "restaurants_dataset.csv"
SCHEMA_PATH = TASK2_DATA_DIR / "restaurants-schema.csv"
DATABASE_PATH = TASK2_DATA_DIR / "restaurants-db.txt"


def sqlite_type(schema_type):
    normalized_type = schema_type.strip().lower()
    if normalized_type.startswith("int"):
        return "INTEGER"
    if normalized_type.startswith("decimal") or normalized_type.startswith("float"):
        return "REAL"
    return "TEXT"


def load_database():
    tables = {}
    with SCHEMA_PATH.open(encoding="utf-8", newline="") as schema_file:
        for table, field, primary_key, _foreign_key, column_type in csv.reader(
            schema_file, skipinitialspace=True
        ):
            table = table.strip()
            field = field.strip()
            if table == "-":
                continue
            tables.setdefault(table, []).append(
                (field, sqlite_type(column_type), primary_key.strip().lower() == "y")
            )

    connection = sqlite3.connect(":memory:")
    for table, columns in tables.items():
        definitions = []
        for field, column_type, primary_key in columns:
            definition = f'"{field}" {column_type}'
            if primary_key:
                definition += " PRIMARY KEY"
            definitions.append(definition)
        connection.execute(f'CREATE TABLE "{table}" ({", ".join(definitions)})')

    with DATABASE_PATH.open(encoding="utf-8") as database_file:
        for line_number, line in enumerate(database_file, start=1):
            match = re.fullmatch(r"([A-Z_]+)\((.*)\)", line.rstrip("\r\n"))
            if match is None:
                raise ValueError(f"Invalid database record on line {line_number}")

            table, values_text = match.groups()
            if table not in tables:
                raise ValueError(f"Unknown table {table!r} on line {line_number}")

            values = next(csv.reader([values_text], skipinitialspace=True))
            columns = tables[table]
            if len(values) != len(columns):
                raise ValueError(
                    f"Expected {len(columns)} values for {table} on line "
                    f"{line_number}, got {len(values)}"
                )

            converted_values = []
            for value, (_field, column_type, _primary_key) in zip(values, columns):
                if column_type == "INTEGER":
                    converted_values.append(int(value))
                elif column_type == "REAL":
                    converted_values.append(float(value))
                else:
                    converted_values.append(value)

            placeholders = ", ".join("?" for _ in columns)
            connection.execute(
                f'INSERT INTO "{table}" VALUES ({placeholders})', converted_values
            )

    return connection


def row_multiset(rows):
    return Counter(tuple(row) for row in rows)


def row_level_scores(predicted_counter, expected_counter):
    """Precision/recall/F1/Jaccard between two row multisets."""
    overlap = sum((predicted_counter & expected_counter).values())
    predicted_total = sum(predicted_counter.values())
    expected_total = sum(expected_counter.values())
    union_total = sum((predicted_counter | expected_counter).values())

    if predicted_total == 0 and expected_total == 0:
        return 1.0, 1.0, 1.0, 1.0

    precision = overlap / predicted_total if predicted_total else 0.0
    recall = overlap / expected_total if expected_total else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    jaccard = overlap / union_total if union_total else 0.0
    return precision, recall, f1, jaccard


def load_labels():
    csv.field_size_limit(1_000_000_000)
    labels_by_question = defaultdict(deque)
    with LABELS_PATH.open(encoding="utf-8", newline="") as source:
        for line_number, row in enumerate(csv.DictReader(source), start=2):
            try:
                result = json.loads(row["result"])
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON label result on line {line_number} "
                    f"of {LABELS_PATH}"
                ) from error
            if not isinstance(result, list):
                raise ValueError(
                    f"Expected a JSON array label result on line {line_number} "
                    f"of {LABELS_PATH}"
                )
            labels_by_question[row["question"]].append(result)
    return labels_by_question


def evaluate_predictions(predictions_path, connection, labels_by_question):
    csv.field_size_limit(1_000_000_000)
    results = []
    with predictions_path.open(encoding="utf-8", newline="") as source:
        for line_number, row in enumerate(csv.DictReader(source), start=2):
            question = row["question"]
            if not labels_by_question[question]:
                raise ValueError(
                    f"No matching label question for prediction on line "
                    f"{line_number}: {question!r}"
                )
            expected_rows = labels_by_question[question].popleft()
            expected_counter = row_multiset(expected_rows)

            try:
                predicted_rows = connection.execute(row["predicted_sql"]).fetchall()
                predicted_counter = row_multiset(predicted_rows)
            except sqlite3.Error:
                predicted_counter = Counter()

            precision, recall, f1, jaccard = row_level_scores(
                predicted_counter, expected_counter
            )
            results.append(
                {
                    "question": question,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "jaccard": jaccard,
                }
            )
    return results


def summarize(framework_name, results):
    count = len(results)
    avg_precision = sum(r["precision"] for r in results) / count
    avg_recall = sum(r["recall"] for r in results) / count
    avg_f1 = sum(r["f1"] for r in results) / count
    avg_jaccard = sum(r["jaccard"] for r in results) / count
    exact_matches = sum(1 for r in results if r["f1"] == 1.0)
    zero_overlap = sum(1 for r in results if r["f1"] == 0.0)
    return {
        "framework": framework_name,
        "questions": count,
        "avg_precision": avg_precision,
        "avg_recall": avg_recall,
        "avg_f1": avg_f1,
        "avg_jaccard": avg_jaccard,
        "exact_matches": exact_matches,
        "zero_overlap": zero_overlap,
    }


def main():
    predictions_paths = [Path(arg) for arg in sys.argv[1:]]
    if not predictions_paths:
        predictions_paths = sorted(TASK2_DATA_DIR.glob("restaurants_dataset_predictions_*.csv"))

    if not predictions_paths:
        raise ValueError("No predictions CSV files found or provided")

    labels_by_question = load_labels()
    connection = load_database()
    try:
        for predictions_path in predictions_paths:
            # Reload labels per file so each framework is scored against the
            # full, unconsumed label set (labels are consumed via deque).
            local_labels = load_labels()
            results = evaluate_predictions(predictions_path, connection, local_labels)
            framework_name = predictions_path.stem.rsplit("_", 1)[-1]
            summary = summarize(framework_name, results)
            print(
                f"{summary['framework']}: "
                f"avg_F1={summary['avg_f1']:.4f}, "
                f"avg_Jaccard={summary['avg_jaccard']:.4f}, "
                f"avg_precision={summary['avg_precision']:.4f}, "
                f"avg_recall={summary['avg_recall']:.4f}, "
                f"perfect_rows={summary['exact_matches']}/{summary['questions']}, "
                f"zero_overlap={summary['zero_overlap']}/{summary['questions']}"
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
