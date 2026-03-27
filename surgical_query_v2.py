# ver 20260327014422.0
import argparse
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def log_message(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}")

def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def slugify_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"^chat_", "", value)
    value = re.sub(r"\.md$", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value

def split_frontmatter_and_body(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[0] + "\n---", parts[1].lstrip()
    return "", text

def extract_title(path: Path, text: str) -> str:
    frontmatter, body = split_frontmatter_and_body(text)

    m = re.search(r'^title:\s*"?(.*?)"?\s*$', frontmatter, re.MULTILINE)
    if m:
        return normalize_text(m.group(1))

    for line in body.splitlines():
        if line.startswith("# "):
            return normalize_text(line[2:])

    return path.stem

def extract_tags(frontmatter: str) -> list[str]:
    m = re.search(r"^tags:\s*\[(.*?)\]\s*$", frontmatter, re.MULTILINE)
    if not m:
        return []
    raw = m.group(1)
    return [normalize_text(tag.strip().strip('"').strip("'")) for tag in raw.split(",") if normalize_text(tag)]

def count_query_hits(text: str, query_terms: list[str]) -> tuple[int, dict[str, int]]:
    lowered = text.lower()
    counts = {}
    score = 0

    for term in query_terms:
        t = term.lower()
        hits = lowered.count(t)
        counts[term] = hits
        if hits > 0:
            if " " in t:
                score += hits * 6
            else:
                score += hits * 2

    return score, counts

def first_matching_lines(text: str, query_terms: list[str], limit: int = 8) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        lowered = line.lower()
        if any(term.lower() in lowered for term in query_terms):
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines

def resolve_base_dir(explicit_base: str | None) -> Path:
    candidates = []

    if explicit_base:
        candidates.append(Path(explicit_base))

    candidates.extend([
        Path.cwd(),
        Path("/storage/emulated/0/Documents/NexusVault"),
    ])

    for candidate in candidates:
        if (candidate / "03_Concepts").is_dir() and (candidate / "04_Code").is_dir():
            return candidate

    raise FileNotFoundError("Could not resolve a NexusVault base directory containing 03_Concepts and 04_Code")

def resolve_notebookvault_dir(base_dir: Path, explicit_notebook_dir: str | None) -> Path:
    candidates = []

    if explicit_notebook_dir:
        candidates.append(Path(explicit_notebook_dir))

    candidates.extend([
        base_dir / "NotebookVault",
        Path("/storage/emulated/0/Documents/NotebookVault"),
    ])

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError("Could not resolve a NotebookVault directory")

def build_concept_index(concepts_dir: Path) -> dict[str, list[Path]]:
    index = defaultdict(list)
    for path in sorted(concepts_dir.glob("*.md")):
        key = slugify_title(path.stem)
        index[key].append(path)
    return index

def parse_linked_code_files(concept_body: str) -> list[str]:
    return re.findall(r"\[\[(.*?\.[A-Za-z0-9]+)\]\]", concept_body)

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def generate_context_pack(
    query_terms: list[str],
    base_dir: Path,
    notebook_dir: Path,
    limit: int,
    copy_to_clipboard: bool,
) -> Path:
    concepts_dir = base_dir / "03_Concepts"
    code_dir = base_dir / "04_Code"

    concept_index = build_concept_index(concepts_dir)
    notebook_hits = []

    log_message(f"Base directory: {base_dir}")
    log_message(f"NotebookVault directory: {notebook_dir}")
    log_message(f"Searching for: {', '.join(query_terms)}")

    for path in sorted(notebook_dir.glob("*.md")):
        text = read_text_file(path)
        frontmatter, body = split_frontmatter_and_body(text)
        title = extract_title(path, text)
        tags = extract_tags(frontmatter)

        title_score, title_counts = count_query_hits(title, query_terms)
        tags_score, tag_counts = count_query_hits(" ".join(tags), query_terms)
        body_score, body_counts = count_query_hits(body, query_terms)

        score = (title_score * 4) + (tags_score * 3) + body_score

        if score <= 0:
            continue

        normalized_key = slugify_title(title)
        concept_paths = concept_index.get(normalized_key, [])

        notebook_hits.append({
            "path": path,
            "title": title,
            "text": text,
            "frontmatter": frontmatter,
            "body": body,
            "tags": tags,
            "score": score,
            "counts": {
                "title": title_counts,
                "tags": tag_counts,
                "body": body_counts,
            },
            "matching_lines": first_matching_lines(body, query_terms, limit=8),
            "concept_paths": concept_paths,
        })

    notebook_hits.sort(key=lambda item: (-item["score"], item["title"].lower()))
    notebook_hits = notebook_hits[:limit]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = base_dir / f"Context_Pack_{ts}.md"

    with output_file.open("w", encoding="utf-8") as pack:
        pack.write("---\n")
        pack.write("type: context-pack\n")
        pack.write(f"generated: {datetime.now().isoformat()}\n")
        pack.write(f"query_terms: [{', '.join(query_terms)}]\n")
        pack.write(f"base_dir: {base_dir}\n")
        pack.write(f"notebookvault_dir: {notebook_dir}\n")
        pack.write(f"result_count: {len(notebook_hits)}\n")
        pack.write("---\n\n")

        pack.write("# Surgical Context Pack\n\n")
        pack.write(f"Generated: `{datetime.now().isoformat()}`\n\n")
        pack.write(f"Query Terms: `{', '.join(query_terms)}`\n\n")
        pack.write(f"NotebookVault Searched: `{notebook_dir}`\n\n")
        pack.write(f"Concept Layer Searched: `{concepts_dir}`\n\n")
        pack.write(f"Code Layer Searched: `{code_dir}`\n\n")
        pack.write("---\n\n")

        if not notebook_hits:
            pack.write("No NotebookVault matches found.\n")
        else:
            for i, hit in enumerate(notebook_hits, start=1):
                pack.write(f"## {i:02d}. {hit['title']}\n\n")
                pack.write(f"- Notebook source: `{hit['path']}`\n")
                pack.write(f"- Score: `{hit['score']}`\n")
                pack.write(f"- Tags: `{', '.join(hit['tags']) if hit['tags'] else ''}`\n")
                pack.write(f"- Matching lines found: `{len(hit['matching_lines'])}`\n")
                pack.write("\n")

                pack.write("### Match Signals\n\n")
                pack.write(f"- Title hits: `{hit['counts']['title']}`\n")
                pack.write(f"- Tag hits: `{hit['counts']['tags']}`\n")
                pack.write(f"- Body hits: `{hit['counts']['body']}`\n\n")

                if hit["matching_lines"]:
                    pack.write("### Matching Lines\n\n")
                    for line in hit["matching_lines"]:
                        pack.write(f"- {line}\n")
                    pack.write("\n")

                pack.write("### Notebook Source Body\n\n")
                pack.write(hit["text"])
                if not hit["text"].endswith("\n"):
                    pack.write("\n")
                pack.write("\n")

                if hit["concept_paths"]:
                    pack.write("### Matching Concept Notes\n\n")
                    for concept_path in hit["concept_paths"]:
                        concept_text = read_text_file(concept_path)
                        concept_frontmatter, concept_body = split_frontmatter_and_body(concept_text)

                        pack.write(f"#### Concept Note: `{concept_path.name}`\n\n")
                        pack.write(concept_text)
                        if not concept_text.endswith("\n"):
                            pack.write("\n")
                        pack.write("\n")

                        linked_files = parse_linked_code_files(concept_body)
                        if linked_files:
                            pack.write("#### Linked Code Assets\n\n")
                            for code_fn in linked_files:
                                code_path = code_dir / code_fn
                                pack.write(f"##### {code_fn}\n\n")
                                if code_path.exists():
                                    lang = code_path.suffix.lstrip(".") or "txt"
                                    code_text = read_text_file(code_path)
                                    pack.write(f"```{lang}\n")
                                    pack.write(code_text)
                                    if not code_text.endswith("\n"):
                                        pack.write("\n")
                                    pack.write("```\n\n")
                                else:
                                    pack.write(f"`MISSING: {code_path}`\n\n")

                pack.write("---\n\n")

    if copy_to_clipboard:
        try:
            subprocess.run(
                ["termux-clipboard-set"],
                input=str(output_file),
                text=True,
                check=True,
            )
            log_message(f"Copied output path to clipboard: {output_file}")
        except Exception as e:
            log_message(f"Clipboard copy failed: {e}")

    log_message(f"Context Pack created: {output_file}")
    return output_file

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search NotebookVault first, then enrich with Concept notes and linked code from 04_Code."
    )
    parser.add_argument(
        "keywords",
        nargs="+",
        help="Keywords or quoted phrases to search for."
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Override NexusVault base directory."
    )
    parser.add_argument(
        "--notebook-dir",
        default="",
        help="Override NotebookVault directory."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Maximum number of NotebookVault matches to include."
    )
    parser.add_argument(
        "--copy-path",
        action="store_true",
        help="Copy the output path to clipboard using termux-clipboard-set."
    )
    args = parser.parse_args()

    base_dir = resolve_base_dir(args.base_dir or None)
    notebook_dir = resolve_notebookvault_dir(base_dir, args.notebook_dir or None)

    generate_context_pack(
        query_terms=args.keywords,
        base_dir=base_dir,
        notebook_dir=notebook_dir,
        limit=args.limit,
        copy_to_clipboard=args.copy_path,
    )

if __name__ == "__main__":
    main()

# Version History Log
# 20260327014422.0 - Initial hybrid surgical query script that searches NotebookVault first, enriches with matching Concept notes, and inlines linked 04_Code assets into a read-only context pack.
