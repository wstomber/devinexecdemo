       01 cwf-tables.
          05 bene-count            binary-long.
          05 bene-entry occurs 1000 times.
             10 bene-mbi           pic x(11).
             10 bene-from          pic 9(8).
             10 bene-to            pic 9(8).
             10 bene-has-msp       pic 9.
             10 bene-msp-from      pic 9(8).
             10 bene-msp-to        pic 9(8).
          05 hist-count            binary-long.
          05 hist-entry occurs 1000 times.
             10 hist-mbi           pic x(11).
             10 hist-dos           pic 9(8).
             10 hist-charges       pic 9(10).
