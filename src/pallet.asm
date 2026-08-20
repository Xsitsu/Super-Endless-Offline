; Init pallets

.include "macros.inc"


.macro pallet_16
	lda $f0
	sts CGADD

.endmacro


.segment "CODE"

; Color palette extracted from char.bmp (16 colors, 4 bits/pixel in the source BMP).
; SNES CGRAM color format is 2 bytes per color: 0bbbbbgggggrrrrr
; (8-bit BMP channels are truncated down to 5 bits each.)
pallet_char:
	.word $0000 ;  0: bmp rgb=(  1,  0,  0)
	.word $0024 ;  1: bmp rgb=( 34, 15,  0)
	.word $0ca2 ;  2: bmp rgb=( 23, 44, 31)
	.word $1127 ;  3: bmp rgb=( 57, 74, 32)
	.word $114a ;  4: bmp rgb=( 84, 80, 35)
	.word $15ad ;  5: bmp rgb=(108,107, 42)
	.word $190f ;  6: bmp rgb=(123, 71, 54)
	.word $1ce9 ;  7: bmp rgb=( 76, 63, 56)
	.word $15f0 ;  8: bmp rgb=(134,123, 46)
	.word $1632 ;  9: bmp rgb=(151,137, 44)
	.word $4e73 ; 10: bmp rgb=(159,159,159)
	.word $77bd ; 11: bmp rgb=(235,235,235)
	.word $0000 ; 12: bmp rgb=(  0,  0,  0)
	.word $0000 ; 13: bmp rgb=(  0,  0,  0)
	.word $0000 ; 14: bmp rgb=(  0,  0,  0)
	.word $0000 ; 15: bmp rgb=(  0,  0,  0)
pallet_char_end:

pallet_char_size = pallet_char_end - pallet_char
