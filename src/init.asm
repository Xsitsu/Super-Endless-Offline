; A very simple SNES init routine
; For serious use, you probably want to do more than this
; This is simple and understandable, though
; Will leave you in A8 XY16 mode

; Disable interrupts and enable native mode
sei
clc
xce
cld

setAXY16

; ZeroCPU registers NMITIMEN through MEMSEL
stz $4200
stz $4202
stz $4204
stz $4206
stz $4208
stz $420A
stz $420C

lda #$0080
sta INIDISP ; Turn off screen ("forced blank")

; Zero some registers used for rendering
stz OAMADDL
stz BGMODE
stz BG1SC
stz BG3SC
stz BG12NBA
stz VMADDL
stz W12SEL
stz WH0
stz WH2
stz WBGLOG
stz TM
stz TMW

; Disable color math / etc
ldx #$0030
stx CGWSEL
ldy #$00E0
sty COLDATA

setA8

; Zero window masks
stz WOBJSEL

; Hide all OAM sprites (place them off the bottom edge of the screen, and
; zero the OAM high table). Objects that want to be shown are responsible
; for writing their own OAM entries afterwards; this only needs to run once
; at boot to get every slot into a known, hidden state.
stz OAMADDL
stz OAMADDH

ldx #0
hide_all_sprites_loop:
	lda #$00
	sta OAMDATA              ; X position
	lda #$f0
	sta OAMDATA              ; Y position = 240, off the bottom edge
	lda #$00
	sta OAMDATA              ; tile
	sta OAMDATA              ; attr
	inx
	inx
	inx
	inx
	cpx #(128 * 4)
	bne hide_all_sprites_loop

stz OAMADDL
lda #$01
sta OAMADDH              ; OAM high table starts at byte 512

ldx #0
zero_oam_high_loop:
	stz OAMDATA
	inx
	cpx #32
	bne zero_oam_high_loop
