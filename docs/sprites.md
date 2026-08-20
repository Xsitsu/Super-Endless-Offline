# SNES Sprites

Source: https://wiki.superfamicom.org/sprites

## Overview

The SNES supports 128 independent sprites, stored in Object Attribute Memory
(OAM). Unused sprites can be hidden by positioning them off-screen, e.g.
X=257 or Y=-16.

## OAM Structure

OAM is 544 bytes total, split into two tables:

- **Low table**: 512 bytes — 128 records of 4 bytes each (one per sprite)
- **High table**: 32 bytes — 128 records of 2 bits each (one per sprite)

### Access

- Set the word address via `$2102`.
- Set the table select via bit 0 of `$2103`.
- Read/write data via `$2104` (or `$2138` for reads during rendering).

The internal OAM address is invalidated during scanline rendering and is
reloaded at V-Blank start (outside force-blank) or when `$2100.7` transitions
from 1 to 0.

## Low Table Record Format (4 bytes per sprite)

```
byte OBJ*4+0: xxxxxxxx   X position (low 8 bits, signed with high bit in high table)
byte OBJ*4+1: yyyyyyyy   Y position
byte OBJ*4+2: cccccccc   First tile number
byte OBJ*4+3: vhoopppN   Flags (see below)
```

## High Table Format (2 bits per sprite)

```
bit (2*n)   of byte OBJ/4: X position MSB
bit (2*n+1) of byte OBJ/4: size flag (s)
```

Each byte of the high table holds the extra X-bit and size flag for 4
sprites (2 bits each).

## Field Definitions

| Field | Bits | Purpose |
|---|---|---|
| X position | 9 bits (8 in low table + MSB in high table) | Signed; 0-239 is on-screen, -63 to -1 is off the left/top edge |
| Y position | 8 bits | 0-239 on-screen |
| Tile (`c`) | 8 bits | Row/column reference into the character table |
| Name (`N`) | 1 bit | Selects which of the two 16x16 character tables to use |
| Palette (`ppp`) | 3 bits | Selects colors `128 + ppp*16` through `128 + ppp*16 + 15` |
| Priority (`oo`) | 2 bits | Sprite-to-background priority |
| H-flip (`h`) | 1 bit | Flips the entire sprite horizontally |
| V-flip (`v`) | 1 bit | Flips the entire sprite vertically |
| Size (`s`) | 1 bit | Selects between the two sprite sizes configured in `$2101` |

## Sprite Palettes

Eight 16-color palettes are available, starting at CGRAM index 128. The
first color of each palette is always considered transparent, which allows
for non-rectangular sprite shapes. Only palettes 4-7 participate in color
math.

## Character Table in VRAM

Sprites draw from two separate 16x16-tile character tables in VRAM. The `N`
bit in OAM selects which table is used. Tile numbers wrap within the same
table — e.g. an arbitrary 32x32 sprite with the N-bit set and a base tile
number that would overflow the table wraps around within that table (for
example, being specified to use tile `$FE`).

VRAM address for a tile is calculated as:

```
((Base << 13) + (cccccccc << 4) + (N ? ((Name + 1) << 12) : 0)) & 0x7FFF
```

Where `Base` and `Name` are configured via `$2101`.

## Sprite Priority

### Relative to Backgrounds

The two priority bits (`oo`) in each OAM entry control how a sprite layers
against the background layers (see the Backgrounds documentation for the
full priority ordering).

### Sprite-to-Sprite

Determined by sprite index and the priority rotation bit (bit 7 of
`$2103`):

- If **unset**, Sprite 0 has the highest priority, and priority decreases
  with increasing sprite index.
- If **set**, priority rotates based on the internal OAM word address:
  `FirstSprite = (OAMAddr & 0xFE) >> 1`.

`FirstSprite` ends up on top of all other sprites, regardless of the
priority bits in OAM. Subsequent sprites follow in index order, wrapping
around from 127 back to 0 as needed.

## Rendering Per-Scanline

For each scanline, the PPU performs three steps:

1. **Range**: Identify the first 32 sprites (in priority order) where
   `-size < X < 256`. If more than 32 sprites qualify, bit 6 of `$213E` is
   set (range over flag).
2. **Time**: Load up to 34 8x8 tiles for the scanline, left-to-right after
   flipping. If more than 34 tiles are needed, bit 7 of `$213E` is set
   (time over flag).
3. **Association**: Each loaded tile is assigned its true X position,
   palette, and priority for compositing.

### Constraints

- A single scanline can display at most **32 distinct sprites**.
- A single scanline can display at most **34 8x8 tiles** total across those
  sprites.

Exceeding either limit causes sprites/tiles beyond the limit to be dropped
for that scanline (with the corresponding overflow flag set in `$213E`),
which is the classic SNES "sprite flicker" cause when naively rendering too
many/too large sprites on one line.
