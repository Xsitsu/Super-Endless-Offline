#!/usr/bin/env python3
"""
Convert an indexed-color .bmp into SNES-ready ca65 assembly:
  - a CGRAM color table (pallet.asm), converting the BMP's 8-bit-per-channel
    palette down to the SNES's 5-bit-per-channel 0bbbbbgggggrrrrr format
  - a packed pixel-index data block (character.asm), converting the BMP's
    on-disk bits-per-pixel down to a chosen SNES bits-per-pixel

The BMP's bpp (how many bits its own palette indices are stored in) and the
asm's target bpp (how many bits each packed pixel takes in the output data
block) are tracked separately and can differ - see PIXEL_BPP below.
"""

import struct
import sys
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
BMP_PATH = REPO_ROOT / "char.bmp"
PALLET_ASM_PATH = REPO_ROOT / "src" / "pallet.asm"
CHARACTER_ASM_PATH = REPO_ROOT / "src" / "character.asm"

# Bits per pixel to pack the output index data at. This is independent of
# the BMP's own on-disk bpp (queried from the file itself below) - e.g. a
# source BMP could be 8bpp/256-color while the target SNES graphics mode
# is only 4bpp/16-color, or vice versa. Must divide evenly into 8.
PIXEL_BPP = 4


def load_indexed_bmp(path):
    im = Image.open(path)
    if im.mode != "P":
        raise ValueError(f"{path} is not a palette-indexed BMP (mode={im.mode})")

    im.load()
    # Pillow doesn't expose the source BMP's bits-per-pixel on the Image object,
    # so read biBitCount straight out of the BITMAPINFOHEADER (offset 28, 2 bytes LE).
    with open(path, "rb") as f:
        header = f.read(30)
    (bmp_bpp,) = struct.unpack_from("<H", header, 28)

    width, height = im.size
    raw_palette = im.getpalette()  # flat [r,g,b, r,g,b, ...], 8 bits/channel
    num_colors = len(raw_palette) // 3
    palette = [tuple(raw_palette[i * 3:i * 3 + 3]) for i in range(num_colors)]

    pixels = list(im.getdata())  # row-major, top-to-bottom, one palette index per pixel

    max_index = max(pixels)
    if max_index >= (1 << bmp_bpp):
        raise ValueError(
            f"pixel index {max_index} does not fit in the BMP's reported {bmp_bpp}bpp"
        )

    return width, height, bmp_bpp, palette, pixels


def channel_8_to_5(value8):
    # Truncate 8-bit (0-255) channel down to SNES's 5-bit (0-31) channel.
    return value8 >> 3


def to_snes_color(rgb):
    r, g, b = rgb
    r5 = channel_8_to_5(r)
    g5 = channel_8_to_5(g)
    b5 = channel_8_to_5(b)
    # AGENTS.md: colors are 2 bytes, _bbbbbgggggrrrrr (bit 15 unused)
    return (b5 << 10) | (g5 << 5) | r5


def pack_pixels(pixels, bpp):
    """Pack a stream of palette-index pixels into bytes at `bpp` bits/pixel.
    Pixels per byte are packed MSB-first (the first pixel in a group lands
    in the high bits of the byte)."""
    if 8 % bpp != 0:
        raise ValueError(f"PIXEL_BPP={bpp} must divide evenly into 8")

    max_index = (1 << bpp) - 1
    for p in pixels:
        if p > max_index:
            raise ValueError(
                f"pixel index {p} does not fit in target PIXEL_BPP={bpp} "
                f"(max {max_index}) - raise PIXEL_BPP or remap the palette"
            )

    pixels_per_byte = 8 // bpp
    packed = bytearray()
    for i in range(0, len(pixels), pixels_per_byte):
        chunk = pixels[i:i + pixels_per_byte]
        chunk += [0] * (pixels_per_byte - len(chunk))  # pad final byte if needed
        byte = 0
        for j, index in enumerate(chunk):
            shift = 8 - bpp * (j + 1)
            byte |= (index & max_index) << shift
        packed.append(byte)
    return bytes(packed)


def write_pallet_asm(path, palette, bmp_bpp):
    lines = []
    lines.append("; Init pallets")
    lines.append("")
    lines.append(".include \"macros.inc\"")
    lines.append("")
    lines.append("")
    lines.append(".macro pallet_16")
    lines.append("\tlda $f0")
    lines.append("\tsts CGADD")
    lines.append("")
    lines.append(".endmacro")
    lines.append("")
    lines.append("")
    lines.append(".segment \"CODE\"")
    lines.append("")
    lines.append(f"; Color palette extracted from char.bmp ({len(palette)} colors, "
                  f"{bmp_bpp} bits/pixel in the source BMP).")
    lines.append("; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr")
    lines.append("; (8-bit BMP channels are truncated down to 5 bits each.)")
    lines.append("pallet_char:")
    for i, rgb in enumerate(palette):
        word = to_snes_color(rgb)
        r, g, b = rgb
        lines.append(f"\t.word ${word:04x} ; {i:2d}: bmp rgb=({r:3d},{g:3d},{b:3d})")
    lines.append("pallet_char_end:")
    lines.append("")
    lines.append("pallet_char_size = pallet_char_end - pallet_char")
    lines.append("")

    path.write_text("\n".join(lines))


def write_character_asm(path, packed, width, height, pixel_bpp, num_colors):
    lines = []
    lines.append("; Routine for loading in character sprite data")
    lines.append("")
    lines.append(".include \"macros.inc\"")
    lines.append("")
    lines.append(".segment \"CODE\"")
    lines.append("")
    lines.append(f"; Character pixel data, auto-generated from char.bmp by tools/bmp2asm.py")
    lines.append(f"; {width} x {height} pixels, {pixel_bpp} bits/pixel, indices into pallet_char "
                  f"(src/pallet.asm, {num_colors} colors).")
    lines.append(f"; Packed {8 // pixel_bpp} pixel(s) per byte, first pixel in the high bits, "
                  "row-major starting from the top-left pixel.")
    lines.append("char_width  = " + str(width))
    lines.append("char_height = " + str(height))
    lines.append("char_pixel_bpp = " + str(pixel_bpp))
    lines.append("")
    lines.append("char_data:")

    bytes_per_line = 16
    for i in range(0, len(packed), bytes_per_line):
        chunk = packed[i:i + bytes_per_line]
        byte_str = ",".join(f"${b:02x}" for b in chunk)
        lines.append(f"\t.byte {byte_str}")
    lines.append("char_data_end:")
    lines.append("")
    lines.append("char_data_size = char_data_end - char_data")
    lines.append("")

    path.write_text("\n".join(lines))


def main():
    width, height, bmp_bpp, palette, pixels = load_indexed_bmp(BMP_PATH)
    used_colors = max(pixels) + 1
    print(f"{BMP_PATH.name}: {width}x{height}, bmp_bpp={bmp_bpp}, "
          f"{len(palette)} palette entries, {used_colors} used by pixel data")

    packed = pack_pixels(pixels, PIXEL_BPP)
    print(f"packed {len(pixels)} pixels at {PIXEL_BPP}bpp -> {len(packed)} bytes")

    write_pallet_asm(PALLET_ASM_PATH, palette, bmp_bpp)
    write_character_asm(CHARACTER_ASM_PATH, packed, width, height, PIXEL_BPP, len(palette))
    print(f"wrote {PALLET_ASM_PATH}")
    print(f"wrote {CHARACTER_ASM_PATH}")


if __name__ == "__main__":
    sys.exit(main())
