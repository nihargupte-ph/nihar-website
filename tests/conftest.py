import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64

import pytest

_PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63f8cfc0f01f00050001ff89993d1d0000000049454e44ae426082"
    )
).decode()


def _stroke(sid, d, color="#ffcca9", width=0.6):
    return (
        f'<path id="STROKE_{sid}" opacity="1.000" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>'
    )


def _rect_d(x0, y0, x1, y1, gap=1.0):
    return (
        f"M {x0} {y0} L {x1} {y0} L {x1} {y1} L {x0} {y1} L {x0} {y0 + gap}"
    )


def _squiggle_d(x, y, n=6, step=4.0):
    parts = [f"M {x} {y}"]
    for i in range(n):
        parts.append(
            f"Q {x + step * (2 * i + 1)} {y + (8 if i % 2 else -8)} {x + step * (2 * i + 2)} {y}"
        )
    return " ".join(parts)


SYNTHETIC_SVG = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="500pt" height="400pt" version="1.1" viewBox="0 0 500 400">
<title>SYNTH</title>
<defs>
<image id="IMAGE_DEF_aaa" width="60" height="30" xlink:href="data:image/png;base64,{_PNG_1PX}"/>
</defs>
<g id="Image" opacity="1.000">
<g id="IMAGE_img1" opacity="1.000" transform="matrix(1.0 0.0 0.0 1.0 240.0 20.0)">
<use xlink:href="#IMAGE_DEF_aaa"/>
</g>
</g>
<g id="Pen" opacity="1.000">
{_stroke("boxA", _rect_d(10, 10, 120, 60))}
{_stroke("txtA1", _squiggle_d(20, 30, n=2, step=2.0))}
{_stroke("txtA2", _squiggle_d(45, 30, n=2, step=2.0))}
{_stroke("txtA3", _squiggle_d(70, 45, n=2, step=2.0))}
<circle id="STROKE_dotA" fill="#ffcca9" stroke="#ffcca9" stroke-width="0.1" cx="95" cy="45" r="0.4"/>
{_stroke("boxB", _rect_d(200, 10, 320, 70))}
{_stroke("txtB1", _squiggle_d(210, 60, n=2, step=2.0))}
{_stroke("boxC_top", "M 10 150 L 140 150")}
{_stroke("boxC_right", "M 140 150 L 140 210")}
{_stroke("boxC_bot", "M 140 210 L 10 210")}
{_stroke("boxC_left", "M 10 210 L 10 150")}
{_stroke("txtC1", _squiggle_d(30, 180, n=2, step=2.0))}
{_stroke("arrowAB", "M 122 35 L 198 35")}
{_stroke("headAB1", "M 192 30 L 198 35")}
{_stroke("headAB2", "M 192 40 L 198 35")}
{_stroke("lineBC", "M 250 72 L 100 148")}
{_stroke("decoy", _squiggle_d(400, 300, n=6, step=4.0))}
</g>
</svg>
"""


@pytest.fixture(scope="session")
def synthetic_svg(tmp_path_factory):
    p = tmp_path_factory.mktemp("svg") / "synth.svg"
    p.write_text(SYNTHETIC_SVG, encoding="utf-8")
    return p
