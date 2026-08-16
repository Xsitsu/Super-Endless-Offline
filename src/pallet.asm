; Init pallets

.include "macros.inc"


.macro pallet_16
	lda $f0
	sts CGADD

.endmacro



