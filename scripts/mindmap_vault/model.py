from dataclasses import dataclass, field


@dataclass
class Stroke:
    sid: str
    points: list
    bbox: tuple
    color: str
    width: float
    layer: str
    radius: float = 0.0  # >0 for <circle> dot strokes


@dataclass
class ImageRef:
    iid: str
    def_id: str
    bbox: tuple


@dataclass
class Box:
    border_ids: list
    bbox: tuple
    member_ids: list = field(default_factory=list)
    image_ids: list = field(default_factory=list)
    box_id: str = ""


@dataclass
class Edge:
    src: int
    dst: int
    directed: bool
    stroke_ids: list = field(default_factory=list)


@dataclass
class OcrResult:
    title: str
    text: str
    is_concept_box: bool
    context: str | None = None
