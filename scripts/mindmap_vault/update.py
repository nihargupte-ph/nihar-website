import argparse
import io
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.mindmap_vault import (  # noqa: E402
    arrows, bind, boxes, config, emit, manifest, parse, render,
)
from scripts.mindmap_vault.ocr import ClaudeOcr, OcrError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = Path("/home/n/Documents/vault/classic_research")


def _backup_v1(vault):
    vault = Path(vault)
    if not vault.exists():
        return
    if (vault / ".pipeline" / "manifest.json").exists():
        return
    if not any(vault.iterdir()):
        return
    backup = vault.parent / f"{vault.name}_v1_backup"
    if backup.exists():
        raise SystemExit(
            f"refusing to overwrite existing backup at {backup}; move it aside first"
        )
    vault.rename(backup)
    print(f"archived pre-pipeline vault to {backup}")


def run(svg_path, vault, ocr_client=None, json_path=None, dry_run=False,
        limit=None, bg=config.CROP_BG):
    svg_path = Path(svg_path)
    vault = Path(vault)
    stem = svg_path.stem
    if json_path is None:
        json_path = REPO_ROOT / "static" / "mindmaps" / f"{stem}-index.json"

    _backup_v1(vault)
    vault.mkdir(parents=True, exist_ok=True)

    parsed = parse.parse_svg(svg_path)
    found = boxes.find_boxes(parsed.strokes)
    edge_list, review = arrows.find_edges(parsed.strokes, found)
    bind.bind(parsed.strokes, parsed.images, found, edge_list)

    data = manifest.load(vault)
    source = data["sources"].setdefault(stem, {"next_box": 1, "boxes": {}})
    # capture slugs before reconcile rewrites the boxes dict (deleted records vanish)
    old_slugs = {bid: rec.get("slug") for bid, rec in source["boxes"].items()}
    decisions, deleted = manifest.reconcile(source, found)
    deleted_slugs = [old_slugs[bid] for bid in deleted if old_slugs.get(bid)]

    strokes_by_id = {s.sid: s for s in parsed.strokes}
    images_by_id = {i.iid: i for i in parsed.images}
    crops_dir = vault / ".pipeline" / "crops" / stem
    crops_dir.mkdir(parents=True, exist_ok=True)

    if ocr_client is None and not dry_run:
        ocr_client = ClaudeOcr()

    summary = {"new": 0, "changed": 0, "unchanged": 0, "moved": 0,
               "deleted": len(deleted), "edges": 0, "review": len(review),
               "ocr_calls": 0, "pending": 0, "dropped": 0}
    assets = {}
    dropped_bids = set()

    for d in decisions:
        summary[d.state] += 1
        if d.ocr is not None:
            source["boxes"][d.box_id]["ocr"] = d.ocr
            continue
        crop = render.render_box(d.box, strokes_by_id, images_by_id, svg_path, bg=bg)
        crop.save(crops_dir / f"{d.box_id}.png")
        over_limit = limit is not None and summary["ocr_calls"] >= limit
        if dry_run or over_limit:
            source["boxes"][d.box_id]["ocr"] = {
                "title": "", "text": "", "context": None, "pending": True}
            summary["pending"] += 1
            continue
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        try:
            r = ocr_client.transcribe(buf.getvalue())
            summary["ocr_calls"] += 1
        except OcrError as e:
            print(f"  OCR failed for {d.box_id}: {e}", file=sys.stderr)
            source["boxes"][d.box_id]["ocr"] = {
                "title": "", "text": "", "context": None, "pending": True}
            summary["pending"] += 1
            continue
        if not r.is_concept_box:
            dropped_bids.add(d.box_id)
            summary["dropped"] += 1
            continue
        source["boxes"][d.box_id]["ocr"] = {
            "title": r.title, "text": r.text, "context": r.context, "pending": False}
        for i, iid in enumerate(d.box.image_ids, start=1):
            ref = images_by_id[iid]
            img_data, img_ext = parse.load_image(svg_path, ref.def_id)
            assets.setdefault(d.box_id, []).append(
                (f"{d.box_id}_{i}.{img_ext}", img_data))

    for bid in dropped_bids:
        source["boxes"].pop(bid, None)
        # if this bid previously had a note (i.e. it wasn't newly created this
        # run), archive it the same way a truly-deleted box would be.
        if old_slugs.get(bid):
            deleted_slugs.append(old_slugs[bid])

    # Edge.src/dst index into `found`; reconcile stamped .box_id onto those
    # same Box objects, so the mapping is direct.
    id_edges = []
    for e in edge_list:
        s_bid = found[e.src].box_id
        d_bid = found[e.dst].box_id
        if s_bid in source["boxes"] and d_bid in source["boxes"]:
            id_edges.append((s_bid, d_bid, e.directed))
    summary["edges"] = len(id_edges)

    review_path = vault / ".pipeline" / "review.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        "# Ambiguous connectors\n\n" + "\n".join(f"- {m}" for m in review) + "\n",
        encoding="utf-8")

    emit.emit(vault, stem, source, id_edges, parsed.viewbox, json_path,
              assets, deleted_slugs)
    manifest.save(vault, data)

    cost = summary["ocr_calls"] * config.OCR_COST_ESTIMATE
    print(f"{stem}: +{summary['new']} new, ~{summary['changed']} changed, "
          f"={summary['unchanged']} unchanged, {summary['moved']} moved, "
          f"-{summary['deleted']} deleted, {summary['dropped']} dropped, "
          f"{summary['edges']} edges, {summary['review']} to review, "
          f"{summary['ocr_calls']} OCR calls (~${cost:.2f}), "
          f"{summary['pending']} pending")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingest/update a mindmap SVG into the vault.")
    ap.add_argument("svg")
    ap.add_argument("--vault", default=str(DEFAULT_VAULT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--bg", default=config.CROP_BG)
    args = ap.parse_args(argv)
    summary = run(args.svg, args.vault, dry_run=args.dry_run,
                  limit=args.limit, bg=args.bg)
    return 2 if summary["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
