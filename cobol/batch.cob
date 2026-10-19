identification division.
program-id. msp-batch.
environment division.
input-output section.
file-control.
    select claims-file assign to input-path
        organization sequential file status input-status.
    select cwf-file assign to cwf-path
        organization line sequential file status cwf-status.
    select results-file assign to output-path
        organization line sequential file status output-status.
    select totals-file assign to totals-path
        organization line sequential file status totals-status.
data division.
file section.
fd claims-file record contains 1 characters.
01 input-byte pic x.
fd cwf-file.
01 cwf-record pic x(64).
fd results-file.
01 output-record pic x(160).
fd totals-file.
01 totals-record pic x(180).
working-storage section.
01 input-path pic x(1024).
01 output-path pic x(1024).
01 cwf-path pic x(1024).
01 cwf-status pic xx.
01 cwf-eof pic 9 value 0.
01 accepted-count pic 9(10) value 0.
01 rejected-count pic 9(10) value 0.
01 released-total pic 9(15) value 0.
01 released-display pic 9(10).
01 totals-path pic x(1024).
01 argument-count binary-long.
01 input-length binary-long value 0.
01 input-record pic x(4097).
01 input-status pic xx.
01 output-status pic xx.
01 totals-status pic xx.
01 eof-flag pic 9 value 0.
01 input-open pic 9 value 0.
01 output-open pic 9 value 0.
01 totals-open pic 9 value 0.
01 record-count pic 9(10) value 0.
01 paid-count pic 9(10) value 0.
01 zero-count pic 9(10) value 0.
01 invalid-count pic 9(10) value 0.
01 payment-total pic 9(15) value 0.
01 payment-display pic 9(10).
01 id-table.
   05 seen-id pic x(12) occurs 10000 times.
01 id-count binary-long value 0.
01 id-index binary-long.
copy "claim.cpy".
copy "cwf.cpy".
procedure division.
main.
    accept argument-count from argument-number
    if argument-count not = 4
        display "usage: msp-batch INPUT CWF OUTPUT TOTALS" upon syserr
        move 2 to return-code
        goback
    end-if
    accept input-path from argument-value
    accept cwf-path from argument-value
    accept output-path from argument-value
    accept totals-path from argument-value
    if input-path = output-path or input-path = totals-path
       or output-path = totals-path
       or cwf-path = input-path or cwf-path = output-path
       or cwf-path = totals-path
        display "paths must be distinct" upon syserr
        move 2 to return-code
        goback
    end-if
    *> Fixed one-byte reads avoid version-dependent LINE SEQUENTIAL
    *> truncation. Line boundaries and the transport limit are explicit.
    set environment "COB_LS_NULLS" to "N"
    set environment "COB_LS_VALIDATE" to "N"
    perform load-cwf
    open input claims-file
    if input-status not = "00" perform fatal-io end-if
    move 1 to input-open
    open output results-file
    if output-status not = "00" perform fatal-io end-if
    move 1 to output-open
    open output totals-file
    if totals-status not = "00" perform fatal-io end-if
    move 1 to totals-open
    move "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents" to output-record
    perform write-result
    move spaces to input-record
    perform until eof-flag = 1
        read claims-file
        evaluate input-status
          when "10"
            if input-length > 0 perform finish-line end-if
            move 1 to eof-flag
          when "00"
            if input-byte = x"0A"
                perform finish-line
            else
                if input-length >= 4097 perform fatal-io end-if
                add 1 to input-length
                move input-byte to input-record(input-length:1)
            end-if
          when other perform fatal-io
        end-evaluate
    end-perform
    move "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents" to totals-record
    perform write-totals
    move spaces to totals-record
    string record-count "," paid-count "," zero-count ","
        invalid-count "," payment-total "," accepted-count ","
        rejected-count "," released-total into totals-record
    end-string
    perform write-totals
    perform close-files
    move 0 to return-code
    goback.
finish-line.
    if input-length > 0
        if input-record(input-length:1) = x"0D"
            move space to input-record(input-length:1)
            subtract 1 from input-length
        end-if
    end-if
    if input-length > 4096
        display "input line exceeds 4096 bytes" upon syserr
        perform fatal-io
    end-if
    perform process-record
    move 0 to input-length
    move spaces to input-record.
process-record.
    if record-count >= 10000
        display "batch exceeds 10000 records" upon syserr
        perform fatal-io
    end-if
    add 1 to record-count
    *> Reset raw AND parsed data for every record, even after rejection.
    initialize claim-interface
    move spaces to claim-id
    string "@" record-count into claim-id end-string
    move input-record(1:92) to claim-raw
    move input-length to claim-length
    call "validate-claim" using claim-interface
    if claim-id(1:1) not = "@"
        perform varying id-index from 1 by 1 until id-index > id-count
            if claim-id = seen-id(id-index)
                display "duplicate claim ID: " claim-id upon syserr
                perform fatal-io
            end-if
        end-perform
        add 1 to id-count
        move claim-id to seen-id(id-count)
    end-if
    if claim-status = "VALID"
        call "calculate-payment" using claim-interface
    end-if
    if claim-status = "PAID" or claim-status = "ZERO"
        call "cwf-check" using claim-interface cwf-tables
    else
        move "NOT_SENT" to claim-cwf
        move "CLAIM_INVALID" to claim-cwf-reason
    end-if
    evaluate claim-cwf
      when "ACCEPTED" add 1 to accepted-count
      when "REJECTED" add 1 to rejected-count
    end-evaluate
    add claim-released to released-total
    move claim-released to released-display
    evaluate claim-status
      when "PAID" add 1 to paid-count
      when "ZERO" add 1 to zero-count
      when other add 1 to invalid-count
    end-evaluate
    add claim-payment to payment-total
    move claim-payment to payment-display
    move spaces to output-record
    string record-count "," function trim(claim-id) ","
        function trim(claim-status) "," payment-display ","
        function trim(claim-reason) "," function trim(claim-cwf) ","
        function trim(claim-cwf-reason) "," released-display
        into output-record
    end-string
    perform write-result.
load-cwf.
    *> Reference data the CWF Host holds: B = beneficiary entitlement and
    *> MSP period, H = a claim already posted to history. Bad data is fatal.
    open input cwf-file
    if cwf-status not = "00" perform fatal-io end-if
    move 0 to bene-count
    move 0 to hist-count
    perform until cwf-eof = 1
        move spaces to cwf-record
        read cwf-file
            at end move 1 to cwf-eof
            not at end
                if cwf-status not = "00" perform bad-cwf end-if
                perform parse-cwf
        end-read
    end-perform
    close cwf-file.
parse-cwf.
    evaluate cwf-record(1:1)
      when "B"
        if cwf-record(45:20) not = spaces or cwf-record(2:11) = spaces
           or cwf-record(13:16) is not numeric or bene-count >= 1000
            perform bad-cwf
        end-if
        add 1 to bene-count
        move cwf-record(2:11) to bene-mbi(bene-count)
        move cwf-record(13:8) to bene-from(bene-count)
        move cwf-record(21:8) to bene-to(bene-count)
        if cwf-record(29:16) = all "-"
            move 0 to bene-has-msp(bene-count)
            move 0 to bene-msp-from(bene-count)
            move 0 to bene-msp-to(bene-count)
        else
            if cwf-record(29:16) is not numeric perform bad-cwf end-if
            move 1 to bene-has-msp(bene-count)
            move cwf-record(29:8) to bene-msp-from(bene-count)
            move cwf-record(37:8) to bene-msp-to(bene-count)
        end-if
      when "H"
        if cwf-record(31:34) not = spaces or cwf-record(2:11) = spaces
           or cwf-record(13:18) is not numeric or hist-count >= 1000
            perform bad-cwf
        end-if
        add 1 to hist-count
        move cwf-record(2:11) to hist-mbi(hist-count)
        move cwf-record(13:8) to hist-dos(hist-count)
        move cwf-record(21:10) to hist-charges(hist-count)
      when other perform bad-cwf
    end-evaluate.
bad-cwf.
    display "invalid CWF reference record" upon syserr
    perform fatal-io.
write-result.
    write output-record
    if output-status not = "00" perform fatal-io end-if.
write-totals.
    write totals-record
    if totals-status not = "00" perform fatal-io end-if.
close-files.
    if input-open = 1
        close claims-file
        move 0 to input-open
        if input-status not = "00" perform fatal-io end-if
    end-if
    if output-open = 1
        close results-file
        move 0 to output-open
        if output-status not = "00" perform fatal-io end-if
    end-if
    if totals-open = 1
        close totals-file
        move 0 to totals-open
        if totals-status not = "00" perform fatal-io end-if
    end-if.
fatal-io.
    display "fatal batch failure; discard outputs; file status "
        input-status "/" output-status "/" totals-status upon syserr
    move 2 to return-code
    stop run.
end program msp-batch.
