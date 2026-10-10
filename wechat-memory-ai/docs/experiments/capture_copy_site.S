# Bounded copy of 32 bytes. Test driver never supplies external process pointers.
.text
.globl capture_copy32
.globl capture_copy_start
.globl capture_copy_end
.def capture_copy32; .scl 2; .type 32; .endef
.seh_proc capture_copy32
capture_copy32:
capture_copy_start:
    .seh_endprologue
    movq (%rcx), %rax
    movq %rax, (%rdx)
    movq 8(%rcx), %rax
    movq %rax, 8(%rdx)
    movq 16(%rcx), %rax
    movq %rax, 16(%rdx)
    movq 24(%rcx), %rax
    movq %rax, 24(%rdx)
    ret
capture_copy_end:
.seh_endproc
