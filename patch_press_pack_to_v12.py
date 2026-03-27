# ver 20260327054822.0
from pathlib import Path
from datetime import datetime
import shutil
import sys

TARGET = Path("/storage/emulated/0/Documents/NexusVault/press_pack_from_json_v1.py")

def log_message(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)

def require(condition: bool, message: str) -> None:
    if not condition:
        log_message(message)
        raise SystemExit(1)

def replace_once(text: str, old: str, new: str, label: str) -> str:
    require(old in text, f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)

def main() -> None:
    require(TARGET.exists(), f"Missing target script: {TARGET}")

    original = TARGET.read_text(encoding="utf-8")
    require("def write_pack(" in original, "Target script is missing write_pack anchor")
    require("def build_candidate_rows(" in original, "Target script is missing build_candidate_rows anchor")
    require("def main(" in original, "Target script is missing main anchor")

    backup_dir = TARGET.parent / "_press" / f"script_backups_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / TARGET.name
    shutil.copy2(TARGET, backup_path)
    log_message(f"Backed up: {backup_path}")

    text = original

    text = replace_once(
        text,
        "from typing import Dict, List, Tuple\n",
        "from typing import Dict, List, Tuple\n\n\ndef csv_escape_pipe_join(values: List[str]) -> str:\n    return \" | \".join(values)\n\n\ndef dedupe_terms(values: List[str]) -> List[str]:\n    result = []\n    seen = set()\n    for raw in values:\n        value = normalize_whitespace(raw)\n        if not value:\n            continue\n        key = value.lower()\n        if key in seen:\n            continue\n        seen.add(key)\n        result.append(value)\n    return result\n\n\ndef merge_terms(required_terms: List[str], boost_terms: List[str]) -> List[str]:\n    return dedupe_terms(required_terms + boost_terms)\n",
        "helpers insert",
    )

    text = replace_once(
        text,
        "def total_hits_by_term(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> Dict[str, int]:\n    totals = {}\n    for term in terms:\n        totals[term] = sum(score_detail[field].get(term, 0) for field in score_detail)\n    return totals\n\n\ndef matched_terms_from_detail(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> List[str]:\n    totals = total_hits_by_term(score_detail, terms)\n    return [term for term in terms if totals.get(term, 0) > 0]\n",
        "def total_hits_by_term(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> Dict[str, int]:\n    totals = {}\n    for term in terms:\n        totals[term] = sum(score_detail[field].get(term, 0) for field in score_detail)\n    return totals\n\n\ndef matched_terms_from_detail(score_detail: Dict[str, Dict[str, int]], terms: List[str]) -> List[str]:\n    totals = total_hits_by_term(score_detail, terms)\n    return [term for term in terms if totals.get(term, 0) > 0]\n\n\ndef required_term_gate_detail(\n    score_detail: Dict[str, Dict[str, int]],\n    required_terms: List[str],\n    required_body_min_hits: int,\n) -> Tuple[bool, Dict[str, dict], List[str], List[str], List[str]]:\n    details = {}\n    passed_terms = []\n    strong_terms = []\n    body_only_terms = []\n    failed_terms = []\n\n    for term in required_terms:\n        strong_hits = (\n            score_detail[\"title\"].get(term, 0)\n            + score_detail[\"summary\"].get(term, 0)\n            + score_detail[\"first_excerpt\"].get(term, 0)\n            + score_detail[\"last_excerpt\"].get(term, 0)\n        )\n        body_hits = score_detail[\"full_text\"].get(term, 0)\n\n        if strong_hits > 0:\n            mode = \"strong\"\n            passed = True\n            passed_terms.append(term)\n            strong_terms.append(term)\n        elif body_hits >= required_body_min_hits:\n            mode = \"body\"\n            passed = True\n            passed_terms.append(term)\n            body_only_terms.append(term)\n        else:\n            mode = \"failed\"\n            passed = False\n            failed_terms.append(term)\n\n        details[term] = {\n            \"strong_hits\": strong_hits,\n            \"body_hits\": body_hits,\n            \"passed\": passed,\n            \"mode\": mode,\n        }\n\n    return len(failed_terms) == 0, details, passed_terms, strong_terms, body_only_terms\n",
        "required term gate insert",
    )

    text = replace_once(
        text,
        "def build_candidate_rows(\n    conversations: List[dict],\n    manifest_map: Dict[str, dict],\n    terms: List[str],\n    match_mode: str,\n) -> List[dict]:\n    candidates = []\n",
        "def build_candidate_rows(\n    conversations: List[dict],\n    manifest_map: Dict[str, dict],\n    required_terms: List[str],\n    boost_terms: List[str],\n    match_mode: str,\n    required_body_min_hits: int,\n) -> List[dict]:\n    candidates = []\n    terms = merge_terms(required_terms, boost_terms)\n",
        "build_candidate_rows signature",
    )

    text = replace_once(
        text,
        "        score, score_detail = weighted_score(\n            title=title,\n            summary=summary,\n            first_excerpt=first_excerpt,\n            last_excerpt=last_excerpt,\n            full_text=full_text,\n            terms=terms,\n        )\n\n        if score <= 0:\n            continue\n\n        matched_terms = matched_terms_from_detail(score_detail, terms)\n        if not passes_match_gate(matched_terms, terms, match_mode):\n            continue\n\n        candidates.append({\n",
        "        score, score_detail = weighted_score(\n            title=title,\n            summary=summary,\n            first_excerpt=first_excerpt,\n            last_excerpt=last_excerpt,\n            full_text=full_text,\n            terms=terms,\n        )\n\n        if score <= 0:\n            continue\n\n        matched_terms = matched_terms_from_detail(score_detail, terms)\n\n        required_gate_passed = True\n        required_gate_detail = {}\n        required_terms_passed = []\n        required_terms_strong = []\n        required_terms_body_only = []\n        required_terms_failed = []\n\n        if required_terms:\n            required_gate_passed, required_gate_detail, required_terms_passed, required_terms_strong, required_terms_body_only = required_term_gate_detail(\n                score_detail=score_detail,\n                required_terms=required_terms,\n                required_body_min_hits=required_body_min_hits,\n            )\n            required_terms_failed = [term for term in required_terms if term not in required_terms_passed]\n            if not required_gate_passed:\n                continue\n        else:\n            if not passes_match_gate(matched_terms, terms, match_mode):\n                continue\n\n        candidates.append({\n",
        "build_candidate_rows gating body",
    )

    text = replace_once(
        text,
        "            \"matched_terms\": matched_terms,\n            \"matched_term_count\": len(matched_terms),\n            \"matching_lines\": matching_lines(full_text, terms, limit=12),\n        })\n\n    candidates.sort(\n        key=lambda row: (\n            -row[\"matched_term_count\"],\n            -row[\"score\"],\n",
        "            \"matched_terms\": matched_terms,\n            \"matched_term_count\": len(matched_terms),\n            \"required_gate_passed\": required_gate_passed,\n            \"required_gate_detail\": required_gate_detail,\n            \"required_terms_passed\": required_terms_passed,\n            \"required_terms_strong\": required_terms_strong,\n            \"required_terms_body_only\": required_terms_body_only,\n            \"required_terms_failed\": required_terms_failed,\n            \"matching_lines\": matching_lines(full_text, terms, limit=8),\n        })\n\n    candidates.sort(\n        key=lambda row: (\n            -len(row[\"required_terms_strong\"]),\n            -row[\"matched_term_count\"],\n            -row[\"score\"],\n",
        "build_candidate_rows row payload",
    )

    text = replace_once(
        text,
        "def format_conversation_block(row: dict, terms: List[str], match_mode: str) -> str:\n",
        "def format_conversation_block(row: dict, terms: List[str], match_mode: str, required_terms: List[str], boost_terms: List[str], required_body_min_hits: int) -> str:\n",
        "format signature",
    )

    text = replace_once(
        text,
        "    lines.append(f\"- match_mode: `{match_mode}`\")\n    lines.append(f\"- matched_terms: `{', '.join(row['matched_terms'])}`\")\n",
        "    lines.append(f\"- match_mode: `{match_mode}`\")\n    lines.append(f\"- required_terms: `{', '.join(required_terms)}`\")\n    lines.append(f\"- booster_terms: `{', '.join(boost_terms)}`\")\n    lines.append(f\"- required_body_min_hits: `{required_body_min_hits}`\")\n    lines.append(f\"- matched_terms: `{', '.join(row['matched_terms'])}`\")\n",
        "format header expansion",
    )

    text = replace_once(
        text,
        "    if row[\"matching_lines\"]:\n",
        "    if row[\"required_gate_detail\"]:\n        lines.append(\"### Required Term Gate Detail\")\n        lines.append(\"\")\n        for term in required_terms:\n            term_detail = row[\"required_gate_detail\"].get(term, {})\n            lines.append(f\"- {term}: strong_hits `{term_detail.get('strong_hits', 0)}` | body_hits `{term_detail.get('body_hits', 0)}` | mode `{term_detail.get('mode', '')}`\")\n        lines.append(\"\")\n\n    if row[\"matching_lines\"]:\n",
        "format required detail block",
    )

    write_helpers = r'''
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
    query_slug = safe_slug("-".join(query_terms), max_len=36)

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
            source_filename = f"{i:03d}_{query_slug}.md"
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
        f.write("Included Conversations By Source\n")
        f.write("-------------------------------\n")
        for i, pack in enumerate(packs, start=1):
            source_filename = f"{i:03d}_{query_slug}.md"
            f.write(f"\n[{source_filename}]\n")
            for row in pack:
                f.write(
                    f"- {row['uuid']} | {row['title']} | matched_terms={', '.join(row['matched_terms'])} | required_strong={', '.join(row['required_terms_strong'])} | required_body_only={', '.join(row['required_terms_body_only'])} | score={row['score']} | chars={row['char_count']}\n"
                )
'''
    require("def write_pack(\n" in text, "write_pack not found")
    text = text.replace("def write_pack(\n", write_helpers + "\n\ndef write_pack(\n", 1)

    text = replace_once(
        text,
        "def write_pack(\n    base_dir: Path,\n    manifest_path: Path,\n    json_path: Path,\n    query_terms: List[str],\n    match_mode: str,\n    candidates_before_cap: int,\n    candidates: List[dict],\n    packs: List[List[dict]],\n) -> Path:\n",
        "def write_pack(\n    base_dir: Path,\n    manifest_path: Path,\n    json_path: Path,\n    query_terms: List[str],\n    required_terms: List[str],\n    boost_terms: List[str],\n    match_mode: str,\n    required_body_min_hits: int,\n    candidates_before_cap: int,\n    candidates: List[dict],\n    packs: List[List[dict]],\n) -> Path:\n",
        "write_pack signature",
    )

    text = replace_once(
        text,
        "            f.write(f'generated: \"{datetime.now().isoformat()}\"\\n')\n            f.write(f'match_mode: \"{match_mode}\"\\n')\n            f.write(f'query_terms: \"{\", \".join(query_terms)}\"\\n')\n",
        "            f.write(f'generated: \"{datetime.now().isoformat()}\"\\n')\n            f.write(f'match_mode: \"{match_mode}\"\\n')\n            f.write(f'query_terms: \"{\", \".join(query_terms)}\"\\n')\n            f.write(f'required_terms: \"{\", \".join(required_terms)}\"\\n')\n            f.write(f'booster_terms: \"{\", \".join(boost_terms)}\"\\n')\n            f.write(f'required_body_min_hits: \"{required_body_min_hits}\"\\n')\n",
        "frontmatter expansion",
    )

    text = replace_once(
        text,
        "            f.write(f\"Query Terms: `{', '.join(query_terms)}`\\n\\n\")\n            f.write(f\"Match Mode: `{match_mode}`\\n\\n\")\n",
        "            f.write(f\"Query Terms: `{', '.join(query_terms)}`\\n\\n\")\n            f.write(f\"Required Terms: `{', '.join(required_terms)}`\\n\\n\")\n            f.write(f\"Booster Terms: `{', '.join(boost_terms)}`\\n\\n\")\n            f.write(f\"Match Mode: `{match_mode}`\\n\\n\")\n            f.write(f\"Required Body Min Hits: `{required_body_min_hits}`\\n\\n\")\n",
        "source header expansion",
    )

    text = replace_once(
        text,
        "            for row in pack:\n                f.write(f\"- `{row['uuid']}` | {row['title']} | matched_terms `{', '.join(row['matched_terms'])}` | score `{row['score']}`\\n\")\n",
        "            for row in pack:\n                f.write(f\"- `{row['uuid']}` | {row['title']} | matched_terms `{', '.join(row['matched_terms'])}` | required_strong `{', '.join(row['required_terms_strong'])}` | required_body_only `{', '.join(row['required_terms_body_only'])}` | score `{row['score']}`\\n\")\n",
        "included conversations expansion",
    )

    text = replace_once(
        text,
        "            for row in pack:\n                f.write(format_conversation_block(row, query_terms, match_mode))\n",
        "            for row in pack:\n                f.write(format_conversation_block(row, query_terms, match_mode, required_terms, boost_terms, required_body_min_hits))\n",
        "format call expansion",
    )

    text = replace_once(
        text,
        "        f.write(f\"Query Terms: `{', '.join(query_terms)}`\\n\\n\")\n        f.write(f\"Match Mode: `{match_mode}`\\n\\n\")\n        f.write(f\"Matched Conversations Before Cap: `{candidates_before_cap}`\\n\\n\")\n",
        "        f.write(f\"Query Terms: `{', '.join(query_terms)}`\\n\\n\")\n        f.write(f\"Required Terms: `{', '.join(required_terms)}`\\n\\n\")\n        f.write(f\"Booster Terms: `{', '.join(boost_terms)}`\\n\\n\")\n        f.write(f\"Match Mode: `{match_mode}`\\n\\n\")\n        f.write(f\"Required Body Min Hits: `{required_body_min_hits}`\\n\\n\")\n        f.write(f\"Matched Conversations Before Cap: `{candidates_before_cap}`\\n\\n\")\n",
        "manifest expansion",
    )

    text = replace_once(
        text,
        "        f.write(\"v1.1 adds distinct-term match gating and candidate capping.\\n\\n\")\n",
        "        f.write(\"v1.2 adds required terms, booster terms, field-aware gating, candidate capping, and compact summary outputs.\\n\\n\")\n",
        "manifest notes update",
    )

    text = replace_once(
        text,
        "    candidate_csv = run_dir / \"_Candidates.csv\"\n    with candidate_csv.open(\"w\", encoding=\"utf-8\", newline=\"\") as f:\n        fieldnames = [\n            \"uuid\",\n            \"title\",\n            \"created_at\",\n            \"updated_at\",\n            \"message_count\",\n            \"char_count\",\n            \"a_now_hit_count\",\n            \"score\",\n            \"matched_term_count\",\n            \"matched_terms\",\n            \"matching_lines\",\n        ]\n        writer = csv.DictWriter(f, fieldnames=fieldnames)\n        writer.writeheader()\n        for row in candidates:\n            writer.writerow({\n                \"uuid\": row[\"uuid\"],\n                \"title\": row[\"title\"],\n                \"created_at\": row[\"created_at\"],\n                \"updated_at\": row[\"updated_at\"],\n                \"message_count\": row[\"message_count\"],\n                \"char_count\": row[\"char_count\"],\n                \"a_now_hit_count\": row[\"a_now_hit_count\"],\n                \"score\": row[\"score\"],\n                \"matched_term_count\": row[\"matched_term_count\"],\n                \"matched_terms\": \" | \".join(row[\"matched_terms\"]),\n                \"matching_lines\": \" | \".join(row[\"matching_lines\"]),\n            })\n\n    return run_dir\n",
        "    candidate_csv = run_dir / \"_Candidates.csv\"\n    with candidate_csv.open(\"w\", encoding=\"utf-8\", newline=\"\") as f:\n        fieldnames = [\n            \"uuid\",\n            \"title\",\n            \"created_at\",\n            \"updated_at\",\n            \"message_count\",\n            \"char_count\",\n            \"a_now_hit_count\",\n            \"score\",\n            \"matched_term_count\",\n            \"matched_terms\",\n            \"required_terms_passed\",\n            \"required_terms_strong\",\n            \"required_terms_body_only\",\n            \"matching_lines\",\n        ]\n        writer = csv.DictWriter(f, fieldnames=fieldnames)\n        writer.writeheader()\n        for row in candidates:\n            writer.writerow({\n                \"uuid\": row[\"uuid\"],\n                \"title\": row[\"title\"],\n                \"created_at\": row[\"created_at\"],\n                \"updated_at\": row[\"updated_at\"],\n                \"message_count\": row[\"message_count\"],\n                \"char_count\": row[\"char_count\"],\n                \"a_now_hit_count\": row[\"a_now_hit_count\"],\n                \"score\": row[\"score\"],\n                \"matched_term_count\": row[\"matched_term_count\"],\n                \"matched_terms\": csv_escape_pipe_join(row[\"matched_terms\"]),\n                \"required_terms_passed\": csv_escape_pipe_join(row[\"required_terms_passed\"]),\n                \"required_terms_strong\": csv_escape_pipe_join(row[\"required_terms_strong\"]),\n                \"required_terms_body_only\": csv_escape_pipe_join(row[\"required_terms_body_only\"]),\n                \"matching_lines\": csv_escape_pipe_join(row[\"matching_lines\"]),\n            })\n\n    write_compact_outputs(\n        run_dir=run_dir,\n        query_terms=query_terms,\n        required_terms=required_terms,\n        boost_terms=boost_terms,\n        match_mode=match_mode,\n        required_body_min_hits=required_body_min_hits,\n        candidates_before_cap=candidates_before_cap,\n        candidates=candidates,\n        packs=packs,\n    )\n\n    return run_dir\n",
        "compact outputs hook",
    )

    text = replace_once(
        text,
        "    parser.add_argument(\n        \"keywords\",\n        nargs=\"+\",\n        help=\"Query terms or quoted phrases to press from the full export.\"\n    )\n",
        "    parser.add_argument(\n        \"keywords\",\n        nargs=\"*\",\n        help=\"Legacy general terms. If --require or --boost are supplied, these are treated as additional booster terms.\"\n    )\n    parser.add_argument(\n        \"--require\",\n        nargs=\"*\",\n        default=[],\n        help=\"Required terms for admission. Each selected conversation must pass field-aware gating for each required term.\"\n    )\n    parser.add_argument(\n        \"--boost\",\n        nargs=\"*\",\n        default=[],\n        help=\"Booster terms used for scoring and ranking.\"\n    )\n",
        "argument expansion",
    )

    text = replace_once(
        text,
        "    parser.add_argument(\n        \"--max-candidates\",\n        type=int,\n        default=48,\n        help=\"Maximum number of matched conversations to pass into packing after scoring and gating.\"\n    )\n    args = parser.parse_args()\n\n    base_dir, manifest_path, json_path = resolve_paths(args.base_dir, args.manifest, args.json)\n",
        "    parser.add_argument(\n        \"--max-candidates\",\n        type=int,\n        default=48,\n        help=\"Maximum number of matched conversations to pass into packing after scoring and gating.\"\n    )\n    parser.add_argument(\n        \"--required-body-min-hits\",\n        type=int,\n        default=2,\n        help=\"If a required term is absent from strong fields, this many body hits can still admit it.\"\n    )\n    args = parser.parse_args()\n\n    required_terms = dedupe_terms(args.require)\n    boost_terms = dedupe_terms(args.boost + args.keywords)\n    query_terms = merge_terms(required_terms, boost_terms)\n\n    if not query_terms:\n        print(\"No query terms supplied.\", file=sys.stderr)\n        return 1\n\n    base_dir, manifest_path, json_path = resolve_paths(args.base_dir, args.manifest, args.json)\n",
        "argument parse logic",
    )

    text = replace_once(
        text,
        "    log_message(f\"Base directory resolved: {base_dir}\")\n    log_message(f\"Stage 1 manifest resolved: {manifest_path}\")\n    log_message(f\"Raw JSON resolved: {json_path}\")\n",
        "    log_message(f\"Base directory resolved: {base_dir}\")\n    log_message(f\"Stage 1 manifest resolved: {manifest_path}\")\n    log_message(f\"Raw JSON resolved: {json_path}\")\n    log_message(f\"Query terms: {', '.join(query_terms)}\")\n    log_message(f\"Required terms: {', '.join(required_terms)}\")\n    log_message(f\"Booster terms: {', '.join(boost_terms)}\")\n",
        "log expansion",
    )

    text = replace_once(
        text,
        "    log_message(f\"Scoring conversations for query: {', '.join(args.keywords)}\")\n    log_message(f\"Applying match mode: {args.match_mode}\")\n    candidates = build_candidate_rows(\n        conversations=conversations,\n        manifest_map=manifest_map,\n        terms=args.keywords,\n        match_mode=args.match_mode,\n    )\n",
        "    log_message(\"Scoring conversations\")\n    if required_terms:\n        log_message(f\"Using field-aware required-term gating with body minimum hits: {args.required_body_min_hits}\")\n    else:\n        log_message(f\"Applying match mode: {args.match_mode}\")\n    candidates = build_candidate_rows(\n        conversations=conversations,\n        manifest_map=manifest_map,\n        required_terms=required_terms,\n        boost_terms=boost_terms,\n        match_mode=args.match_mode,\n        required_body_min_hits=args.required_body_min_hits,\n    )\n",
        "candidate builder call",
    )

    text = replace_once(
        text,
        "    run_dir = write_pack(\n        base_dir=base_dir,\n        manifest_path=manifest_path,\n        json_path=json_path,\n        query_terms=args.keywords,\n        match_mode=args.match_mode,\n        candidates_before_cap=candidates_before_cap,\n        candidates=candidates,\n        packs=packs,\n    )\n",
        "    run_dir = write_pack(\n        base_dir=base_dir,\n        manifest_path=manifest_path,\n        json_path=json_path,\n        query_terms=query_terms,\n        required_terms=required_terms,\n        boost_terms=boost_terms,\n        match_mode=args.match_mode,\n        required_body_min_hits=args.required_body_min_hits,\n        candidates_before_cap=candidates_before_cap,\n        candidates=candidates,\n        packs=packs,\n    )\n",
        "write_pack call",
    )

    text = replace_once(
        text,
        "    log_message(f\"Pressed pack written: {run_dir}\")\n    print(run_dir)\n    return 0\n",
        "    log_message(f\"Pressed pack written: {run_dir}\")\n    log_message(f\"Compact summary: {run_dir / '_Console_Summary.txt'}\")\n    log_message(f\"Pack index CSV: {run_dir / '_Pack_Index.csv'}\")\n    print(run_dir)\n    return 0\n",
        "final logs",
    )

    text = text.replace("# ver 20260327034456.1", "# ver 20260327053218.2", 1)

    old_history = "# 20260327034456.1 - Added distinct-term match gating via --match-mode, added --max-candidates cap, and surfaced matched term metadata in outputs and manifests.\n"
    new_history = old_history + "# 20260327053218.2 - Added required terms, booster terms, field-aware gating, compact summary artifacts, and lower-noise inspection outputs.\n"
    require(old_history in text, "Version history anchor not found")
    text = text.replace(old_history, new_history, 1)

    TARGET.write_text(text, encoding="utf-8")
    log_message(f"Patched: {TARGET}")

if __name__ == "__main__":
    main()

# Version History Log
# 20260327054822.0 - Incremental patcher for press_pack_from_json_v1.py to add v1.2 required/booster gating and compact outputs without pasting the full target script.
