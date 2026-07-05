import json

from scripts.mindmap_vault import emit


def _source():
    return {
        "next_box": 3,
        "boxes": {
            "b001": {"hash": "h1", "stroke_ids": ["a"], "bbox": [0, 0, 10, 10],
                     "slug": None,
                     "ocr": {"title": "Bayes Theorem", "text": "$p(a|b)p(b)=p(b|a)p(a)$",
                             "context": None, "pending": False}},
            "b002": {"hash": "h2", "stroke_ids": ["b"], "bbox": [20, 0, 30, 10],
                     "slug": None,
                     "ocr": {"title": "Prior", "text": "belief before data",
                             "context": "Refers to Bayesian priors.", "pending": False}},
        },
    }


def test_emit_writes_notes_and_json(tmp_path):
    vault = tmp_path / "vault"
    json_path = tmp_path / "cs-stat-index.json"
    src = _source()
    emit.emit(vault, "cs-stat", src, [("b001", "b002", True)],
              (0, 0, 500, 400), json_path, assets={}, deleted_slugs=[])

    note = (vault / "concepts" / "bayes_theorem.md").read_text()
    assert "id: cs-stat/b001" in note
    assert "# Bayes Theorem" in note
    assert "$p(a|b)p(b)=p(b|a)p(a)$" in note
    assert "→ [[prior]]" in note
    assert "*context:*" not in note

    prior = (vault / "concepts" / "prior.md").read_text()
    assert "*context:* Refers to Bayesian priors." in prior
    assert "→" not in prior  # no outgoing links

    idx = json.loads(json_path.read_text())
    assert idx["svg"] == "cs-stat.svg"
    assert idx["viewBox"] == [0, 0, 500, 400]
    c1 = next(c for c in idx["concepts"] if c["id"] == "b001")
    assert c1["links_out"] == ["b002"] and c1["links_in"] == []
    c2 = next(c for c in idx["concepts"] if c["id"] == "b002")
    assert c2["links_in"] == ["b001"] and c2["links_out"] == []

    assert src["boxes"]["b001"]["slug"] == "bayes_theorem"
    assert (vault / "mocs" / "cs-stat.md").exists()
    assert (vault / "index.md").exists()


def test_undirected_links_both_ways(tmp_path):
    src = _source()
    emit.emit(tmp_path / "v", "cs-stat", src, [("b001", "b002", False)],
              (0, 0, 500, 400), tmp_path / "i.json", assets={}, deleted_slugs=[])
    note1 = (tmp_path / "v" / "concepts" / "bayes_theorem.md").read_text()
    note2 = (tmp_path / "v" / "concepts" / "prior.md").read_text()
    assert "[[prior]]" in note1
    assert "[[bayes_theorem]]" in note2


def test_slug_stable_and_unique(tmp_path):
    src = _source()
    src["boxes"]["b002"]["slug"] = "bayes_theorem"  # simulate collision from earlier run
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1),
              tmp_path / "i.json", assets={}, deleted_slugs=[])
    assert src["boxes"]["b002"]["slug"] == "bayes_theorem"      # untouched
    assert src["boxes"]["b001"]["slug"] == "bayes_theorem_2"    # deduped


def test_archive_moves_note(tmp_path):
    vault = tmp_path / "v"
    src = _source()
    emit.emit(vault, "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={}, deleted_slugs=[])
    # reconcile would have removed the deleted record before emit runs again
    del src["boxes"]["b002"]
    emit.emit(vault, "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={}, deleted_slugs=["prior"])
    assert not (vault / "concepts" / "prior.md").exists()
    assert (vault / "concepts" / "_archived" / "prior.md").exists()


def test_pending_box_included_with_stub(tmp_path):
    src = _source()
    src["boxes"]["b001"]["ocr"] = None
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1),
              tmp_path / "i.json", assets={}, deleted_slugs=[])
    idx = json.loads((tmp_path / "i.json").read_text())
    c1 = next(c for c in idx["concepts"] if c["id"] == "b001")
    assert c1["title"] == "(pending OCR)"
    assert c1["slug"] is None
    assert src["boxes"]["b001"]["slug"] is None
    notes = {p.name: p.read_text() for p in (tmp_path / "v" / "concepts").glob("*.md")}
    assert not any("cs-stat/b001" in text for text in notes.values())


def test_assets_written(tmp_path):
    src = _source()
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={"b001": [("b001_1.png", b"\x89PNGdata")]}, deleted_slugs=[])
    assert (tmp_path / "v" / "assets" / "b001_1.png").read_bytes() == b"\x89PNGdata"
