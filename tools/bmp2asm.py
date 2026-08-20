#!/usr/bin/env python3
"""
Convert an indexed-color .bmp into SNES-ready ca65 assembly:
  - a CGRAM color table (pallet.asm), converting the BMP's 8-bit-per-channel
    palette down to the SNES's 5-bit-per-channel 0bbbbbgggggrrrrr format
  - sprite character (tile) data (character.asm), converting the BMP's pixels
    into the SNES's planar 4bpp OAM tile format, plus a table describing how
    to lay the tiles out on screen as 16x16 OAM sprites

The BMP's bpp (how many bits its own palette indices are stored in) and the
asm's target bpp (how many bitplanes each tile is packed with) are tracked
separately and can differ - see PIXEL_BPP below.
"""

import colorsys
import struct
import sys
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
BMP_PATH = REPO_ROOT / "game_final_assets" / "male_face_down.bmp"
PALLET_ASM_PATH = REPO_ROOT / "src" / "pallet.asm"
CHARACTER_ASM_PATH = REPO_ROOT / "src" / "character.asm"

# Extra sprite palettes (colors only, no tile data) that get cycled through at
# runtime by the timer in main.asm's nmi handler - see pallet_table and
# load_char_pallet below.
#
# These are *derived* from pallet_char itself (via derive_pallet_variant)
# rather than read from separate BMPs: the only other skin-tone-recolor BMPs
# in the asset library (male_1.bmp/male_2.bmp) turned out to be a different
# pose/composition than male_face_down.bmp, not a recolor of it, so swapping
# their palettes onto male_face_down's pixel data produced a mismatched
# result no index-remapping could fix. Deriving from pallet_char guarantees
# the variant always matches the on-screen sprite.
PALLET_VARIANTS = [
    # (name, hue_shift_degrees, saturation_scale, value_scale)
    ("pallet_char_1", -18, 1.05, 0.92),  # deeper/tanner
    ("pallet_char_2", 18, 0.85, 1.05),   # paler/golden
]

# Bits per pixel (bitplanes) to pack each output tile with. This is
# independent of the BMP's own on-disk bpp (queried from the file itself
# below) - e.g. a source BMP could be 8bpp/256-color while the target SNES
# graphics mode is only 4bpp/16-color, or vice versa. Must be even (SNES
# planar tiles are built from pairs of interleaved bitplanes) and divide
# evenly into 8.
PIXEL_BPP = 4

# The SNES sprite character table is always addressed as if it were a sheet
# 16 tiles wide - a 16x16 OAM sprite's four 8x8 tiles are tile numbers
# c, c+1, c+0x10, c+0x11. So every row of tiles we generate must be padded
# out to 16 tiles even though our sheet is narrower than that.
TABLE_WIDTH_TILES = 16

TILE_SIZE = 8


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


def derive_pallet_variant(base_palette, hue_shift_deg, sat_scale, val_scale, gray_threshold=0.12):
    """Build a recolor variant of base_palette by rotating hue (and scaling
    saturation/value) of its non-grayscale entries, in HSV space. Near-gray
    entries (outlines, eye whites, underwear, etc. - saturation below
    gray_threshold) are left untouched, so only the skin-tone ramp shifts and
    the sprite's structural colors stay put."""
    out = []
    for r, g, b in base_palette:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < gray_threshold:
            out.append((r, g, b))
            continue
        h = (h + hue_shift_deg / 360.0) % 1.0
        s = max(0.0, min(1.0, s * sat_scale))
        v = max(0.0, min(1.0, v * val_scale))
        nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
        out.append((round(nr * 255), round(ng * 255), round(nb * 255)))
    return out


def split_into_tiles(pixels, width, height):
    """Split a row-major flat list of palette-index pixels into 8x8 tiles,
    in left-to-right, top-to-bottom tile order. Returns (tiles, tiles_x,
    tiles_y), where each tile is a list of 8 rows of 8 pixel indices."""
    if width % TILE_SIZE != 0 or height % TILE_SIZE != 0:
        raise ValueError(f"{width}x{height} is not a multiple of {TILE_SIZE}x{TILE_SIZE}")

    tiles_x = width // TILE_SIZE
    tiles_y = height // TILE_SIZE
    tiles = []
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            rows = []
            for y in range(TILE_SIZE):
                row_start = (ty * TILE_SIZE + y) * width + tx * TILE_SIZE
                rows.append(pixels[row_start:row_start + TILE_SIZE])
            tiles.append(rows)
    return tiles, tiles_x, tiles_y


def tile_to_planar(tile_pixels, bpp):
    """Convert an 8x8 block of palette-index pixels into the SNES's planar
    tile format: `bpp` bitplanes, interleaved two at a time (16 bytes per
    plane-pair: 2 bytes/row, low plane of the pair first). E.g. at 4bpp,
    planes 0&1 are stored as 16 bytes, followed by planes 2&3 as 16 more."""
    if bpp % 2 != 0:
        raise ValueError(f"bpp={bpp} must be even (planes are interleaved in pairs)")

    max_index = (1 << bpp) - 1
    out = bytearray(TILE_SIZE * bpp)
    for plane_pair in range(bpp // 2):
        base = plane_pair * 2 * TILE_SIZE
        for row in range(TILE_SIZE):
            lo = hi = 0
            for col in range(TILE_SIZE):
                index = tile_pixels[row][col]
                if index > max_index:
                    raise ValueError(
                        f"pixel index {index} does not fit in target PIXEL_BPP={bpp} "
                        f"(max {max_index}) - raise PIXEL_BPP or remap the palette"
                    )
                bit = 7 - col
                if index & (1 << (plane_pair * 2)):
                    lo |= (1 << bit)
                if index & (1 << (plane_pair * 2 + 1)):
                    hi |= (1 << bit)
            out[base + row * 2] = lo
            out[base + row * 2 + 1] = hi
    return bytes(out)


def pack_char_table(tiles, tiles_x, tiles_y, bpp):
    """Lay tiles out row-major into a TABLE_WIDTH_TILES-wide character
    table, padding each row out with blank tiles so that VRAM tile numbers
    follow the sheet's real 6-wide layout while still landing 16 (0x10)
    tiles apart per row, as the 16x16 OAM hardware requires."""
    blank_tile = bytes(TILE_SIZE * bpp)
    packed = bytearray()
    for ty in range(tiles_y):
        for tx in range(TABLE_WIDTH_TILES):
            if tx < tiles_x:
                packed += tile_to_planar(tiles[ty * tiles_x + tx], bpp)
            else:
                packed += blank_tile
    return bytes(packed)


def build_sprite_info(tiles_x, tiles_y):
    """Every 16x16 OAM sprite covers a 2x2 block of 8x8 tiles. Build the
    (dx, dy, first-tile-number) for each such block needed to cover the
    whole sheet, in row-major order. first-tile-number is the tile number
    of the block's top-left 8x8 tile within the padded character table."""
    if tiles_x % 2 != 0 or tiles_y % 2 != 0:
        raise ValueError(f"{tiles_x}x{tiles_y} tiles is not divisible into 16x16 sprites")

    quads_x = tiles_x // 2
    quads_y = tiles_y // 2
    info = []
    for qy in range(quads_y):
        for qx in range(quads_x):
            dx = qx * 16
            dy = qy * 16
            tile = (qy * 2) * TABLE_WIDTH_TILES + (qx * 2)
            info.append((dx, dy, tile))
    return info, quads_x, quads_y


def write_pallet_asm(path, pallets):
    """pallets is a list of (asm_name, source_comment_lines, palette) tuples.
    The first entry is the primary pallet (pallet_char) - its bank and color
    count set the DMA parameters shared by every pallet, since they must all
    be the same size (16 colors) to be interchangeable at runtime."""
    primary_name, _, primary_palette = pallets[0]

    lines = []
    lines.append("; Init pallets")
    lines.append("")
    lines.append(".segment \"CODE\"")
    lines.append("")

    for name, source_comment_lines, palette in pallets:
        if len(palette) != len(primary_palette):
            raise ValueError(
                f"{name} has {len(palette)} colors, expected "
                f"{len(primary_palette)} to match {primary_name}"
            )
        lines.extend(source_comment_lines)
        lines.append(f"{name}:")
        for i, rgb in enumerate(palette):
            word = to_snes_color(rgb)
            r, g, b = rgb
            lines.append(f"\t.word ${word:04x} ; {i:2d}: rgb=({r:3d},{g:3d},{b:3d})")
        lines.append(f"{name}_end:")
        lines.append("")
        lines.append(f"{name}_size = {name}_end - {name}")
        lines.append("")

    lines.append("; Fourth pallet slot for the cycling timer in main.asm - deliberately not")
    lines.append("; backed by its own BMP, so it aliases whatever bytes happen to follow the")
    lines.append(f"; last real pallet ({pallets[-1][0]}) in ROM.")
    lines.append(f"{primary_name}_3 = {pallets[-1][0]}_end")
    lines.append("")

    lines.append("; The pallets the per-second timer in main.asm's nmi handler rotates the")
    lines.append("; sprite through. Low words only - every pallet here lives in the same "
                  f"bank as {primary_name}.")
    lines.append("pallet_table:")
    for name, _, _ in pallets:
        lines.append(f"\t.word .loword({name})")
    lines.append(f"\t.word .loword({primary_name}_3)")
    lines.append("pallet_table_end:")
    lines.append("")
    lines.append("pallet_table_count = (pallet_table_end - pallet_table) / 2")
    lines.append("")

    lines.append("; Loads pallet_table[A] (A = pallet index, 8-bit) into CGRAM as sprite")
    lines.append("; palette 0 (colors 128-143). Call during forced blank or v-blank.")
    lines.append("; Assumes/leaves A8 XY16 (see init.asm).")
    lines.append("load_char_pallet:")
    lines.append("\tpha                 ; stash the index while we set CGADD")
    lines.append("\tlda #128            ; CGRAM color index 128 = sprite palette 0, color 0")
    lines.append("\tsta CGADD")
    lines.append("")
    lines.append("\tpla")
    lines.append("\tasl a               ; index -> byte offset into pallet_table")
    lines.append("\trep #$20            ; A16 (high byte is stale - mask it below)")
    lines.append("\tand #$00ff")
    lines.append("\ttax")
    lines.append("\tlda pallet_table,x")
    lines.append("\tsta A1T1L")
    lines.append(f"\tlda #{primary_name}_size ; every pallet is the same size")
    lines.append("\tsta DAS1L")
    lines.append("")
    lines.append("\tsetA8")
    lines.append(f"\tlda #^{primary_name}")
    lines.append("\tsta A1B1")
    lines.append("\tlda #$22            ; CGDATA")
    lines.append("\tsta BBAD1")
    lines.append("\tlda #$00            ; mode 0: write 1 byte per src, increment src addr")
    lines.append("\tsta DMAP1")
    lines.append("\tlda #$02            ; enable DMA channel 1")
    lines.append("\tsta MDMAEN")
    lines.append("\trts")
    lines.append("")

    path.write_text("\n".join(lines))


def write_character_asm(path, packed, width, height, tiles_x, tiles_y, pixel_bpp,
                         num_colors, sprite_info, quads_x, quads_y):
    lines = []
    lines.append("; Routine for loading in character sprite data")
    lines.append("")
    lines.append(".segment \"CODE\"")
    lines.append("")
    lines.append(f"; Character tile data, auto-generated from {BMP_PATH.name} by tools/bmp2asm.py")
    lines.append(f"; {width} x {height} pixels ({tiles_x} x {tiles_y} tiles), {pixel_bpp} bits/pixel, "
                  f"indices into pallet_char (src/pallet.asm, {num_colors} colors).")
    lines.append("; Packed as SNES-native planar OAM tiles, padded out to a "
                  f"{TABLE_WIDTH_TILES}-tile-wide character table (see docs/sprites.md) -")
    lines.append("; i.e. row-major tiles, each row padded with blank tiles out to "
                  f"{TABLE_WIDTH_TILES} so that VRAM tile numbers land {TABLE_WIDTH_TILES} (0x10)")
    lines.append("; apart per row, as required by the 16x16 OAM hardware.")
    lines.append("char_width  = " + str(width))
    lines.append("char_height = " + str(height))
    lines.append("char_tiles_x = " + str(tiles_x))
    lines.append("char_tiles_y = " + str(tiles_y))
    lines.append("char_pixel_bpp = " + str(pixel_bpp))
    lines.append("")
    lines.append("; VRAM word address the tile sheet below must be loaded at - must match")
    lines.append("; the Base bits configured in OBSEL.")
    lines.append("char_vram_addr = $0000")
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
    lines.append("; Loads char_data into VRAM as the sprite character table (OBSEL Base=0).")
    lines.append("; Call during forced blank. Assumes/leaves A8 XY16 (see init.asm).")
    lines.append("load_char_gfx:")
    lines.append("\tlda #$80            ; increment VRAM address after writing VMDATAH")
    lines.append("\tsta VMAIN")
    lines.append("")
    lines.append("\tsetAXY16")
    lines.append("\tlda #char_vram_addr")
    lines.append("\tsta VMADDL")
    lines.append("\tldx #.loword(char_data)")
    lines.append("\tstx A1T0L")
    lines.append("\tldx #char_data_size")
    lines.append("\tstx DAS0L")
    lines.append("")
    lines.append("\tsetA8")
    lines.append("\tlda #^char_data")
    lines.append("\tsta A1B0")
    lines.append("\tlda #$18            ; VMDATAL")
    lines.append("\tsta BBAD0")
    lines.append("\tlda #$01            ; mode 1: write 2 bytes (L,H) per src pair, increment src addr")
    lines.append("\tsta DMAP0")
    lines.append("\tlda #$01            ; enable DMA channel 0")
    lines.append("\tsta MDMAEN")
    lines.append("\trts")
    lines.append("")

    lines.append(f"; One (dx, dy, tile) triple per 16x16 OAM sprite needed to cover the whole")
    lines.append(f"; character ({quads_x} x {quads_y} = {len(sprite_info)} sprites), row-major.")
    lines.append("; dx/dy are pixel offsets from the character's top-left corner; tile is the")
    lines.append("; first-tile-number to put in OAM (see docs/sprites.md).")
    lines.append("char_sprite_info:")
    for dx, dy, tile in sprite_info:
        lines.append(f"\t.byte {dx}, {dy}, ${tile:02x}")
    lines.append("char_sprite_info_end:")
    lines.append("")
    lines.append("char_sprite_info_size = char_sprite_info_end - char_sprite_info")
    lines.append("")
    lines.append("; Writes OAM entries for the char_sprite_info grid, placed on screen with")
    lines.append("; its top-left corner at (char_x, char_y). Hides all other OAM sprites.")
    lines.append("; Call during forced blank. Assumes/leaves A8 XY16 (see init.asm).")
    lines.append("char_x = 104")
    lines.append("char_y = 80")
    lines.append("")
    lines.append("draw_char_sprites:")
    lines.append("\tstz OAMADDL")
    lines.append("\tstz OAMADDH")
    lines.append("")
    lines.append("\tldx #0")
    lines.append("sprite_loop:")
    lines.append("\tlda char_sprite_info,x   ; dx")
    lines.append("\tclc")
    lines.append("\tadc #char_x")
    lines.append("\tsta OAMDATA              ; X position")
    lines.append("\tlda char_sprite_info+1,x ; dy")
    lines.append("\tclc")
    lines.append("\tadc #char_y")
    lines.append("\tsta OAMDATA              ; Y position")
    lines.append("\tlda char_sprite_info+2,x ; first tile number")
    lines.append("\tsta OAMDATA")
    lines.append("\tlda #$00                 ; palette 0, priority 0, no flip, name table 0")
    lines.append("\tsta OAMDATA")
    lines.append("\tinx")
    lines.append("\tinx")
    lines.append("\tinx")
    lines.append("\tcpx #char_sprite_info_size")
    lines.append("\tbne sprite_loop")
    lines.append("")
    lines.append(f"\tldx #({len(sprite_info)} * 4)")
    lines.append("hide_loop:")
    lines.append("\tlda #$00")
    lines.append("\tsta OAMDATA              ; X position")
    lines.append("\tlda #$f0")
    lines.append("\tsta OAMDATA              ; Y position = 240, off the bottom edge")
    lines.append("\tlda #$00")
    lines.append("\tsta OAMDATA              ; tile")
    lines.append("\tsta OAMDATA              ; attr")
    lines.append("\tinx")
    lines.append("\tinx")
    lines.append("\tinx")
    lines.append("\tinx")
    lines.append("\tcpx #(128 * 4)")
    lines.append("\tbne hide_loop")
    lines.append("")
    lines.append("\tstz OAMADDL")
    lines.append("\tlda #$01")
    lines.append("\tsta OAMADDH              ; OAM high table starts at byte 512")
    lines.append("")
    lines.append("\tldx #0")
    lines.append("zero_high_loop:")
    lines.append("\tstz OAMDATA")
    lines.append("\tinx")
    lines.append("\tcpx #32")
    lines.append("\tbne zero_high_loop")
    lines.append("\trts")
    lines.append("")

    path.write_text("\n".join(lines))


def main():
    width, height, bmp_bpp, palette, pixels = load_indexed_bmp(BMP_PATH)
    used_colors = max(pixels) + 1
    print(f"{BMP_PATH.name}: {width}x{height}, bmp_bpp={bmp_bpp}, "
          f"{len(palette)} palette entries, {used_colors} used by pixel data")

    tiles, tiles_x, tiles_y = split_into_tiles(pixels, width, height)
    packed = pack_char_table(tiles, tiles_x, tiles_y, PIXEL_BPP)
    print(f"packed {tiles_x}x{tiles_y} tiles at {PIXEL_BPP}bpp, padded to "
          f"{TABLE_WIDTH_TILES}-wide -> {len(packed)} bytes")

    sprite_info, quads_x, quads_y = build_sprite_info(tiles_x, tiles_y)
    print(f"{quads_x}x{quads_y} = {len(sprite_info)} 16x16 OAM sprites needed")

    primary_comment = [
        f"; Color palette extracted from {BMP_PATH.name} ({len(palette)} colors, "
        f"{bmp_bpp} bits/pixel in the source BMP).",
        "; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr",
        "; (8-bit BMP channels are truncated down to 5 bits each.)",
    ]
    pallets = [("pallet_char", primary_comment, palette)]
    for name, hue_shift, sat_scale, val_scale in PALLET_VARIANTS:
        variant_palette = derive_pallet_variant(palette, hue_shift, sat_scale, val_scale)
        print(f"{name}: derived from pallet_char (hue{hue_shift:+d} deg, "
              f"sat x{sat_scale}, val x{val_scale})")
        variant_comment = [
            f"; Recolor of pallet_char (hue{hue_shift:+d} deg, sat x{sat_scale}, val "
            f"x{val_scale} on non-grayscale entries - see derive_pallet_variant in",
            "; tools/bmp2asm.py). Not backed by its own BMP: the only other skin-tone-",
            "; recolor BMPs in the asset library (male_1.bmp/male_2.bmp) turned out to be",
            "; a different pose than male_face_down.bmp, not a recolor of it.",
        ]
        pallets.append((name, variant_comment, variant_palette))

    write_pallet_asm(PALLET_ASM_PATH, pallets)
    write_character_asm(CHARACTER_ASM_PATH, packed, width, height, tiles_x, tiles_y,
                         PIXEL_BPP, len(palette), sprite_info, quads_x, quads_y)
    print(f"wrote {PALLET_ASM_PATH}")
    print(f"wrote {CHARACTER_ASM_PATH}")


if __name__ == "__main__":
    sys.exit(main())
