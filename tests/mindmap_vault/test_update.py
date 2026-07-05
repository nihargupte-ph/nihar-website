import json

from scripts.mindmap_vault import update
from scripts.mindmap_vault.model import OcrResult
from scripts.mindmap_vault.ocr import FakeOcr


def _fake3():
    return FakeOcr([
        OcrResult("Alpha", "alpha text", True),
        OcrResult("Beta", "beta text $x^2$", True),
        OcrResult("Gamma", "gamma text", True),
    ])


def test_full_run_offline(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    summary = update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=json_out)
    assert summary["new"] == 3
    assert summary["edges"] == 2
    assert summary["pending"] == 0
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 3
    titles = {c["title"] for c in idx["concepts"]}
    assert titles == {"Alpha", "Beta", "Gamma"}
    notes = list((vault / "concepts").glob("*.md"))
    assert len(notes) == 3


def test_second_run_zero_ocr_and_stable_output(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=json_out)
    first = json_out.read_text()
    first_notes = {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")}

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert summary["unchanged"] == 3
    assert empty_fake.calls == 0
    assert json_out.read_text() == first
    assert {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")} == first_notes


def test_non_concept_box_dropped(synthetic_svg, tmp_path):
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),
        OcrResult("Gamma", "g", True),
    ])
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, tmp_path / "vault", ocr_client=fake,
                         json_path=json_out)
    assert summary["dropped"] == 1
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 2


def test_dry_run_marks_pending(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, vault, ocr_client=None,
                         json_path=json_out, dry_run=True)
    assert summary["pending"] == 3
    assert summary["ocr_calls"] == 0
    idx = json.loads(json_out.read_text())
    assert all(c["title"] == "(pending OCR)" for c in idx["concepts"])
    assert all(c["slug"] is None for c in idx["concepts"])
    assert not list((vault / "concepts").glob("*.md"))


def test_dropped_persists_and_skips_reocr(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),
        OcrResult("Gamma", "g", True),
    ])
    summary1 = update.run(synthetic_svg, vault, ocr_client=fake, json_path=json_out)
    assert summary1["dropped"] == 1

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary2 = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert empty_fake.calls == 0
    assert summary2["ocr_calls"] == 0
    assert summary2["pending"] == 0
    assert summary2["dropped"] == 0
    assert summary2["unchanged"] == 3
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 2


def test_dropped_box_edges_excluded(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),  # drops box B ("Beta"), which has 2 edges
        OcrResult("Gamma", "g", True),
    ])
    update.run(synthetic_svg, vault, ocr_client=fake, json_path=json_out)
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 2
    ids = {c["id"] for c in idx["concepts"]}
    for c in idx["concepts"]:
        # no dangling references to the dropped box
        assert set(c["links_out"]) <= ids
        assert set(c["links_in"]) <= ids
        # both real edges in the fixture touch the dropped box, so nothing survives
        assert c["links_out"] == []
        assert c["links_in"] == []


def test_v1_backup(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "old_note.md").write_text("v1 content")
    update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=tmp_path / "i.json")
    backup = tmp_path / "vault_v1_backup"
    assert (backup / "old_note.md").read_text() == "v1 content"
    assert not (vault / "old_note.md").exists()
    assert (vault / ".pipeline" / "manifest.json").exists()
