import json

from scripts.mindmap_vault import apply_ocr, manifest, update
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
    assert len(box_ids) == 3

    results = {
        "source": stem,
        "results": [
            {"box_id": box_ids[0], "title": "Alpha", "text": "a",
             "is_concept_box": True, "context": None},
            {"box_id": box_ids[1], "title": "junk", "text": "",
             "is_concept_box": False, "context": None},
            {"box_id": box_ids[2], "title": "Gamma", "text": "g",
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
    assert titles == {"Alpha", "Gamma"}
    assert len(idx["concepts"]) == 2


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
