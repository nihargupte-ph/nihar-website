import json

from scripts.mindmap_vault import update
from scripts.mindmap_vault.model import OcrResult
from scripts.mindmap_vault.ocr import FakeOcr


# The synthetic fixture (post-R1) contains 3 boxes and 2 unboxed-region
# clusters. update.run's new pipeline order runs OCR decisions in
# combined = boxes + regions order, so a fully-fresh run needs 5 queued
# results: the 3 boxes first (Alpha/Beta/Gamma, same order as before), then
# the 2 regions (Delta/Epsilon, y-sorted — region A's cluster then region
# B's cluster per tests/conftest.py).
def _fake5():
    return FakeOcr([
        OcrResult("Alpha", "alpha text", True),
        OcrResult("Beta", "beta text $x^2$", True),
        OcrResult("Gamma", "gamma text", True),
        OcrResult("Delta", "delta text", True),
        OcrResult("Epsilon", "epsilon text", True),
    ])


def test_full_run_offline(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    summary = update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=json_out)
    assert summary["new"] == 5
    # arrowAB (A->B), lineBC (B-C), arrowAtoRegA (A-regionA, undirected).
    assert summary["edges"] == 3
    assert summary["pending"] == 0
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 5
    titles = {c["title"] for c in idx["concepts"]}
    assert titles == {"Alpha", "Beta", "Gamma", "Delta", "Epsilon"}
    notes = list((vault / "concepts").glob("*.md"))
    assert len(notes) == 5


def test_second_run_zero_ocr_and_stable_output(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=json_out)
    first = json_out.read_text()
    first_notes = {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")}

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert summary["unchanged"] == 5
    assert empty_fake.calls == 0
    assert json_out.read_text() == first
    assert {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")} == first_notes


def test_non_concept_box_dropped(synthetic_svg, tmp_path):
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),
        OcrResult("Gamma", "g", True),
        OcrResult("Delta", "d", True),
        OcrResult("Epsilon", "e", True),
    ])
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, tmp_path / "vault", ocr_client=fake,
                         json_path=json_out)
    assert summary["dropped"] == 1
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 4


def test_dry_run_marks_pending(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, vault, ocr_client=None,
                         json_path=json_out, dry_run=True)
    assert summary["pending"] == 5
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
        OcrResult("Delta", "d", True),
        OcrResult("Epsilon", "e", True),
    ])
    summary1 = update.run(synthetic_svg, vault, ocr_client=fake, json_path=json_out)
    assert summary1["dropped"] == 1

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary2 = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert empty_fake.calls == 0
    assert summary2["ocr_calls"] == 0
    assert summary2["pending"] == 0
    assert summary2["dropped"] == 0
    assert summary2["unchanged"] == 5
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 4


def test_dropped_box_edges_excluded(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),  # drops box B ("Beta"), which has 2 edges
        OcrResult("Gamma", "g", True),
        OcrResult("Delta", "d", True),
        OcrResult("Epsilon", "e", True),
    ])
    update.run(synthetic_svg, vault, ocr_client=fake, json_path=json_out)
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 4
    by_id = {c["id"]: c for c in idx["concepts"]}
    ids = set(by_id)
    for c in idx["concepts"]:
        # no dangling references to the dropped box
        assert set(c["links_out"]) <= ids
        assert set(c["links_in"]) <= ids
    # Both edges that touch box B ("Beta", arrowAB and lineBC) vanish with
    # it, so box A and box C lose their B-side links entirely. But box A's
    # separate edge to region A (arrowAtoRegA, undirected) doesn't touch box
    # B at all, so it must survive the drop. Undirected edges populate both
    # links_out and links_in on both endpoints (see
    # test_emit.test_undirected_links_both_ways), so b001<->r001 shows up
    # symmetrically on both sides.
    assert by_id["b001"]["links_out"] == ["r001"]
    assert by_id["b001"]["links_in"] == ["r001"]
    assert by_id["b003"]["links_out"] == []
    assert by_id["b003"]["links_in"] == []
    assert by_id["r001"]["links_in"] == ["b001"]
    assert by_id["r001"]["links_out"] == ["b001"]
    assert by_id["r002"]["links_out"] == []
    assert by_id["r002"]["links_in"] == []


def test_assets_namespaced_by_stem(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    stem = synthetic_svg.stem
    update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=json_out)
    written = list((vault / "assets").glob("*"))
    assert len(written) == 1
    assert written[0].name.startswith(f"{stem}_")
    # bare box-id names (the old, collision-prone scheme) must not appear
    assert not any(f.name.startswith("b0") for f in written)


def test_assets_exported_regardless_of_ocr_path(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    stem = synthetic_svg.stem

    # First pass: live OCR, box with an image gets its asset exported.
    update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=json_out)
    assets_dir = vault / "assets"
    first_written = list(assets_dir.glob("*"))
    assert len(first_written) == 1

    # Simulate the assets directory going missing, then re-run with a
    # fully-resolved manifest (zero OCR calls needed — every box is
    # "unchanged"). The reused-OCR path must still (re-)export the asset
    # instead of skipping it because no live OCR happened.
    for f in assets_dir.glob("*"):
        f.unlink()
    assert not list(assets_dir.glob("*"))

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert empty_fake.calls == 0
    assert summary["unchanged"] == 5
    re_written = list(assets_dir.glob("*"))
    assert len(re_written) == 1
    assert re_written[0].name == first_written[0].name


def test_lazy_ocr_client_not_constructed_when_fully_resolved(synthetic_svg, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    json_out = tmp_path / "i.json"
    # Resolve every box up front so the second pass below has zero OCR work.
    update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=json_out)

    class _ExplodingOcr:
        def __init__(self, *a, **k):
            raise AssertionError(
                "ClaudeOcr should not be constructed when no transcribe call "
                "is ever needed"
            )

    monkeypatch.setattr(update, "ClaudeOcr", _ExplodingOcr)
    # ocr_client=None + dry_run=False used to eagerly construct ClaudeOcr()
    # (requiring ANTHROPIC_API_KEY) even though every box is "unchanged" and
    # zero OCR calls happen. Construction must now be lazy.
    summary = update.run(synthetic_svg, vault, ocr_client=None, json_path=json_out,
                         dry_run=False)
    assert summary["ocr_calls"] == 0
    assert summary["pending"] == 0
    assert summary["unchanged"] == 5


def test_v1_backup(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "old_note.md").write_text("v1 content")
    update.run(synthetic_svg, vault, ocr_client=_fake5(), json_path=tmp_path / "i.json")
    backup = tmp_path / "vault_v1_backup"
    assert (backup / "old_note.md").read_text() == "v1 content"
    assert not (vault / "old_note.md").exists()
    assert (vault / ".pipeline" / "manifest.json").exists()
