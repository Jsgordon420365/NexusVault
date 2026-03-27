# ver 20260327053218.2
import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def log_message(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def safe_slug(value: str, max_len: int = 48) -> str:
    value = normalize_whitespace(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        value = "untitled"
    return value[:max_len].strip("-") or "untitled"


def yaml_escape(value: str) -> str:
    return value.replace('"', '\\"')


def csv_escape_pipe_join(values: List[str]) -> str:
    return " | ".join(values)


def dedupe_terms(values: List[str]) -> List[str]:
    result = []
    seen = set()
    for raw in values:
        value = normalize_whitespace(raw)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def merge_terms(required_terms: List[str], boost_terms: List[str]) -> List[str]:
    return dedupe_terms(required_terms + boost_terms)


def extract_message_text(msg: dict) -> str:
    text = msg.get("text", "")
    if isinstance(text, str):
        return text
    if text is None:
        return ""
    return str(text)


def role_label(sender: str) -> str:
    sender = (sender or "").strip().lower()
    if sender == "user":
        return "HUMAN"
    if sender == "assistant":
        return "ASSISTANT"
    if sender == "system":
        return "SYSTEM"
    if sender == "tool":
        return "TOOL"
    return sender.upper() if sender else "UNKNOWN"


def count_term_hits(text: str, terms: List[str]) -> Dict[str, int]:
    lowered = text.lower()
    counts = {}
    for term in terms:
        counts[term] = lowered.count(term.lower())
    return counts


def score_terms(
    title: str,
    summary: str,
    first_excerpt: str,
    last_excerpt: str,
    full_text: str,
    required_terms: List[str],
    boost_terms: List[str],
) -> Tuple[int, Dict[str, Dict[str, int]]]:
    all_terms = merge_terms(required_terms, boost_terms)

    title_hits = count_term_hits(title, all_terms)
    summary_hits = count_term_hits(summary, all_terms)
    first_hits = count_term_hits(first_excerpt, all_terms)
    last_hits = count_term_hits(last_excerpt, all_terms)
    full_hits = count_term_hits(full_text, all_terms)

    required_keys = {t.lower() for t in required_terms}
    score = 0

    for term in all_terms:
        phrase_mult = 6 if " " in term else 3
        role_mult = 2 if term.lower() in required_keys else 1
        score += title_hits[term] * phrase_mult * role_mult * 4
        score += summary_hits[term] * phrase_mult * role_mult * 3
        score += first_hits[term] * phrase_mult * role_mult * 2
        score += last_hits[term] * phrase_mult * role_mult * 1
        score += full_hits[term] * phrase_mult * role_mult

    detail = {
        "title": title_hits,
        "summary": summary_hits,
        "first_excerpt": first_hits,
        "last_excerpt": last_hits,
        "full_text": full_hits,
    }
    return score, detail


def total_hits_by_term(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> Dict[str, int]:
    totals = {}
    for term in terms:
        totals[term] = sum(score_detail[field].get(term, 0) for field in score_detail)
    return totals


def matched_terms_from_detail(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> List[str]:
    totals = total_hits_by_term(score_detail, terms)
    return [term for term in terms if totals.get(term, 0) > 0]


def required_term_gate_detail(
    score_detail: Dict[str, Dict[str, int]],
    required_terms: List[str],
    required_body_min_hits: int,
) -> Tuple[bool, Dict[str, dict], List[str], List[str], List[str]]:
    details = {}
    passed_terms = []
    strong_terms = []
    body_only_terms = []
    failed_terms = []

    for term in required_terms:
        strong_hits = (
            score_detail["title"].get(term, 0)
            + score_detail["summary"].get(term, 0)
            + score_detail["first_excerpt"].get(term, 0)
            + score_detail["last_excerpt"].get(term, 0)
        )
        body_hits = score_detail["full_text"].get(term, 0)

        if strong_hits > 0:
            mode = "strong"
            passed = True
            passed_terms.append(term)
            strong_terms.append(term)
        elif body_hits >= required_body_min_hits:
            mode = "body"
            passed = True
            passed_terms.append(term)
            body_only_terms.append(term)
        else:
            mode = "failed"
            passed = False
            failed_terms.append(term)

        details[term] = {
            "strong_hits": strong_hits,
            "body_hits": body_hits,
            "passed": passed,
            "mode": mode,
        }

    return len(failed_terms) == 0, details, passed_terms, strong_terms, body_only_terms


def passes_match_gate(matched_terms: List[str], all_terms: List[str], match_mode: str) -> bool:
    matched_count = len(matched_terms)
    total_terms = len(all_terms)

    if match_mode == "any":
        return matched_count >= 1
    if match_mode == "atleast2":
        return matched_count >= min(2, total_terms)
    if match_mode == "all":
        return matched_count == total_terms
    return False


def matching_lines(full_text: str, terms: List[str], limit: int = 8) -> List[str]:
    hits = []
    for raw_line in full_text.splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        lowered = line.lower()
        if any(term.lower() in lowered for term in terms):
            hits.append(line)
        if len(hits) >= limit:
            break
    return hits


def load_stage1_manifest(path: Path) -> Dict[str, dict]:
    manifest = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uuid = row.get("conversation_uuid", "").strip()
            if uuid:
                manifest[uuid] = row
    return manifest


def load_conversations(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected conversations.json top level to be a list")
    return data


def resolve_paths(
    base_dir_arg: str,
    manifest_arg: str,
    json_arg: str,
) -> Tuple[Path, Path, Path]:
    if base_dir_arg:
        base_dir = Path(base_dir_arg)
    else:
        cwd = Path.cwd()
        if (cwd / "conversations.json").exists():
            base_dir = cwd
        else:
            base_dir = Path("/storage/emulated/0/Documents/NexusVault")

    if manifest_arg:
        manifest_path = Path(manifest_arg)
    else:
        press_root = base_dir / "_press"
        candidates = sorted(press_root.glob("press_stage1_*/conversations_manifest.csv"), reverse=True)
        if not candidates:
            raise FileNotFoundError("Could not locate Stage 1 manifest CSV under NexusVault/_press")
        manifest_path = candidates[0]

    if json_arg:
        json_path = Path(json_arg)
    else:
        json_path = base_dir / "conversations.json"

    return base_dir, manifest_path, json_path


def build_candidate_rows(
    conversations: List[dict],
    manifest_map: Dict[str, dict],
    required_terms: List[str],
    boost_terms: List[str],
    match_mode: str,
    required_body_min_hits: int,
) -> List[dict]:
    candidates = []
    query_terms = merge_terms(required_terms, boost_terms)

    for conv in conversations:
        uuid = (conv.get("uuid") or "").strip()
        title = normalize_whitespace(conv.get("name", "") or "Untitled Conversation")
        summary = normalize_whitespace(conv.get("summary", ""))

        manifest_row = manifest_map.get(uuid, {})
        created_at = manifest_row.get("created_at", conv.get("created_at", ""))
        updated_at = manifest_row.get("updated_at", conv.get("updated_at", ""))
        message_count = int(manifest_row.get("message_count", "0") or "0")
        char_count = int(manifest_row.get("message_text_char_count", "0") or "0")
        a_now_hit_count = int(manifest_row.get("a_now_hit_count", "0") or "0")
        first_excerpt = manifest_row.get("first_message_excerpt", "")
        last_excerpt = manifest_row.get("last_message_excerpt", "")

        parts = []
        for msg in conv.get("chat_messages", []):
            sender = role_label(msg.get("sender", ""))
            text = normalize_whitespace(extract_message_text(msg))
            if text:
                parts.append(f"{sender}: {text}")
        full_text = "\n".join(parts)

        score, score_detail = score_terms(
            title=title,
            summary=summary,
            first_excerpt=first_excerpt,
            last_excerpt=last_excerpt,
            full_text=full_text,
            required_terms=required_terms,
            boost_terms=boost_terms,
        )

        if score <= 0:
            continue

        matched_terms = matched_terms_from_detail(score_detail, query_terms)

        required_gate_passed = True
        required_gate_detail = {}
        required_terms_passed = []
        required_terms_strong = []
        required_terms_body_only = []
        required_terms_failed = []

        if required_terms:
            required_gate_passed, required_gate_detail, required_terms_passed, required_terms_strong, required_terms_body_only = required_term_gate_detail(
                score_detail=score_detail,
                required_terms=required_terms,
                required_body_min_hits=required_body_min_hits,
            )
            required_terms_failed = [term for term in required_terms if term not in required_terms_passed]
            if not required_gate_passed:
                continue
        else:
            if not passes_match_gate(matched_terms, query_terms, match_mode):
                continue

        candidates.append({
            "uuid": uuid,
            "title": title,
            "summary": summary,
            "created_at": created_at,
            "updated_at": updated_at,
            "message_count": message_count,
            "char_count": char_count,
            "a_now_hit_count": a_now_hit_count,
            "first_excerpt": first_excerpt,
            "last_excerpt": last_excerpt,
            "full_text": full_text,
            "conversation": conv,
            "score": score,
            "score_detail": score_detail,
            "matched_terms": matched_terms,
            "matched_term_count": len(matched_terms),
            "required_gate_passed": required_gate_passed,
            "required_gate_detail": required_gate_detail,
            "required_terms_passed": required_terms_passed,
            "required_terms_strong": required_terms_strong,
            "required_terms_body_only": required_terms_body_only,
            "required_terms_failed": required_terms_failed,
            "matching_lines": matching_lines(full_text, query_terms, limit=8),
        })

    candidates.sort(
        key=lambda row: (
            -len(row["required_terms_strong"]),
            -row["matched_term_count"],
            -row["score"],
            -row["char_count"],
            -row["message_count"],
            row["title"].lower(),
        )
    )
    return candidates


def format_conversation_block(
    row: dict,
    query_terms: List[str],
    required_terms: List[str],
    boost_terms: List[str],
    match_mode: str,
    required_body_min_hits: int,
) -> str:
    conv = row["conversation"]
    lines = []

    lines.append(f"## Conversation: {row['title']}")
    lines.append("")
    lines.append(f"- conversation_uuid: `{row['uuid']}`")
    lines.append(f"- created_at: `{row['created_at']}`")
    lines.append(f"- updated_at: `{row['updated_at']}`")
    lines.append(f"- message_count: `{row['message_count']}`")
    lines.append(f"- message_text_char_count: `{row['char_count']}`")
    lines.append(f"- a_now_hit_count: `{row['a_now_hit_count']}`")
    lines.append(f"- press_score: `{row['score']}`")
    lines.append(f"- query_terms: `{', '.join(query_terms)}`")
    lines.append(f"- required_terms: `{', '.join(required_terms)}`")
    lines.append(f"- booster_terms: `{', '.join(boost_terms)}`")
    lines.append(f"- match_mode: `{match_mode}`")
    lines.append(f"- required_body_min_hits: `{required_body_min_hits}`")
    lines.append(f"- matched_terms: `{', '.join(row['matched_terms'])}`")
    lines.append(f"- matched_term_count: `{row['matched_term_count']}`")
    lines.append(f"- required_terms_passed: `{', '.join(row['required_terms_passed'])}`")
    lines.append(f"- required_terms_strong: `{', '.join(row['required_terms_strong'])}`")
    lines.append(f"- required_terms_body_only: `{', '.join(row['required_terms_body_only'])}`")
    lines.append("")

    lines.append("### Match Signals")
    lines.append("")
    for field_name in ["title", "summary", "first_excerpt", "last_excerpt", "full_text"]:
        lines.append(f"- {field_name}: `{row['score_detail'][field_name]}`")
    lines.append("")

    if row["required_gate_detail"]:
        lines.append("### Required Term Gate Detail")
        lines.append("")
        for term in required_terms:
            term_detail = row["required_gate_detail"].get(term, {})
            lines.append(
                f"- {term}: strong_hits `{term_detail.get('strong_hits', 0)}` | body_hits `{term_detail.get('body_hits', 0)}` | mode `{term_detail.get('mode', '')}`"
            )
        lines.append("")

    if row["matching_lines"]:
        lines.append("### Matching Lines")
        lines.append("")
        for line in row["matching_lines"]:
            lines.append(f"- {line}")
        lines.append("")

    lines.append("### Conversation Body")
    lines.append("")
    for msg in conv.get("chat_messages", []):
        sender = role_label(msg.get("sender", ""))
        text = extract_message_text(msg).rstrip()
        if not text:
            continue
        lines.append(f"### {sender}")
        lines.append(text)
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def pack_candidates(
    candidates: List[dict],
    max_sources: int,
    target_chars_per_source: int,
) -> List[List[dict]]:
    packs = []
    current_pack = []
    current_chars = 0

    for row in candidates:
        estimated_size = max(row["char_count"], len(row["full_text"]))

        if not current_pack:
            current_pack.append(row)
            current_chars = estimated_size
            continue

        would_exceed = current_chars + estimated_size > target_chars_per_source
        source_limit_pressure = len(packs) + 1 >= max_sources

        if would_exceed and not source_limit_pressure:
            packs.append(current_pack)
            current_pack = [row]
            current_chars = estimated_size
        else:
            current_pack.append(row)
            current_chars += estimated_size

    if current_pack:
        packs.append(current_pack)

    if len(packs) > max_sources:
        overflow = []
        for extra_pack in packs[max_sources - 1:]:
            overflow.extend(extra_pack)
        packs = packs[:max_sources - 1]
        packs.append(overflow)

    return packs


def write_compact_outputs(
    run_dir: Path,
    query_terms: List[str],
    required_terms: List[str],
    boost_terms: List[str],
    match_mode: str,
    required_body_min_hits: int,
    candidates_before_cap: int,
    candidates: List[dict],
    packs: List[List[dict]],
) -> None:
    pack_index_csv = run_dir / "_Pack_Index.csv"
    with pack_index_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "source_file",
            "source_index",
            "conversation_uuid",
            "title",
            "score",
            "matched_term_count",
            "matched_terms",
            "required_terms_passed",
            "required_terms_strong",
            "required_terms_body_only",
            "message_count",
            "char_count",
            "a_now_hit_count",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, pack in enumerate(packs, start=1):
            source_filename = f"{i:03d}_{safe_slug('-'.join(query_terms), max_len=36)}.md"
            for row in pack:
                writer.writerow({
                    "source_file": source_filename,
                    "source_index": f"{i:03d}",
                    "conversation_uuid": row["uuid"],
                    "title": row["title"],
                    "score": row["score"],
                    "matched_term_count": row["matched_term_count"],
                    "matched_terms": csv_escape_pipe_join(row["matched_terms"]),
                    "required_terms_passed": csv_escape_pipe_join(row["required_terms_passed"]),
                    "required_terms_strong": csv_escape_pipe_join(row["required_terms_strong"]),
                    "required_terms_body_only": csv_escape_pipe_join(row["required_terms_body_only"]),
                    "message_count": row["message_count"],
                    "char_count": row["char_count"],
                    "a_now_hit_count": row["a_now_hit_count"],
                })

    candidates_csv = run_dir / "_Candidates.csv"
    with candidates_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "conversation_uuid",
            "title",
            "score",
            "matched_term_count",
            "matched_terms",
            "required_terms_passed",
            "required_terms_strong",
            "required_terms_body_only",
            "created_at",
            "updated_at",
            "message_count",
            "char_count",
            "a_now_hit_count",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in candidates:
            writer.writerow({
                "conversation_uuid": row["uuid"],
                "title": row["title"],
                "score": row["score"],
                "matched_term_count": row["matched_term_count"],
                "matched_terms": csv_escape_pipe_join(row["matched_terms"]),
                "required_terms_passed": csv_escape_pipe_join(row["required_terms_passed"]),
                "required_terms_strong": csv_escape_pipe_join(row["required_terms_strong"]),
                "required_terms_body_only": csv_escape_pipe_join(row["required_terms_body_only"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
                "char_count": row["char_count"],
                "a_now_hit_count": row["a_now_hit_count"],
            })

    console_summary = run_dir / "_Console_Summary.txt"
    with console_summary.open("w", encoding="utf-8") as f:
        f.write("Press Pack Console Summary\n")
        f.write("==========================\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Query Terms: {', '.join(query_terms)}\n")
        f.write(f"Required Terms: {', '.join(required_terms)}\n")
        f.write(f"Booster Terms: {', '.join(boost_terms)}\n")
        f.write(f"Match Mode: {match_mode}\n")
        f.write(f"Required Body Min Hits: {required_body_min_hits}\n")
        f.write(f"Matched Conversations Before Cap: {candidates_before_cap}\n")
        f.write(f"Matched Conversations After Cap: {len(candidates)}\n")
        f.write(f"Output Sources: {len(packs)}\n\n")

        f.write("Source Files\n")
        f.write("------------\n")
        for i, pack in enumerate(packs, start=1):
            source_filename = f"{i:03d}_{safe_slug('-'.join(query_terms), max_len=36)}.md"
            combined_score = sum(row["score"] for row in pack)
            combined_chars = sum(row["char_count"] for row in pack)
            f.write(
                f"{source_filename} | conversations={len(pack)} | combined_score={combined_score} | combined_char_count={combined_chars}\n"
            )
        f.write("\n")

        f.write("Included Conversations By Source\n")
        f.write("-------------------------------\n")
        for i, pack in enumerate(packs, start=1):
            source_filename = f"{i:03d}_{safe_slug('-'.join(query_terms), max_len=36)}.md"
            f.write(f"\n[{source_filename}]\n")
            for row in pack:
                f.write(
                    f"- {row['uuid']} | {row['title']} | matched_terms={', '.join(row['matched_terms'])} | required_strong={', '.join(row['required_terms_strong'])} | required_body_only={', '.join(row['required_terms_body_only'])} | score={row['score']} | chars={row['char_count']}\n"
                )


def write_pack(
    base_dir: Path,
    manifest_path: Path,
    json_path: Path,
    query_terms: List[str],
    required_terms: List[str],
    boost_terms: List[str],
    match_mode: str,
    required_body_min_hits: int,
    candidates_before_cap: int,
    candidates: List[dict],
    packs: List[List[dict]],
) -> Path:
    press_root = base_dir / "_press"
    press_root.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    query_slug = safe_slug("-".join(query_terms), max_len=36)
    run_dir = press_root / f"pressed_pack_{ts}_{query_slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    total_conversations = 0

    for i, pack in enumerate(packs, start=1):
        total_conversations += len(pack)
        source_filename = f"{i:03d}_{query_slug}.md"
        source_path = run_dir / source_filename

        uuids = [row["uuid"] for row in pack]
        titles = [row["title"] for row in pack]
        combined_score = sum(row["score"] for row in pack)
        combined_chars = sum(row["char_count"] for row in pack)

        with source_path.open("w", encoding="utf-8") as f:
            f.write("---\n")
            f.write('type: "pressed-notebook-source"\n')
            f.write(f'generated: "{datetime.now().isoformat()}"\n')
            f.write(f'query_terms: "{", ".join(query_terms)}"\n')
            f.write(f'required_terms: "{", ".join(required_terms)}"\n')
            f.write(f'booster_terms: "{", ".join(boost_terms)}"\n')
            f.write(f'match_mode: "{match_mode}"\n')
            f.write(f'required_body_min_hits: "{required_body_min_hits}"\n')
            f.write(f'pack_index: "{i:03d}"\n')
            f.write(f'conversation_count: "{len(pack)}"\n')
            f.write(f'combined_score: "{combined_score}"\n')
            f.write(f'combined_char_count: "{combined_chars}"\n')
            f.write("conversation_uuids:\n")
            for uuid in uuids:
                f.write(f'  - "{yaml_escape(uuid)}"\n')
            f.write("---\n\n")

            f.write(f"# Pressed Source {i:03d}\n\n")
            f.write(f"Query Terms: `{', '.join(query_terms)}`\n\n")
            f.write(f"Required Terms: `{', '.join(required_terms)}`\n\n")
            f.write(f"Booster Terms: `{', '.join(boost_terms)}`\n\n")
            f.write(f"Match Mode: `{match_mode}`\n\n")
            f.write(f"Required Body Min Hits: `{required_body_min_hits}`\n\n")
            f.write(f"Source File: `{source_filename}`\n\n")
            f.write(f"Conversation Count: `{len(pack)}`\n\n")
            f.write(f"Combined Score: `{combined_score}`\n\n")
            f.write("Included Conversations:\n")
            for row in pack:
                f.write(
                    f"- `{row['uuid']}` | {row['title']} | matched_terms `{', '.join(row['matched_terms'])}` | required_strong `{', '.join(row['required_terms_strong'])}` | required_body_only `{', '.join(row['required_terms_body_only'])}` | score `{row['score']}`\n"
                )
            f.write("\n---\n\n")

            for row in pack:
                f.write(
                    format_conversation_block(
                        row=row,
                        query_terms=query_terms,
                        required_terms=required_terms,
                        boost_terms=boost_terms,
                        match_mode=match_mode,
                        required_body_min_hits=required_body_min_hits,
                    )
                )

        summary_rows.append({
            "source_file": source_filename,
            "conversation_count": len(pack),
            "combined_score": combined_score,
            "combined_char_count": combined_chars,
            "conversation_uuids": " | ".join(uuids),
            "conversation_titles": " | ".join(titles),
        })

    manifest_md = run_dir / "_Manifest.md"
    with manifest_md.open("w", encoding="utf-8") as f:
        f.write("# Press Manifest\n\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Base Directory: `{base_dir}`\n\n")
        f.write(f"Manifest CSV Used: `{manifest_path}`\n\n")
        f.write(f"JSON Used: `{json_path}`\n\n")
        f.write(f"Query Terms: `{', '.join(query_terms)}`\n\n")
        f.write(f"Required Terms: `{', '.join(required_terms)}`\n\n")
        f.write(f"Booster Terms: `{', '.join(boost_terms)}`\n\n")
        f.write(f"Match Mode: `{match_mode}`\n\n")
        f.write(f"Required Body Min Hits: `{required_body_min_hits}`\n\n")
        f.write(f"Matched Conversations Before Cap: `{candidates_before_cap}`\n\n")
        f.write(f"Pressed Conversations: `{total_conversations}`\n\n")
        f.write(f"Output Sources: `{len(packs)}`\n\n")
        f.write("## Source Files\n\n")
        for row in summary_rows:
            f.write(
                f"- `{row['source_file']}` | conversations `{row['conversation_count']}` | combined_score `{row['combined_score']}`\n"
            )
        f.write("\n## Notes\n\n")
        f.write("This pack preserves whole conversations intact.\n\n")
        f.write("Admission logic is field-aware when required terms are supplied.\n\n")
        f.write("Required terms pass if they appear in title, summary, first excerpt, or last excerpt, or meet the body hit minimum.\n\n")
        f.write("Booster terms affect scoring but do not control admission when required terms are present.\n\n")
        f.write("v1.2 adds compact summary artifacts for low-noise inspection.\n\n")
        f.write("Alias families, synonym families, and concept-family expansion are not yet applied in this version.\n\n")

    manifest_csv = run_dir / "_Manifest.csv"
    with manifest_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "source_file",
            "conversation_count",
            "combined_score",
            "combined_char_count",
            "conversation_uuids",
            "conversation_titles",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    write_compact_outputs(
        run_dir=run_dir,
        query_terms=query_terms,
        required_terms=required_terms,
        boost_terms=boost_terms,
        match_mode=match_mode,
        required_body_min_hits=required_body_min_hits,
        candidates_before_cap=candidates_before_cap,
        candidates=candidates,
        packs=packs,
    )

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a JSON-first NotebookLM press pack from raw conversations.json plus Stage 1 manifest."
    )
    parser.add_argument(
        "keywords",
        nargs="*",
        help="Legacy general terms. If --require or --boost are supplied, these are treated as additional booster terms."
    )
    parser.add_argument(
        "--require",
        nargs="*",
        default=[],
        help="Required terms for admission. Each selected conversation must pass field-aware gating for each required term."
    )
    parser.add_argument(
        "--boost",
        nargs="*",
        default=[],
        help="Booster terms used for scoring and ranking."
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Override NexusVault base directory."
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Override Stage 1 manifest CSV path."
    )
    parser.add_argument(
        "--json",
        default="",
        help="Override conversations.json path."
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=16,
        help="Maximum number of pressed markdown source files to emit."
    )
    parser.add_argument(
        "--target-chars-per-source",
        type=int,
        default=250000,
        help="Target total message characters per emitted source file before rolling to the next source."
    )
    parser.add_argument(
        "--match-mode",
        choices=["any", "atleast2", "all"],
        default="atleast2",
        help="Used only when no required terms are supplied."
    )
    parser.add_argument(
        "--required-body-min-hits",
        type=int,
        default=2,
        help="If a required term is absent from strong fields, this many body hits can still admit it."
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=48,
        help="Maximum number of matched conversations to pass into packing after scoring and gating."
    )
    args = parser.parse_args()

    required_terms = dedupe_terms(args.require)
    boost_terms = dedupe_terms(args.boost + args.keywords)
    query_terms = merge_terms(required_terms, boost_terms)

    if not query_terms:
        print("No query terms supplied.", file=sys.stderr)
        return 1

    base_dir, manifest_path, json_path = resolve_paths(args.base_dir, args.manifest, args.json)

    log_message(f"Base directory resolved: {base_dir}")
    log_message(f"Stage 1 manifest resolved: {manifest_path}")
    log_message(f"Raw JSON resolved: {json_path}")
    log_message(f"Query terms: {', '.join(query_terms)}")
    log_message(f"Required terms: {', '.join(required_terms)}")
    log_message(f"Booster terms: {', '.join(boost_terms)}")

    if required_terms:
        log_message(f"Using field-aware required-term gating with body minimum hits: {args.required_body_min_hits}")
    else:
        log_message(f"Using legacy distinct-term gate with match mode: {args.match_mode}")

    if not manifest_path.exists():
        log_message(f"Missing manifest CSV: {manifest_path}")
        return 1

    if not json_path.exists():
        log_message(f"Missing conversations.json: {json_path}")
        return 1

    log_message("Loading Stage 1 manifest")
    manifest_map = load_stage1_manifest(manifest_path)

    log_message("Loading raw conversations.json")
    conversations = load_conversations(json_path)

    log_message("Scoring conversations")
    candidates = build_candidate_rows(
        conversations=conversations,
        manifest_map=manifest_map,
        required_terms=required_terms,
        boost_terms=boost_terms,
        match_mode=args.match_mode,
        required_body_min_hits=args.required_body_min_hits,
    )

    if not candidates:
        log_message("No matching conversations found")
        return 0

    candidates_before_cap = len(candidates)
    log_message(f"Matched conversations before cap: {candidates_before_cap}")

    if args.max_candidates > 0:
        candidates = candidates[:args.max_candidates]

    log_message(f"Matched conversations after cap: {len(candidates)}")

    packs = pack_candidates(
        candidates=candidates,
        max_sources=args.max_sources,
        target_chars_per_source=args.target_chars_per_source,
    )
    log_message(f"Planned source files: {len(packs)}")

    run_dir = write_pack(
        base_dir=base_dir,
        manifest_path=manifest_path,
        json_path=json_path,
        query_terms=query_terms,
        required_terms=required_terms,
        boost_terms=boost_terms,
        match_mode=args.match_mode,
        required_body_min_hits=args.required_body_min_hits,
        candidates_before_cap=candidates_before_cap,
        candidates=candidates,
        packs=packs,
    )

    log_message(f"Pressed pack written: {run_dir}")
    log_message(f"Compact summary: {run_dir / '_Console_Summary.txt'}")
    log_message(f"Pack index CSV: {run_dir / '_Pack_Index.csv'}")
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Version History Log
# 20260327022331.0 - Initial JSON-first press pack builder using Stage 1 manifest plus raw conversations.json to emit numbered NotebookLM-ready sources and manifests while preserving whole conversations intact.
# 20260327034456.1 - Added distinct-term match gating via --match-mode, added --max-candidates cap, and surfaced matched term metadata in outputs and manifests.
# 20260327053218.2 - Added required terms, booster terms, field-aware gating, compact summary artifacts, backup-first patch workflow, and lower-noise candidate/index outputs.
