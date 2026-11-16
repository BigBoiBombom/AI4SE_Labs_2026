from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "Task_1" / "AI4SE_Playground"
OUTPUT_PATH = Path(__file__).resolve().with_name("repository_chunks.json")
TARGET_CHARS = 1200


def iter_python_files(repo_root: Path):
    for path in sorted(repo_root.rglob("*.py")):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        yield path


def chunk_file(path: Path, target_chars: int = TARGET_CHARS):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    if not lines:
        return []

    chunks = []
    start_line = 1
    current_lines = []
    current_chars = 0

    for line_number, line in enumerate(lines, start=1):
        line_text = f"{line}\n"
        if current_lines and current_chars + len(line_text) > target_chars:
            chunks.append(
                {
                    "start_line": start_line,
                    "end_line": line_number - 1,
                    "content": "".join(current_lines).rstrip(),
                }
            )
            start_line = line_number
            current_lines = [line_text]
            current_chars = len(line_text)
        else:
            current_lines.append(line_text)
            current_chars += len(line_text)

    if current_lines:
        chunks.append(
            {
                "start_line": start_line,
                "end_line": len(lines),
                "content": "".join(current_lines).rstrip(),
            }
        )

    return chunks


def build_repository_chunks(repo_root: Path):
    chunks = []
    for path in iter_python_files(repo_root):
        relative_path = path.relative_to(repo_root).as_posix()
        file_chunks = chunk_file(path)
        for index, chunk in enumerate(file_chunks, start=1):
            chunks.append(
                {
                    "chunk_id": f"{relative_path}#{index}",
                    "source_file": relative_path,
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "content": chunk["content"],
                }
            )
    return chunks


def main():
    repo_root = REPO_ROOT
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository not found at {repo_root}")

    chunks = build_repository_chunks(repo_root)
    OUTPUT_PATH.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    print(f"Created {len(chunks)} chunks at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
