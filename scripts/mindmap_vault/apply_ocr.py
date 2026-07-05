import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.mindmap_vault import manifest  # noqa: E402
from scripts.mindmap_vault.update import DEFAULT_VAULT  # noqa: E402


def apply_ocr(vault, results_path):
    """Merge externally produced OCR results into the manifest.

    Returns (applied, dropped, unknown) counts.
    """
    vault = Path(vault)
    data = manifest.load(vault)
    payload = json.loads(Path(results_path).read_text(encoding="utf-8"))
    stem = payload["source"]
    source = data["sources"].get(stem)
    if source is None:
        print(f"unknown source '{stem}' in manifest at {vault}", file=sys.stderr)
        raise SystemExit(1)

    applied = 0
    dropped = 0
    unknown = 0
    for r in payload["results"]:
        box_id = r["box_id"]
        if box_id not in source["boxes"]:
            print(f"unknown box id '{box_id}' for source '{stem}'; skipping",
                  file=sys.stderr)
            unknown += 1
            continue
        if r.get("is_concept_box", True):
            source["boxes"][box_id]["ocr"] = {
                "title": r.get("title", ""),
                "text": r.get("text", ""),
                "context": r.get("context"),
                "pending": False,
            }
        else:
            source["boxes"][box_id]["ocr"] = {
                "title": "", "text": "", "context": None,
                "pending": False, "dropped": True,
            }
            dropped += 1
        applied += 1

    manifest.save(vault, data)
    print(f"applied {applied} transcriptions ({dropped} dropped, "
          f"{unknown} unknown ids) to {stem}")
    return applied, dropped, unknown


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Merge externally produced OCR results into the manifest.")
    ap.add_argument("results")
    ap.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = ap.parse_args(argv)
    _, _, unknown = apply_ocr(args.vault, args.results)
    return 0 if unknown == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
