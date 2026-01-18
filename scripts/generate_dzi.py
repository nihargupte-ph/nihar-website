#!/usr/bin/env python3
"""
Generate Deep Zoom Image (DZI) tiles from large mindmap images.
Uses Pillow for image processing.

Usage:
    python scripts/generate_dzi.py physics
    python scripts/generate_dzi.py cs
"""

import os
import sys
import math
from PIL import Image

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_IMAGES = {
    'physics': os.path.join(BASE_DIR, 'static', 'images', 'physics.png'),
    'cs': os.path.join(BASE_DIR, 'static', 'images', 'cs.png'),
}
OUTPUT_DIR = os.path.join(BASE_DIR, 'static', 'mindmaps')

# Deep Zoom settings
TILE_SIZE = 256
OVERLAP = 1
TILE_FORMAT = 'jpg'
TILE_QUALITY = 85


def generate_dzi(mindmap_name: str) -> None:
    """Generate DZI tiles for a mindmap image."""

    if mindmap_name not in SOURCE_IMAGES:
        print(f"Error: Unknown mindmap '{mindmap_name}'")
        print(f"Available: {list(SOURCE_IMAGES.keys())}")
        sys.exit(1)

    source_path = SOURCE_IMAGES[mindmap_name]

    if not os.path.exists(source_path):
        print(f"Error: Source image not found: {source_path}")
        sys.exit(1)

    # Create output directories
    output_base = os.path.join(OUTPUT_DIR, mindmap_name)
    tiles_dir = os.path.join(output_base, f'{mindmap_name}_files')
    os.makedirs(tiles_dir, exist_ok=True)

    print(f"Loading image: {source_path}")
    print("This may take a moment for large images...")

    # Load image
    Image.MAX_IMAGE_PIXELS = None  # Allow large images
    img = Image.open(source_path)

    # Convert to RGB if necessary (for JPEG output)
    if img.mode in ('RGBA', 'P'):
        print("Converting to RGB...")
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    print(f"Image dimensions: {width} x {height}")

    # Calculate number of levels
    max_dimension = max(width, height)
    max_level = int(math.ceil(math.log2(max_dimension)))

    print(f"Generating {max_level + 1} zoom levels...")

    total_tiles = 0

    # Generate tiles for each level (from highest to lowest resolution)
    for level in range(max_level, -1, -1):
        # Calculate dimensions at this level
        scale = 2 ** (max_level - level)
        level_width = int(math.ceil(width / scale))
        level_height = int(math.ceil(height / scale))

        # Resize image for this level
        if level == max_level:
            level_img = img.copy()
        else:
            level_img = img.resize((level_width, level_height), Image.Resampling.LANCZOS)

        # Create level directory
        level_dir = os.path.join(tiles_dir, str(level))
        os.makedirs(level_dir, exist_ok=True)

        # Calculate number of tiles
        cols = int(math.ceil(level_width / TILE_SIZE))
        rows = int(math.ceil(level_height / TILE_SIZE))

        level_tiles = 0

        # Generate tiles
        for col in range(cols):
            for row in range(rows):
                # Calculate tile bounds with overlap
                x = col * TILE_SIZE
                y = row * TILE_SIZE

                # Add overlap (except at edges)
                x1 = x - OVERLAP if col > 0 else x
                y1 = y - OVERLAP if row > 0 else y
                x2 = min(x + TILE_SIZE + OVERLAP, level_width)
                y2 = min(y + TILE_SIZE + OVERLAP, level_height)

                # Crop tile
                tile = level_img.crop((x1, y1, x2, y2))

                # Save tile
                tile_path = os.path.join(level_dir, f'{col}_{row}.{TILE_FORMAT}')
                tile.save(tile_path, 'JPEG', quality=TILE_QUALITY)
                level_tiles += 1

        total_tiles += level_tiles
        print(f"  Level {level}: {level_width}x{level_height} ({cols}x{rows} = {level_tiles} tiles)")

    # Generate DZI descriptor file
    dzi_path = os.path.join(output_base, f'{mindmap_name}.dzi')
    dzi_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="{TILE_FORMAT}"
       Overlap="{OVERLAP}"
       TileSize="{TILE_SIZE}">
    <Size Width="{width}" Height="{height}"/>
</Image>
'''

    with open(dzi_path, 'w') as f:
        f.write(dzi_content)

    print(f"\nDone!")
    print(f"  Total tiles: {total_tiles}")
    print(f"  DZI file: {dzi_path}")
    print(f"  Tiles directory: {tiles_dir}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python generate_dzi.py <mindmap_name>")
        print("Example: python generate_dzi.py physics")
        sys.exit(1)

    generate_dzi(sys.argv[1])
