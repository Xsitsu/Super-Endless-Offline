.p816
.smart

.include "macros.inc"
.include "registers.inc"

.include "header.asm"

.segment "CODE"

.include "pallet.asm"
.include "character.asm"

start:
	.include "init.asm"

	; Set up the color palette
	stz CGADD
	; Set color zero to red
	; $001f = %0000000000011111
	;           bbbbbgggggrrrrr
	lda #$1f
	sta CGDATA
	lda #$00
	sta CGDATA

	; Load the character's sprite palette and tile data, and place it on
	; screen as a grid of 16x16 OAM sprites.
	jsr load_char_pallet
	jsr load_char_gfx

	lda #$60            ; sprite size = 16x16/32x32, character table base = VRAM word $0000
	sta OBSEL

	jsr draw_char_sprites

	lda #$10            ; enable OBJ on the main screen
	sta TM

	lda #$0f
	sta INIDISP

busywait:
	bra busywait

nmi:
	bit RDNMI
_rti:
	rti
