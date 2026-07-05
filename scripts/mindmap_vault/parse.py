import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.mindmap_vault.geom import bbox_of
from scripts.mindmap_vault.model import ImageRef, Stroke

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TAG = re.compile(r"<g\b[^>]*>|</g>|<path\b[^>]*?>|<circle\b[^>]*?>|<use\b[^>]*?>")
_CMD = re.compile(r"([MLQ])([^MLQ]*)")


@dataclass
class ParseResult:
    strokes: list = field(default_factory=list)
    images: list = field(default_factory=list)
    viewbox: tuple = (0.0, 0.0, 0.0, 0.0)
    image_defs: dict = field(default_factory=dict)


def _attr(tag, name):
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def _sample_d(d):
    pts = []
    cur = None
    for m in _CMD.finditer(d):
        cmd = m.group(1)
        nums = [float(x) for x in _NUM.findall(m.group(2))]
        if cmd in ("M", "L"):
            for i in range(0, len(nums) - 1, 2):
                cur = (nums[i], nums[i + 1])
                pts.append(cur)
        elif cmd == "Q":
            for i in range(0, len(nums) - 3, 4):
                cx, cy, x, y = nums[i : i + 4]
                x0, y0 = cur
                pts.append(((x0 + 2 * cx + x) / 4.0, (y0 + 2 * cy + y) / 4.0))
                cur = (x, y)
                pts.append(cur)
    return pts


def _matrix_bbox(matrix, w, h):
    a, b, c, d, e, f = matrix
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    tx = [a * x + c * y + e for x, y in corners]
    ty = [b * x + d * y + f for x, y in corners]
    return (min(tx), min(ty), max(tx), max(ty))


def parse_svg(path):
    text = Path(path).read_text(encoding="utf-8")
    result = ParseResult()

    vb = re.search(r'viewBox="([^"]+)"', text[:3000])
    result.viewbox = tuple(float(v) for v in _NUM.findall(vb.group(1)))

    defs_end = text.find("</defs>")
    defs_end = 0 if defs_end < 0 else defs_end
    for m in re.finditer(r"<image\b[^>]*?>", text[:defs_end]):
        tag = m.group(0)
        did = _attr(tag, "id")
        if did:
            result.image_defs[did] = (float(_attr(tag, "width")), float(_attr(tag, "height")))

    stack = []  # (kind, name, matrix)
    layer = "root"
    for m in _TAG.finditer(text, defs_end):
        tag = m.group(0)
        if tag.startswith("</g"):
            if stack:
                stack.pop()
            layer = next((n for k, n, _ in reversed(stack) if k == "layer"), "root")
        elif tag.startswith("<g"):
            gid = _attr(tag, "id") or ""
            tr = _attr(tag, "transform")
            if gid.startswith("IMAGE_") and tr and tr.startswith("matrix("):
                matrix = tuple(float(v) for v in _NUM.findall(tr))
                stack.append(("image", gid, matrix))
            else:
                stack.append(("layer", gid, None))
                layer = gid
        elif tag.startswith("<use"):
            img = next(((n, mx) for k, n, mx in reversed(stack) if k == "image"), None)
            href = _attr(tag, "xlink:href") or _attr(tag, "href") or ""
            def_id = href.lstrip("#")
            if img and def_id in result.image_defs:
                w, h = result.image_defs[def_id]
                iid = img[0]
                if iid.startswith("IMAGE_"):
                    iid = iid[len("IMAGE_"):]
                result.images.append(
                    ImageRef(iid=iid, def_id=def_id, bbox=_matrix_bbox(img[1], w, h))
                )
        elif tag.startswith("<path"):
            sid = (_attr(tag, "id") or "")
            if not sid.startswith("STROKE_"):
                continue
            pts = _sample_d(_attr(tag, "d") or "")
            if len(pts) < 1:
                continue
            result.strokes.append(
                Stroke(
                    sid=sid[len("STROKE_"):],
                    points=pts,
                    bbox=bbox_of(pts),
                    color=_attr(tag, "stroke") or "#ffffff",
                    width=float(_attr(tag, "stroke-width") or 1.0),
                    layer=layer,
                )
            )
        elif tag.startswith("<circle"):
            sid = (_attr(tag, "id") or "")
            if not sid.startswith("STROKE_"):
                continue
            cx, cy = float(_attr(tag, "cx")), float(_attr(tag, "cy"))
            r = float(_attr(tag, "r"))
            result.strokes.append(
                Stroke(
                    sid=sid[len("STROKE_"):],
                    points=[(cx, cy)],
                    bbox=(cx - r, cy - r, cx + r, cy + r),
                    color=_attr(tag, "fill") or _attr(tag, "stroke") or "#ffffff",
                    width=r * 2,
                    layer=layer,
                    radius=r,
                )
            )
    return result


def load_image_png(path, def_id):
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(
        rf'<image id="{re.escape(def_id)}"[^>]*?href="data:image/[^;]+;base64,([^"]+)"',
        text,
    )
    if not m:
        raise KeyError(f"image def {def_id!r} not found in {path}")
    return base64.b64decode(m.group(1))
