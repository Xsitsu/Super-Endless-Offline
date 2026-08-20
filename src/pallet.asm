; Init pallets

.segment "CODE"

; Color palette extracted from male_face_down.bmp (16 colors, 4 bits/pixel in the source BMP).
; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr
; (8-bit BMP channels are truncated down to 5 bits each.)
pallet_char:
	.word $0000 ;  0: bmp rgb=(  0,  0,  0)
	.word $0027 ;  1: bmp rgb=( 56, 14,  0)
	.word $18c6 ;  2: bmp rgb=( 49, 49, 49)
	.word $10ea ;  3: bmp rgb=( 84, 60, 37)
	.word $1971 ;  4: bmp rgb=(139, 90, 49)
	.word $1195 ;  5: bmp rgb=(172, 98, 32)
	.word $265c ;  6: bmp rgb=(226,144, 76)
	.word $3ebd ;  7: bmp rgb=(238,172,123)
	.word $4e73 ;  8: bmp rgb=(159,159,159)
	.word $4f3f ;  9: bmp rgb=(255,205,156)
	.word $5b7f ; 10: bmp rgb=(251,223,177)
	.word $6f7b ; 11: bmp rgb=(222,222,222)
	.word $7fff ; 12: bmp rgb=(255,255,255)
	.word $0000 ; 13: bmp rgb=(  0,  0,  0)
	.word $0000 ; 14: bmp rgb=(  0,  0,  0)
	.word $0000 ; 15: bmp rgb=(  0,  0,  0)
pallet_char_end:

pallet_char_size = pallet_char_end - pallet_char

; Loads pallet_char into CGRAM as sprite palette 0 (colors 128-143).
; Call during forced blank. Assumes/leaves A8 XY16 (see init.asm).
load_char_pallet:
	lda #128            ; CGRAM color index 128 = sprite palette 0, color 0
	sta CGADD

	setAXY16
	ldx #.loword(pallet_char)
	stx A1T1L
	ldx #pallet_char_size
	stx DAS1L

	setA8
	lda #^pallet_char
	sta A1B1
	lda #$22            ; CGDATA
	sta BBAD1
	lda #$00            ; mode 0: write 1 byte per src, increment src addr
	sta DMAP1
	lda #$02            ; enable DMA channel 1
	sta MDMAEN
	rts
