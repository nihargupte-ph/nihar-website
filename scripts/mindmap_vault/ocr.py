import base64
import time

from scripts.mindmap_vault import config
from scripts.mindmap_vault.model import OcrResult


class OcrError(Exception):
    pass


_PROMPT = """This image is a crop of ONE hand-drawn concept box from a physics/CS research mindmap.
Transcribe the handwriting verbatim — do not paraphrase, expand, or correct it.
Use LaTeX ($...$) for equations and mathematical symbols.
- title: the box's heading (usually the first or most prominent line)
- text: the full transcription, preserving line breaks
- is_concept_box: false if this is NOT actually a concept box with handwritten notes
  (e.g. a stray mark, an underline, or a frame around a photo with no writing)
- context: at most ONE short sentence of clarification, ONLY if the transcription
  alone would be cryptic; otherwise omit it entirely."""

_TOOL = {
    "name": "record_transcription",
    "description": "Record the transcription of one handwritten concept box.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "text": {"type": "string"},
            "is_concept_box": {"type": "boolean"},
            "context": {"type": "string"},
        },
        "required": ["title", "text", "is_concept_box"],
    },
}


class ClaudeOcr:
    def __init__(self, client=None, model=config.OCR_MODEL):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.calls = 0

    def transcribe(self, png_bytes):
        last = None
        for attempt in range(config.OCR_RETRIES):
            try:
                self.calls += 1
                msg = self.client.messages.create(
                    model=self.model,
                    max_tokens=config.OCR_MAX_TOKENS,
                    tools=[_TOOL],
                    tool_choice={"type": "tool", "name": "record_transcription"},
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": "image/png",
                                "data": base64.b64encode(png_bytes).decode()}},
                            {"type": "text", "text": _PROMPT},
                        ],
                    }],
                )
                block = next(b for b in msg.content if b.type == "tool_use")
                d = block.input
                return OcrResult(
                    title=d["title"],
                    text=d["text"],
                    is_concept_box=bool(d["is_concept_box"]),
                    context=d.get("context") or None,
                )
            except Exception as e:  # noqa: BLE001 — retry any API failure
                last = e
                time.sleep(2 ** attempt)
        raise OcrError(f"OCR failed after {config.OCR_RETRIES} attempts: {last}")


class FakeOcr:
    """Test double: returns queued OcrResults in order."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def transcribe(self, png_bytes):
        self.calls += 1
        return self._results.pop(0)
