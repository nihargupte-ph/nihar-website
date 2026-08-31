#!/usr/bin/env bash
# Render channel animations as *candidates*: tools/manim/candidates/<id>-<variant>.mp4 + .png (still = last frame).
# Pick one per channel with tools/videopicker.py, which copies it into static/channels/media/<id>.{mp4,png}.
#   tools/manim/render.sh                      # all channels, variant 1
#   VARIANT=2 tools/manim/render.sh iso-ce     # one channel, variant 2 (scenes read style.VARIANT)
#   QUALITY=l tools/manim/render.sh …          # quick low-res preview (default m = 720p)
set -euo pipefail
cd "$(dirname "$0")"
OUT="$PWD/candidates"; mkdir -p "$OUT"
Q=${QUALITY:-m}; V=${VARIANT:-1}
ids=("$@"); [ ${#ids[@]} -eq 0 ] && ids=(iso-smt iso-ce iso-che cluster-ejected cluster-capture single-capture triples zkl-smbh agn)
for id in "${ids[@]}"; do
  mod="scene_${id//-/_}"; cls=$(grep -oE 'class \w+\(ChannelScene\)' "$mod.py" | head -1 | sed -E 's/class (\w+).*/\1/')
  rm -rf "media_out/videos/$mod"          # never pick up a stale render from another quality
  CH_VARIANT=$V micromamba run -n django-nihar-website manim render -q"$Q" --format=mp4 --media_dir ./media_out --disable_caching "$mod.py" "$cls" > /dev/null
  f=$(find media_out/videos/"$mod" -name "$cls.mp4" | head -1)
  ffmpeg -y -loglevel error -i "$f" -an -movflags +faststart -pix_fmt yuv420p -crf 26 "$OUT/$id-$V.mp4"
  ffmpeg -y -loglevel error -sseof -0.1 -i "$OUT/$id-$V.mp4" -frames:v 1 -update 1 "$OUT/$id-$V.png"
  echo "$id v$V -> $OUT/$id-$V.mp4 ($(du -h "$OUT/$id-$V.mp4" | cut -f1))"
done
