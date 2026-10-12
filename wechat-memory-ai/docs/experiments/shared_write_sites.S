# Windows x64 leaf sites. XCHG with a memory operand is implicitly locked.
.text
.globl shared_write64
.globl shared_write_site
.globl shared_write_site_end
.def shared_write64; .scl 2; .type 32; .endef
.seh_proc shared_write64
shared_write64:
    .seh_endprologue
shared_write_site:
    xchgq %rdx, (%rcx)
shared_write_site_end:
    ret
.seh_endproc

# Test-only wrong-PC control: same operation, explicitly outside admitted site.
.globl foreign_write64
.globl foreign_write_site
.def foreign_write64; .scl 2; .type 32; .endef
.seh_proc foreign_write64
foreign_write64:
    .seh_endprologue
foreign_write_site:
    xchgq %rdx, (%rcx)
    ret
.seh_endproc
