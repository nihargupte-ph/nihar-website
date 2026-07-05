import io

from PIL import Image, ImageDraw

from scripts.mindmap_vault import config, parse
from scripts.mindmap_vault.geom import bbox_expand


def render_box(box, strokes_by_id, images_by_id, svg_path, bg=config.CROP_BG):
    x0, y0, x1, y1 = bbox_expand(box.bbox, config.CROP_MARGIN)
    w, h = x1 - x0, y1 - y0
    scale = min(config.CROP_TARGET_W / w, config.CROP_MAX_H / h, config.CROP_MAX_SCALE)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)

    def to_px(p):
        return ((p[0] - x0) * scale, (p[1] - y0) * scale)

    for iid in box.image_ids:
        ref = images_by_id[iid]
        bio = io.BytesIO(parse.load_image_png(svg_path, ref.def_id))
        png = Image.open(bio)
        png = png.convert("RGB")  # Force conversion/load before BytesIO scope ends
        bx0, by0 = to_px((ref.bbox[0], ref.bbox[1]))
        bx1, by1 = to_px((ref.bbox[2], ref.bbox[3]))
        tw, th = max(1, round(bx1 - bx0)), max(1, round(by1 - by0))
        img.paste(png.resize((tw, th)), (round(bx0), round(by0)))

    for sid in list(box.border_ids) + list(box.member_ids):
        s = strokes_by_id[sid]
        if s.radius > 0:
            cx, cy = to_px(s.points[0])
            r = max(1.0, s.radius * scale)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=s.color)
        elif len(s.points) >= 2:
            draw.line(
                [to_px(p) for p in s.points],
                fill=s.color,
                width=max(2, round(s.width * scale)),
                joint="curve",
            )
    return img
