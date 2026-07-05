import types

import pytest

from scripts.mindmap_vault import ocr
from scripts.mindmap_vault.model import OcrResult


class _StubBlock:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class _StubMessages:
    def __init__(self, responses):
        self._responses = responses
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(content=[_StubBlock(r)])


def _client(responses):
    return types.SimpleNamespace(messages=_StubMessages(responses))


def test_transcribe_parses_tool_output():
    client = _client([{"title": "Bayes", "text": "$p(a|b)$", "is_concept_box": True}])
    o = ocr.ClaudeOcr(client=client)
    r = o.transcribe(b"png")
    assert r == OcrResult(title="Bayes", text="$p(a|b)$", is_concept_box=True, context=None)
    assert o.calls == 1
    req = client.messages.requests[0]
    assert req["model"] == "claude-sonnet-5"
    assert req["tool_choice"]["name"] == "record_transcription"


def test_transcribe_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    client = _client([RuntimeError("boom"),
                      {"title": "T", "text": "x", "is_concept_box": True}])
    r = ocr.ClaudeOcr(client=client).transcribe(b"png")
    assert r.title == "T"


def test_transcribe_raises_after_retries(monkeypatch):
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    client = _client([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    with pytest.raises(ocr.OcrError):
        ocr.ClaudeOcr(client=client).transcribe(b"png")


def test_fake_ocr_pops_in_order():
    f = ocr.FakeOcr([OcrResult("A", "a", True), OcrResult("B", "b", False)])
    assert f.transcribe(b"1").title == "A"
    assert f.transcribe(b"2").title == "B"
    assert f.calls == 2
