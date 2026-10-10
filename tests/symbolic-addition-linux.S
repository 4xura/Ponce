/* Owned Linux ELF probe: solve input + 7 == 42 (expected input: 35).
 * No C runtime or external libraries; assembles for both x86 and x86-64.
 */
.section .data
.globl ponce_input
.type ponce_input, @object
ponce_input:
    .byte 1
.size ponce_input, .-ponce_input

.section .text
.globl ponce_entry, ponce_branch, ponce_true, ponce_false
.type ponce_entry, @function
ponce_entry:
#ifdef __x86_64__
    movzbl ponce_input(%rip), %eax
#else
    movzbl ponce_input, %eax
#endif
    addl $7, %eax
    cmpl $42, %eax
ponce_branch:
    jne ponce_false
ponce_true:
    movl $1, %ebx
    jmp exit_probe
ponce_false:
    xorl %ebx, %ebx
exit_probe:
#ifdef __x86_64__
    movl %ebx, %edi
    movl $60, %eax
    syscall
#else
    movl $1, %eax
    int $0x80
#endif
.size ponce_entry, .-ponce_entry
.section .note.GNU-stack,"",@progbits
