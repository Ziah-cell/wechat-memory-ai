# Only calls a supplied function in this executable's own generated page.
.text
.globl register_caller
.def register_caller; .scl 2; .type 32; .endef
.seh_proc register_caller
register_caller:
    pushq %rbp
    .seh_pushreg %rbp
    pushq %r14
    .seh_pushreg %r14
    pushq %rsi
    .seh_pushreg %rsi
    pushq %rdi
    .seh_pushreg %rdi
    subq $56, %rsp
    .seh_stackalloc 56
    .seh_endprologue
    movq %rcx, %r10
    movq %rdx, %rcx
    movabsq $0x123456789abcdef1, %rbp
    movabsq $0x23456789abcdef12, %r14
    movabsq $0x3456789abcdef123, %rsi
    movabsq $0x456789abcdef1234, %rdi
    movl $2, %edx
    movl $3, %r8d
    movl $4, %r9d
    movq $5, 32(%rsp)
    movq $6, 40(%rsp)
    call *%r10
    xorl %edx, %edx
    cmpq $183, %rax
    jne 1f
    orl $16, %edx
1:  movabsq $0x123456789abcdef1, %r11
    cmpq %r11, %rbp
    jne 2f
    orl $1, %edx
2:  movabsq $0x23456789abcdef12, %r11
    cmpq %r11, %r14
    jne 3f
    orl $2, %edx
3:  movabsq $0x3456789abcdef123, %r11
    cmpq %r11, %rsi
    jne 4f
    orl $4, %edx
4:  movabsq $0x456789abcdef1234, %r11
    cmpq %r11, %rdi
    jne 5f
    orl $8, %edx
5:  movl %edx, %eax
    addq $56, %rsp
    popq %rdi
    popq %rsi
    popq %r14
    popq %rbp
    ret
.seh_endproc
