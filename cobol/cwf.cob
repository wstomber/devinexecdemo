identification division.
program-id. cwf-check.
*> Pre-payment validation as the CWF Host would apply it to a claim the
*> contractor has already priced (CMS Pub. 100-04 Ch. 27 s20, s20.2.2).
*> Order: entitlement, duplicate of a posted claim, MSP primary not billed.
*> Reject codes are demo-defined; "accepted as is" is disposition 01.
data division.
working-storage section.
01 bene-index binary-long.
01 bene-found binary-long.
01 hist-index binary-long.
01 charges-display pic 9(10).
linkage section.
copy "claim.cpy".
copy "cwf.cpy".
procedure division using claim-interface cwf-tables.
check-claim.
    move 0 to claim-released
    move "REJECTED" to claim-cwf
    move "NOT_ENTITLED" to claim-cwf-reason
    move 0 to bene-found
    perform varying bene-index from 1 by 1
            until bene-index > bene-count or bene-found > 0
        if bene-mbi(bene-index) = claim-mbi
            move bene-index to bene-found
        end-if
    end-perform
    if bene-found = 0 goback end-if
    if claim-dos < bene-from(bene-found)
       or claim-dos > bene-to(bene-found)
        goback
    end-if
    move "DUPLICATE" to claim-cwf-reason
    move claim-charges to charges-display
    perform varying hist-index from 1 by 1 until hist-index > hist-count
        if hist-mbi(hist-index) = claim-mbi
           and hist-dos(hist-index) = claim-dos
           and hist-charges(hist-index) = charges-display
            goback
        end-if
    end-perform
    move "MSP_PRIMARY_NOT_BILLED" to claim-cwf-reason
    if bene-has-msp(bene-found) = 1
       and claim-dos >= bene-msp-from(bene-found)
       and claim-dos <= bene-msp-to(bene-found)
       and claim-primary = 0
        goback
    end-if
    move "ACCEPTED" to claim-cwf
    move "DISPOSITION_01" to claim-cwf-reason
    move claim-payment to claim-released
    goback.
end program cwf-check.
