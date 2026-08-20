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

; Color palette extracted from male_1.bmp (16 colors, 4 bits/pixel in the source BMP).
; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr
; (8-bit BMP channels are truncated down to 5 bits each.)
pallet_char_1:
	.word $0000 ;  0: bmp rgb=(  4,  0,  0)
	.word $323a ;  1: bmp rgb=(213,140,100)
	.word $2195 ;  2: bmp rgb=(172, 98, 65)
	.word $0047 ;  3: bmp rgb=( 57, 16,  0)
	.word $08ec ;  4: bmp rgb=( 98, 57, 16)
	.word $0006 ;  5: bmp rgb=( 49,  0,  0)
	.word $2529 ;  6: bmp rgb=( 72, 72, 72)
	.word $3ebb ;  7: bmp rgb=(222,172,123)
	.word $5ad6 ;  8: bmp rgb=(180,180,180)
	.word $6f7b ;  9: bmp rgb=(222,222,222)
	.word $1084 ; 10: bmp rgb=( 39, 38, 38)
	.word $2112 ; 11: bmp rgb=(148, 65, 65)
	.word $4210 ; 12: bmp rgb=(131,131,131)
	.word $0000 ; 13: bmp rgb=(  4,  0,  0)
	.word $0000 ; 14: bmp rgb=(  4,  0,  0)
	.word $0000 ; 15: bmp rgb=(  4,  0,  0)
pallet_char_1_end:

pallet_char_1_size = pallet_char_1_end - pallet_char_1

; Color palette extracted from male_2.bmp (16 colors, 4 bits/pixel in the source BMP).
; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr
; (8-bit BMP channels are truncated down to 5 bits each.)
pallet_char_2:
	.word $0066 ;  0: bmp rgb=( 55, 29,  0)
	.word $0000 ;  1: bmp rgb=(  4,  2,  0)
	.word $4f9f ;  2: bmp rgb=(255,230,158)
	.word $3f3d ;  3: bmp rgb=(239,206,122)
	.word $19d1 ;  4: bmp rgb=(139,115, 49)
	.word $5bdf ;  5: bmp rgb=(255,247,180)
	.word $4a52 ;  6: bmp rgb=(148,148,148)
	.word $1109 ;  7: bmp rgb=( 79, 66, 39)
	.word $6f7b ;  8: bmp rgb=(222,222,222)
	.word $4fdf ;  9: bmp rgb=(255,244,156)
	.word $7fff ; 10: bmp rgb=(255,255,255)
	.word $26db ; 11: bmp rgb=(222,180, 74)
	.word $5ef7 ; 12: bmp rgb=(189,189,189)
	.word $0066 ; 13: bmp rgb=( 55, 29,  0)
	.word $0066 ; 14: bmp rgb=( 55, 29,  0)
	.word $0066 ; 15: bmp rgb=( 55, 29,  0)
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
