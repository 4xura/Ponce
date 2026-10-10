; Owned, deterministic test: solve input + 7 == 42 (expected input: 35).
PUBLIC ponce_entry, ponce_input, ponce_branch, ponce_true, ponce_false
.data
ponce_input BYTE 1
.code
ponce_entry PROC
    movzx eax, BYTE PTR [ponce_input]
    add eax, 7
    cmp eax, 42
ponce_branch::
    jne ponce_false
ponce_true::
    mov eax, 1
    ret
ponce_false::
    xor eax, eax
    ret
ponce_entry ENDP
END
