# Task 4: detailed statistical comparison of the three prompting frameworks
# (RTF, ICIO, CoT) using both the Task 2 exact-match metric and the Task 3
# row-level F1/Jaccard metric. Reuses the schema/DB-loading logic from
# Task_2/data/evaluate_retrieval_predictions.py.
#
# Produces:
#   - combined_scores.csv            (per-question scores, all frameworks)
#   - descriptive_stats.txt          (means/medians/std for each metric)
#   - statistical_tests.txt          (Friedman, pairwise Wilcoxon, McNemar)
#   - accuracy_comparison.png        (bar chart: exact-match accuracy)
#   - f1_boxplot.png                 (box plot: per-question F1 distribution)
#   - f1_bar.png                     (bar chart: average F1/Jaccard/precision/recall)
#   - timing_vs_accuracy.png         (scatter: elapsed time vs accuracy)
#
# Usage: python analyze_frameworks.py

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict, deque
from pathlib import Path

import matplotlib.pyplot as plt
from scipy.stats import friedmanchisquare, wilcoxon, chi2

DATA_DIR = Path(__file__).resolve().parent
TASK2_DATA_DIR = DATA_DIR.parent.parent / "Task_2" / "data"
LABELS_PATH = TASK2_DATA_DIR / "restaurants_dataset.csv"
SCHEMA_PATH = TASK2_DATA_DIR / "restaurants-schema.csv"
DATABASE_PATH = TASK2_DATA_DIR / "restaurants-db.txt"
FRAMEWORKS = ["RTF", "ICIO", "CoT"]

TIMING = {
    "RTF": 288.854,
    "ICIO": 251.72,
    "CoT": 134.018295,
}


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
                    f"Invalid JSON label result on line {line_number} of {LABELS_PATH}"
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
                    "exact_match": 1 if f1 == 1.0 and expected_counter == predicted_counter else 0,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "jaccard": jaccard,
                }
            )
    return results


def build_combined_table(connection):
    per_framework = {}
    for framework in FRAMEWORKS:
        labels = load_labels()
        path = TASK2_DATA_DIR / f"restaurants_dataset_predictions_{framework}.csv"
        per_framework[framework] = evaluate_predictions(path, connection, labels)

    n = len(per_framework[FRAMEWORKS[0]])
    rows = []
    for i in range(n):
        row = {"question": per_framework[FRAMEWORKS[0]][i]["question"]}
        for framework in FRAMEWORKS:
            r = per_framework[framework][i]
            row[f"{framework}_exact_match"] = r["exact_match"]
            row[f"{framework}_f1"] = r["f1"]
            row[f"{framework}_jaccard"] = r["jaccard"]
            row[f"{framework}_precision"] = r["precision"]
            row[f"{framework}_recall"] = r["recall"]
        rows.append(row)
    return rows


def write_combined_csv(rows):
    out_path = DATA_DIR / "combined_scores.csv"
    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def mean(values):
    return sum(values) / len(values)


def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def stdev(values):
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def write_descriptive_stats(rows):
    lines = ["DESCRIPTIVE STATISTICS (n=155 questions per framework)", "=" * 55, ""]
    for framework in FRAMEWORKS:
        exact = [r[f"{framework}_exact_match"] for r in rows]
        f1 = [r[f"{framework}_f1"] for r in rows]
        jaccard = [r[f"{framework}_jaccard"] for r in rows]
        precision = [r[f"{framework}_precision"] for r in rows]
        recall = [r[f"{framework}_recall"] for r in rows]
        lines.append(f"{framework}:")
        lines.append(f"  Exact-match accuracy : {mean(exact):.4f} ({sum(exact)}/{len(exact)})")
        lines.append(f"  F1       mean={mean(f1):.4f}  median={median(f1):.4f}  sd={stdev(f1):.4f}")
        lines.append(f"  Jaccard  mean={mean(jaccard):.4f}  median={median(jaccard):.4f}  sd={stdev(jaccard):.4f}")
        lines.append(f"  Precision mean={mean(precision):.4f}  sd={stdev(precision):.4f}")
        lines.append(f"  Recall    mean={mean(recall):.4f}  sd={stdev(recall):.4f}")
        lines.append(f"  Elapsed time (s): {TIMING[framework]:.3f}")
        lines.append("")
    out_path = DATA_DIR / "descriptive_stats.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def mcnemar_test(a, b):
    """Exact-ish McNemar's test (chi-square approx with continuity correction)
    for two paired binary vectors a, b (same length)."""
    n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
    if n01 + n10 == 0:
        return 0.0, 1.0, n01, n10
    statistic = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    p_value = 1 - chi2.cdf(statistic, df=1)
    return statistic, p_value, n01, n10


def write_statistical_tests(rows):
    lines = ["STATISTICAL SIGNIFICANCE TESTS", "=" * 55, ""]

    # Friedman test across all three frameworks on F1 (paired, non-parametric
    # repeated-measures analogue of ANOVA; appropriate since all 3 frameworks
    # were evaluated on the identical 155 questions).
    f1_by_framework = [[r[f"{fw}_f1"] for r in rows] for fw in FRAMEWORKS]
    stat, p = friedmanchisquare(*f1_by_framework)
    lines.append("Friedman test across RTF/ICIO/CoT on per-question F1 scores:")
    lines.append(f"  chi-square={stat:.4f}, p-value={p:.6f}")
    lines.append(
        "  -> "
        + ("Significant difference among the three frameworks (p < 0.05)."
           if p < 0.05 else "No significant difference detected (p >= 0.05).")
    )
    lines.append("")

    # Pairwise Wilcoxon signed-rank tests on F1 (post-hoc), Bonferroni-corrected.
    lines.append("Pairwise Wilcoxon signed-rank tests on F1 (Bonferroni-corrected, m=3):")
    pairs = [("RTF", "ICIO"), ("RTF", "CoT"), ("ICIO", "CoT")]
    for a, b in pairs:
        fa = [r[f"{a}_f1"] for r in rows]
        fb = [r[f"{b}_f1"] for r in rows]
        diffs = [x - y for x, y in zip(fa, fb)]
        if all(d == 0 for d in diffs):
            lines.append(f"  {a} vs {b}: all differences are zero -> p=1.0000 (identical)")
            continue
        stat, p = wilcoxon(fa, fb)
        p_corrected = min(p * 3, 1.0)
        lines.append(
            f"  {a} vs {b}: W={stat:.4f}, p={p:.6f}, Bonferroni-corrected p={p_corrected:.6f} "
            f"-> {'significant' if p_corrected < 0.05 else 'not significant'}"
        )
    lines.append("")

    # Pairwise McNemar's tests on exact-match (binary) outcomes.
    lines.append("Pairwise McNemar's tests on exact-match accuracy (Bonferroni-corrected, m=3):")
    for a, b in pairs:
        ea = [r[f"{a}_exact_match"] for r in rows]
        eb = [r[f"{b}_exact_match"] for r in rows]
        stat, p, n01, n10 = mcnemar_test(ea, eb)
        p_corrected = min(p * 3, 1.0)
        lines.append(
            f"  {a} vs {b}: discordant pairs ({a}-wrong/{b}-right={n01}, "
            f"{a}-right/{b}-wrong={n10}), chi2={stat:.4f}, p={p:.6f}, "
            f"Bonferroni-corrected p={p_corrected:.6f} -> "
            f"{'significant' if p_corrected < 0.05 else 'not significant'}"
        )
    lines.append("")

    out_path = DATA_DIR / "statistical_tests.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def make_plots(rows):
    colors = {"RTF": "#4C72B0", "ICIO": "#DD8452", "CoT": "#55A868"}

    # 1. Exact-match accuracy bar chart
    accuracies = [mean([r[f"{fw}_exact_match"] for r in rows]) for fw in FRAMEWORKS]
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(FRAMEWORKS, accuracies, color=[colors[fw] for fw in FRAMEWORKS])
    ax.set_ylabel("Exact-match accuracy")
    ax.set_title("Task 2 metric: exact-match accuracy by framework")
    ax.set_ylim(0, 1)
    for bar, value in zip(bars, accuracies):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2%}", ha="center")
    fig.tight_layout()
    fig.savefig(DATA_DIR / "accuracy_comparison.png", dpi=150)
    plt.close(fig)

    # 2. F1 boxplot
    f1_data = [[r[f"{fw}_f1"] for r in rows] for fw in FRAMEWORKS]
    fig, ax = plt.subplots(figsize=(5, 4))
    bp = ax.boxplot(f1_data, labels=FRAMEWORKS, patch_artist=True)
    for patch, fw in zip(bp["boxes"], FRAMEWORKS):
        patch.set_facecolor(colors[fw])
    ax.set_ylabel("Per-question F1 score")
    ax.set_title("Task 3 metric: F1 distribution by framework")
    fig.tight_layout()
    fig.savefig(DATA_DIR / "f1_boxplot.png", dpi=150)
    plt.close(fig)

    # 3. Average F1/Jaccard/Precision/Recall grouped bar chart
    metrics = ["f1", "jaccard", "precision", "recall"]
    metric_labels = ["F1", "Jaccard", "Precision", "Recall"]
    x = range(len(metrics))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, fw in enumerate(FRAMEWORKS):
        values = [mean([r[f"{fw}_{m}"] for r in rows]) for m in metrics]
        ax.bar([xi + (i - 1) * width for xi in x], values, width, label=fw, color=colors[fw])
    ax.set_xticks(list(x))
    ax.set_xticklabels(metric_labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Average score")
    ax.set_title("Task 3 metric: average row-level scores by framework")
    ax.legend()
    fig.tight_layout()
    fig.savefig(DATA_DIR / "f1_bar.png", dpi=150)
    plt.close(fig)

    # 4. Timing vs accuracy scatter
    fig, ax = plt.subplots(figsize=(5, 4))
    for fw in FRAMEWORKS:
        acc = mean([r[f"{fw}_exact_match"] for r in rows])
        ax.scatter(TIMING[fw], acc, s=120, color=colors[fw], label=fw)
        ax.annotate(fw, (TIMING[fw], acc), textcoords="offset points", xytext=(8, 4))
    ax.set_xlabel("Total elapsed time (s)")
    ax.set_ylabel("Exact-match accuracy")
    ax.set_title("Accuracy vs. elapsed time")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(DATA_DIR / "timing_vs_accuracy.png", dpi=150)
    plt.close(fig)


def main():
    connection = load_database()
    try:
        rows = build_combined_table(connection)
    finally:
        connection.close()

    csv_path = write_combined_csv(rows)
    stats_path = write_descriptive_stats(rows)
    tests_path = write_statistical_tests(rows)
    make_plots(rows)

    print(f"Wrote {csv_path}")
    print(f"Wrote {stats_path}")
    print(f"Wrote {tests_path}")
    print("Wrote accuracy_comparison.png, f1_boxplot.png, f1_bar.png, timing_vs_accuracy.png")


if __name__ == "__main__":
    main()
