import json

import pytest

from scripts.mindmap_vault import apply_ocr, manifest, update
from scripts.mindmap_vault.model import OcrResult
from scripts.mindmap_vault.ocr import FakeOcr


def _dry_run_boxes(synthetic_svg, vault, json_out):
    update.run(synthetic_svg, vault, ocr_client=None, json_path=json_out, dry_run=True)
    data = manifest.load(vault)
    stem = synthetic_svg.stem
    return data, stem, sorted(data["sources"][stem]["boxes"])


def test_apply_ocr_happy_path(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    _, stem, box_ids = _dry_run_boxes(synthetic_svg, vault, json_out)
    assert len(box_ids) == 5

    results = {
        "source": stem,
        "results": [
            {"box_id": box_ids[0], "title": "Alpha", "text": "a",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[1], "title": "junk", "text": "",
             "is_concept_box": False, "context": None},
            {"box_id": box_ids[2], "title": "Gamma", "text": "g",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[3], "title": "Delta", "text": "d",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[4], "title": "Epsilon", "text": "e",
             "is_concept_box": True, "context": None},
        ],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")

    code = apply_ocr.main([str(results_path), "--vault", str(vault)])
    assert code == 0

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert empty_fake.calls == 0
    assert summary["pending"] == 0
    assert summary["ocr_calls"] == 0

    idx = json.loads(json_out.read_text())
    titles = {c["title"] for c in idx["concepts"]}
    assert titles == {"Alpha", "Gamma", "Delta", "Epsilon"}
    assert len(idx["concepts"]) == 4


def test_apply_ocr_unknown_id(synthetic_svg, tmp_path, capsys):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    _, stem, box_ids = _dry_run_boxes(synthetic_svg, vault, json_out)

    results = {
        "source": stem,
        "results": [
            {"box_id": box_ids[0], "title": "Alpha", "text": "a",
             "is_concept_box": True, "context": None},
            {"box_id": "bogus", "title": "x", "text": "",
             "is_concept_box": True, "context": None},
        ],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")

    code = apply_ocr.main([str(results_path), "--vault", str(vault)])
    assert code == 1
    err = capsys.readouterr().err
    assert "bogus" in err

    data2 = manifest.load(vault)
    assert data2["sources"][stem]["boxes"][box_ids[0]]["ocr"]["title"] == "Alpha"
    assert data2["sources"][stem]["boxes"][box_ids[0]]["ocr"]["pending"] is False


def test_apply_ocr_dropped_pending_placeholder_never_had_note(synthetic_svg, tmp_path):
    # A dry-run leaves every box pending: no slug is assigned and no note is
    # ever written for a pending record (title is empty, so a slug would
    # just be a meaningless "concept" placeholder). If apply_ocr later marks
    # one of those pending boxes dropped, there is no note to archive — it
    # never existed in the first place.
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    _, stem, box_ids = _dry_run_boxes(synthetic_svg, vault, json_out)

    dropped_id = box_ids[1]
    data = manifest.load(vault)
    slug = data["sources"][stem]["boxes"][dropped_id]["slug"]
    assert slug is None
    assert not list((vault / "concepts").glob("*.md"))

    # Resolve all five pending records (3 boxes + 2 regions) so the re-run
    # below has no remaining OCR work to do.
    results = {
        "source": stem,
        "results": [
            {"box_id": box_ids[0], "title": "Alpha", "text": "a",
             "is_concept_box": True, "context": None},
            {"box_id": dropped_id, "title": "junk", "text": "",
             "is_concept_box": False, "context": None},
            {"box_id": box_ids[2], "title": "Gamma", "text": "g",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[3], "title": "Delta", "text": "d",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[4], "title": "Epsilon", "text": "e",
             "is_concept_box": True, "context": None},
        ],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")
    code = apply_ocr.main([str(results_path), "--vault", str(vault)])
    assert code == 0

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)

    # Alpha, Gamma, Delta, Epsilon get real notes now that they've been
    # resolved, but the dropped box never had a note, so there is nothing to
    # archive.
    notes = {p.stem for p in (vault / "concepts").glob("*.md")}
    assert notes == {"alpha", "gamma", "delta", "epsilon"}
    assert not (vault / "concepts" / "_archived").exists()
    data2 = manifest.load(vault)
    assert data2["sources"][stem]["boxes"][dropped_id]["slug"] is None
    idx = json.loads(json_out.read_text())
    dropped_entry = [c for c in idx["concepts"] if c["id"] == dropped_id]
    assert dropped_entry == []


def test_apply_ocr_dropped_real_note_archives_note(synthetic_svg, tmp_path):
    # A full (non-dry-run) pass produces real notes with content for every
    # box. If apply_ocr later marks one of those already-real boxes
    # dropped, its existing note must be archived on the next run, and the
    # other real notes must be left untouched.
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("Beta", "beta text", True),
        OcrResult("Gamma", "g", True),
        OcrResult("Delta", "d", True),
        OcrResult("Epsilon", "e", True),
    ])
    update.run(synthetic_svg, vault, ocr_client=fake, json_path=json_out)

    data = manifest.load(vault)
    stem = synthetic_svg.stem
    box_ids = sorted(data["sources"][stem]["boxes"])
    beta_id = next(
        bid for bid in box_ids
        if data["sources"][stem]["boxes"][bid]["ocr"]["title"] == "Beta"
    )
    beta_slug = data["sources"][stem]["boxes"][beta_id]["slug"]
    assert (vault / "concepts" / f"{beta_slug}.md").exists()
    # Alpha/Gamma link to Beta in the fixture, so their note bodies will
    # legitimately lose the "→ [[beta]]" line once Beta is dropped — that's
    # not the bug under test here. Just track which other notes exist.
    other_note_names = {
        p.name for p in (vault / "concepts").glob("*.md") if p.stem != beta_slug
    }

    results = {
        "source": stem,
        "results": [
            {"box_id": beta_id, "title": "junk", "text": "",
             "is_concept_box": False, "context": None},
        ],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")
    code = apply_ocr.main([str(results_path), "--vault", str(vault)])
    assert code == 0

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)

    assert not (vault / "concepts" / f"{beta_slug}.md").exists()
    assert (vault / "concepts" / "_archived" / f"{beta_slug}.md").exists()
    assert {
        p.name for p in (vault / "concepts").glob("*.md")
    } == other_note_names
    idx = json.loads(json_out.read_text())
    assert beta_slug not in {c["slug"] for c in idx["concepts"]}


def test_apply_ocr_malformed_missing_results_key(synthetic_svg, tmp_path, capsys):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    _, stem, _ = _dry_run_boxes(synthetic_svg, vault, json_out)

    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps({"source": stem}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        apply_ocr.main([str(results_path), "--vault", str(vault)])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "results" in err
