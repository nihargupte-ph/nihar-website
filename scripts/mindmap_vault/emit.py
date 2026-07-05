import json
import re
from pathlib import Path

from scripts.mindmap_vault.manifest import _is_dropped


def _slugify(title, taken):
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "concept"
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}_{n}"
        n += 1
    return slug


def _assign_slugs(vault, source):
    concepts = Path(vault) / "concepts"
    taken = {p.stem for p in concepts.glob("*.md")} if concepts.exists() else set()
    taken |= {p.stem for p in (concepts / "_archived").glob("*.md")} if (concepts / "_archived").exists() else set()
    taken |= {
        rec["slug"] for rec in source["boxes"].values()
        if rec.get("slug") and not _is_dropped(rec)
    }
    for rec in source["boxes"].values():
        if _is_dropped(rec):
            # dropped records never get a note, so they never need a slug —
            # clear any stale slug from before the box was dropped.
            rec["slug"] = None
            continue
        if rec.get("slug"):
            continue
        title = (rec.get("ocr") or {}).get("title") or "concept"
        rec["slug"] = _slugify(title, taken)
        taken.add(rec["slug"])


def _link_maps(box_ids, edges):
    out = {b: [] for b in box_ids}
    inc = {b: [] for b in box_ids}
    for src_bid, dst_bid, directed in edges:
        if src_bid not in out or dst_bid not in out:
            continue
        out[src_bid].append(dst_bid)
        inc[dst_bid].append(src_bid)
        if not directed:
            out[dst_bid].append(src_bid)
            inc[src_bid].append(dst_bid)
    return out, inc


def _note(stem, bid, rec, out_slugs):
    ocr = rec.get("ocr") or {}
    pending = rec.get("ocr") is None or ocr.get("pending")
    title = "(pending OCR)" if pending else ocr["title"]
    text = "" if pending else ocr["text"]
    bbox = ", ".join(str(round(v, 1)) for v in rec["bbox"])
    lines = [
        "---",
        f"id: {stem}/{bid}",
        f"source: {stem}",
        f"bbox: [{bbox}]",
        "---",
        f"# {title}",
        "",
    ]
    if text:
        lines += [text, ""]
    if not pending and ocr.get("context"):
        lines += [f"*context:* {ocr['context']}", ""]
    if out_slugs:
        lines += ["→ " + " ".join(f"[[{s}]]" for s in out_slugs), ""]
    return "\n".join(lines)


def emit(vault, stem, source, edges, viewbox, json_path, assets, deleted_slugs):
    vault = Path(vault)
    concepts = vault / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    (vault / "mocs").mkdir(exist_ok=True)
    (vault / "assets").mkdir(exist_ok=True)

    archived = concepts / "_archived"
    for slug in deleted_slugs:
        src_file = concepts / f"{slug}.md"
        if src_file.exists():
            archived.mkdir(exist_ok=True)
            src_file.rename(archived / f"{slug}.md")

    _assign_slugs(vault, source)
    boxes = source["boxes"]
    active_ids = [bid for bid, rec in boxes.items() if not _is_dropped(rec)]
    out, inc = _link_maps(active_ids, edges)
    slug_of = {bid: boxes[bid]["slug"] for bid in active_ids}

    for bid in active_ids:
        rec = boxes[bid]
        out_slugs = [slug_of[t] for t in out[bid]]
        (concepts / f"{rec['slug']}.md").write_text(
            _note(stem, bid, rec, out_slugs), encoding="utf-8"
        )

    for bid, files in assets.items():
        for fname, data in files:
            (vault / "assets" / fname).write_bytes(data)

    moc = [f"# MOC — {stem}", "",
           f"Generated from `{stem}.svg` — {len(active_ids)} concepts, {len(edges)} edges.",
           "", "## Concepts", ""]
    moc += [f"- [[{boxes[bid]['slug']}]] ({bid})" for bid in sorted(active_ids)]
    moc += ["", "## Edges", ""]
    for src_bid, dst_bid, directed in edges:
        if src_bid in slug_of and dst_bid in slug_of:
            arrow = "→" if directed else "—"
            moc.append(f"- [[{slug_of[src_bid]}]] {arrow} [[{slug_of[dst_bid]}]]")
    (vault / "mocs" / f"{stem}.md").write_text("\n".join(moc) + "\n", encoding="utf-8")

    hub = ["# Index — classic_research", "",
           "Knowledge graph generated from handwritten mindmaps (Concepts app exports).", ""]
    for moc_file in sorted((vault / "mocs").glob("*.md")):
        hub.append(f"- [[mocs/{moc_file.stem}]]")
    (vault / "index.md").write_text("\n".join(hub) + "\n", encoding="utf-8")

    index = {
        "svg": f"{stem}.svg",
        "viewBox": list(viewbox),
        "concepts": [],
    }
    for bid in sorted(active_ids):
        rec = boxes[bid]
        ocr = rec.get("ocr") or {}
        pending = rec.get("ocr") is None or ocr.get("pending")
        index["concepts"].append({
            "id": bid,
            "slug": rec["slug"],
            "title": "(pending OCR)" if pending else ocr["title"],
            "text": "" if pending else ocr["text"],
            "context": None if pending else ocr.get("context"),
            "bbox": [round(v, 1) for v in rec["bbox"]],
            "links_out": out[bid],
            "links_in": inc[bid],
        })
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(index, indent=1), encoding="utf-8")
