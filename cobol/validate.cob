identification division.
program-id. validate-claim.
data division.
working-storage section.
01 char-index binary-long.
01 id-ended pic 9.
linkage section.
copy "claim.cpy".
procedure division using claim-interface.
validate-record.
    move "INVALID" to claim-status
    move "BAD_LENGTH" to claim-reason
    if claim-length not = 73 goback end-if
    move "BAD_ID" to claim-reason
    if raw-id = spaces goback end-if
    move 0 to id-ended
    perform varying char-index from 1 by 1 until char-index > 12
        evaluate true
          when raw-id(char-index:1) = space
            move 1 to id-ended
          when id-ended = 1
            goback
          when raw-id(char-index:1) >= "A" and <= "Z"
            continue
          when raw-id(char-index:1) >= "0" and <= "9"
            continue
          when raw-id(char-index:1) = "-" or "_"
            continue
          when other
            goback
        end-evaluate
    end-perform
    move raw-id to claim-id
    move "BAD_AMOUNT" to claim-reason
    if raw-charges is not numeric or raw-gross is not numeric
       or raw-primary is not numeric or raw-deductible is not numeric
       or raw-coinsurance is not numeric
        goback
    end-if
    if raw-contract not = "----------"
        if raw-contract is not numeric goback end-if
        move raw-contract to claim-contract
        move 1 to claim-has-contract
    end-if
    *> No numeric moves or arithmetic precede the class tests above.
    move raw-charges to claim-charges
    move raw-gross to claim-gross
    move raw-primary to claim-primary
    move raw-deductible to claim-deductible
    move raw-coinsurance to claim-coinsurance
    move "BAD_CONTRACT" to claim-reason
    if claim-has-contract = 1
       and claim-contract > claim-charges
        goback
    end-if
    move "BAD_FLAG" to claim-reason
    if raw-full not = "Y" and not = "N" goback end-if
    move "VALID" to claim-status
    move spaces to claim-reason
    goback.
end program validate-claim.
