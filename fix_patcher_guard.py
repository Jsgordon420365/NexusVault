# ver 20260327051958.0
from pathlib import Path
from datetime import datetime
import shutil
import sys

PATCHER = Path("/storage/emulated/0/Documents/NexusVault/patch_press_pack_to_v12.py")

def log_message(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)

def main() -> int:
    if not PATCHER.exists():
        log_message(f"Missing patcher: {PATCHER}")
        return 1

    original = PATCHER.read_text(encoding="utf-8")

    old = '    require("# ver 20260327034456.1" in original or "# ver 20260327022331.0" in original, "Target script is not the expected v1.0/v1.1 family")\n'
    new = (
        '    require("def write_pack(" in original, "Target script is missing write_pack anchor")\n'
        '    require("def build_candidate_rows(" in original, "Target script is missing build_candidate_rows anchor")\n'
        '    require("def main(" in original, "Target script is missing main anchor")\n'
    )

    if old not in original:
        log_message("Expected strict version-guard line was not found in patcher")
        log_message("Showing first 80 lines of patcher for inspection")
        print("===== PATCHER HEAD =====")
        print("\n".join(original.splitlines()[:80]))
        return 1

    backup_dir = PATCHER.parent / "_press" / f"patcher_backups_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / PATCHER.name
    shutil.copy2(PATCHER, backup_path)
    log_message(f"Backed up patcher: {backup_path}")

    updated = original.replace(old, new, 1)
    PATCHER.write_text(updated, encoding="utf-8")
    log_message(f"Updated patcher guard: {PATCHER}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

# Version History Log
# 20260327051958.0 - Initial helper script to relax the version-string guard inside patch_press_pack_to_v12.py and rerun safely.
