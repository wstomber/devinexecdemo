identification division.
program-id. calculate-payment.
data division.
working-storage section.
01 charge-basis pic 9(10) comp-3.
01 deductions pic 9(11) comp-3.
01 reduction-amount pic 9(11) comp-3.
01 payment-cap pic 9(10) comp-3.
linkage section.
copy "claim.cpy".
procedure division using claim-interface.
calculate-prospective-payment.
    move 0 to claim-payment
    move "ZERO" to claim-status
    *> Demo reason precedence: full, primary cap, deductions cap, paid.
    if raw-full = "Y"
        move "PAYMENT_IN_FULL" to claim-reason
        goback
    end-if
    move claim-charges to charge-basis
    if claim-has-contract = 1
        move claim-contract to charge-basis
    end-if
    compute payment-cap = function min(claim-gross, charge-basis)
    if claim-primary >= payment-cap
        move "PRIMARY_AT_CAP" to claim-reason
        goback
    end-if
    compute deductions = claim-deductible + claim-coinsurance
    if deductions >= payment-cap
        move "DEDUCTIONS_AT_CAP" to claim-reason
        goback
    end-if
    compute reduction-amount = function max(deductions, claim-primary)
    compute claim-payment = payment-cap - reduction-amount
    move "PAID" to claim-status
    move "SECONDARY_PAYABLE" to claim-reason
    goback.
end program calculate-payment.
