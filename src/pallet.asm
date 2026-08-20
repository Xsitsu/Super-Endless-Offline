; Init pallets

.segment "CODE"

; Color palette extracted from male_face_down.bmp (16 colors, 4 bits/pixel in the source BMP).
; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr
; (8-bit BMP channels are truncated down to 5 bits each.)
pallet_char:
	.word $0000 ;  0: rgb=(  0,  0,  0)
	.word $0027 ;  1: rgb=( 56, 14,  0)
	.word $18c6 ;  2: rgb=( 49, 49, 49)
	.word $10ea ;  3: rgb=( 84, 60, 37)
	.word $1971 ;  4: rgb=(139, 90, 49)
	.word $1195 ;  5: rgb=(172, 98, 32)
	.word $265c ;  6: rgb=(226,144, 76)
	.word $3ebd ;  7: rgb=(238,172,123)
	.word $4e73 ;  8: rgb=(159,159,159)
	.word $4f3f ;  9: rgb=(255,205,156)
	.word $5b7f ; 10: rgb=(251,223,177)
	.word $6f7b ; 11: rgb=(222,222,222)
	.word $7fff ; 12: rgb=(255,255,255)
	.word $0000 ; 13: rgb=(  0,  0,  0)
	.word $0000 ; 14: rgb=(  0,  0,  0)
	.word $0000 ; 15: rgb=(  0,  0,  0)
pallet_char_end:

pallet_char_size = pallet_char_end - pallet_char

; Recolor of pallet_char (hue-18 deg, sat x1.05, val x0.92 on non-grayscale entries - see derive_pallet_variant in
; tools/bmp2asm.py). Not backed by its own BMP: the only other skin-tone-
; recolor BMPs in the asset library (male_1.bmp/male_2.bmp) turned out to be
; a different pose than male_face_down.bmp, not a recolor of it.
pallet_char_1:
	.word $0000 ;  0: rgb=(  0,  0,  0)
	.word $0006 ;  1: rgb=( 52,  0,  3)
	.word $18c6 ;  2: rgb=( 49, 49, 49)
	.word $10a9 ;  3: rgb=( 77, 40, 32)
	.word $14d0 ;  4: rgb=(128, 54, 41)
	.word $08b3 ;  5: rgb=(158, 46, 23)
	.word $1d5a ;  6: rgb=(208, 85, 63)
	.word $35fb ;  7: rgb=(219,122,108)
	.word $4e73 ;  8: rgb=(159,159,159)
	.word $467d ;  9: rgb=(235,158,139)
	.word $4edc ; 10: rgb=(231,182,159)
	.word $6f7b ; 11: rgb=(222,222,222)
	.word $7fff ; 12: rgb=(255,255,255)
	.word $0000 ; 13: rgb=(  0,  0,  0)
	.word $0000 ; 14: rgb=(  0,  0,  0)
	.word $0000 ; 15: rgb=(  0,  0,  0)
pallet_char_1_end:

pallet_char_1_size = pallet_char_1_end - pallet_char_1

; Recolor of pallet_char (hue+18 deg, sat x0.85, val x1.05 on non-grayscale entries - see derive_pallet_variant in
; tools/bmp2asm.py). Not backed by its own BMP: the only other skin-tone-
; recolor BMPs in the asset library (male_1.bmp/male_2.bmp) turned out to be
; a different pose than male_face_down.bmp, not a recolor of it.
pallet_char_2:
	.word $0000 ;  0: rgb=(  0,  0,  0)
	.word $0487 ;  1: rgb=( 59, 36,  9)
	.word $18c6 ;  2: rgb=( 49, 49, 49)
	.word $152b ;  3: rgb=( 88, 79, 46)
	.word $21f2 ;  4: rgb=(146,126, 66)
	.word $1e76 ;  5: rgb=(181,152, 56)
	.word $333d ;  6: rgb=(237,204,103)
	.word $4b7f ;  7: rgb=(250,222,147)
	.word $4e73 ;  8: rgb=(159,159,159)
	.word $57bf ;  9: rgb=(255,238,171)
	.word $5fff ; 10: rgb=(255,250,191)
	.word $6f7b ; 11: rgb=(222,222,222)
	.word $7fff ; 12: rgb=(255,255,255)
	.word $0000 ; 13: rgb=(  0,  0,  0)
	.word $0000 ; 14: rgb=(  0,  0,  0)
	.word $0000 ; 15: rgb=(  0,  0,  0)
pallet_char_2_end:

pallet_char_2_size = pallet_char_2_end - pallet_char_2

; Fourth pallet slot for the cycling timer in main.asm - deliberately not
; backed by its own BMP, so it aliases whatever bytes happen to follow the
; last real pallet (pallet_char_2) in ROM.
pallet_char_3 = pallet_char_2_end

; The pallets the per-second timer in main.asm's nmi handler rotates the
; sprite through. Low words only - every pallet here lives in the same bank as pallet_char.
pallet_table:
	.word .loword(pallet_char)
	.word .loword(pallet_char_1)
	.word .loword(pallet_char_2)
	.word .loword(pallet_char_3)
pallet_table_end:

pallet_table_count = (pallet_table_end - pallet_table) / 2

; Loads pallet_table[A] (A = pallet index, 8-bit) into CGRAM as sprite
; palette 0 (colors 128-143). Call during forced blank or v-blank.
; Assumes/leaves A8 XY16 (see init.asm).
load_char_pallet:
	pha                 ; stash the index while we set CGADD
	lda #128            ; CGRAM color index 128 = sprite palette 0, color 0
	sta CGADD

	pla
	asl a               ; index -> byte offset into pallet_table
	rep #$20            ; A16 (high byte is stale - mask it below)
	and #$00ff
	tax
	lda pallet_table,x
	sta A1T1L
	lda #pallet_char_size ; every pallet is the same size
	sta DAS1L

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
