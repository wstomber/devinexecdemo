       01 claim-interface.
          05 claim-raw.
             10 raw-id             pic x(12).
             10 raw-charges        pic x(10).
             10 raw-gross          pic x(10).
             10 raw-primary        pic x(10).
             10 raw-deductible     pic x(10).
             10 raw-coinsurance    pic x(10).
             10 raw-contract       pic x(10).
             10 raw-full           pic x.
             10 raw-mbi            pic x(11).
             10 raw-dos            pic x(8).
             10 raw-dos-parts redefines raw-dos.
                15 raw-dos-year    pic x(4).
                15 raw-dos-month   pic x(2).
                15 raw-dos-day     pic x(2).
          05 claim-length          binary-long.
          05 claim-id              pic x(12).
          05 claim-status          pic x(7).
          05 claim-reason          pic x(24).
          05 claim-charges         pic 9(10) comp-3.
          05 claim-gross           pic 9(10) comp-3.
          05 claim-primary         pic 9(10) comp-3.
          05 claim-deductible      pic 9(10) comp-3.
          05 claim-coinsurance     pic 9(10) comp-3.
          05 claim-contract        pic 9(10) comp-3.
          05 claim-has-contract    pic 9.
          05 claim-payment         pic 9(10) comp-3.
          05 claim-mbi             pic x(11).
          05 claim-dos             pic 9(8).
          05 claim-cwf             pic x(8).
          05 claim-cwf-reason      pic x(24).
          05 claim-released        pic 9(10) comp-3.
