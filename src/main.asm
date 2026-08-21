.p816
.smart

.include "macros.inc"
.include "registers.inc"

.include "header.asm"

.segment "CODE"

.include "pallet.asm"
.include "objects/include.asm"

.segment "BSS"
nmi_frame_count: .res 1    ; frames since the last pallet swap
pallet_cycle_index: .res 1 ; which pallet_table entry is currently loaded

.segment "CODE"

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
	stz nmi_frame_count
	stz pallet_cycle_index
	lda #0               ; pallet_table index 0 = pallet_char
	jsr load_char_pallet
	jsr load_char_gfx

	lda #$60            ; sprite size = 16x16/32x32, character table base = VRAM word $0000
	sta OBSEL

	jsr draw_char_sprites

	lda #$10            ; enable OBJ on the main screen
	sta TM

	lda #$0f
	sta INIDISP

	lda #$80             ; enable NMI (v-blank interrupt)
	sta NMITIMEN

busywait:
	bra busywait

; Fires once per v-blank (~60Hz NTSC). Every 60 frames, advances to the next
; pallet in pallet_table (wrapping) and reloads the sprite's CGRAM palette,
; cycling the character's colors roughly once per second.
nmi:
	php
	sep #$20
	rep #$10
	pha
	phx
	phy

	lda RDNMI             ; acknowledge NMI

	inc nmi_frame_count
	lda nmi_frame_count
	cmp #60
	bne nmi_done
	stz nmi_frame_count

	lda pallet_cycle_index
	inc a
	cmp #pallet_table_count
	bcc nmi_store_index
	lda #0
nmi_store_index:
	sta pallet_cycle_index
	jsr load_char_pallet

nmi_done:
	ply
	plx
	pla
	plp
	rti

; Shared bare-return stub for the vectors we don't otherwise handle (COP,
; BRK, ABORT, IRQ - see header.asm). Must stay push/pull-free since none of
; those vectors have a matching register save.
_rti:
	rti
