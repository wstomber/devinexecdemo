# Ledger source: every expected value below is typed by hand from the cited rule. Regenerate with: python3 tests_policy/ledger_source.py
import json
EX3="CMS Pub. 100-05 Ch. 5 §40.8.3 Example 3, PDF pp. 83-84 (docs/cms-example-3.md)"
EX1="CMS Pub. 100-05 Ch. 5 §40.8.3 Example 1, PDF p. 82"
LIM="CMS Pub. 100-05 Ch. 5 §40.8.2 four limits (PDF pp. 79-80) and §40.8.3 A formula (pp. 80-81)"
OTAF="CMS Pub. 100-05 Ch. 5 §40.8.2: a lower obligated-to-accept amount replaces charges (PDF pp. 79-80)"
FULL="CMS Pub. 100-05 Ch. 5 §40.8 (PDF p. 78): no secondary payment when the primary payment is accepted/required as payment in full"
ZPREC="docs/rules.md demo decision: zero precedence PAYMENT_IN_FULL, PRIMARY_AT_CAP, DEDUCTIONS_AT_CAP (reason codes are demo interface)"
IF="README interface: record layout and rejection precedence length, ID, numeric fields, contract range, flag, MBI, date"
MAXS="README interface: each amount 0-9,999,999,999 cents; deductible+coinsurance uses 11 digits"
STATE="README interface: per-record processing; rejected records must not affect later records"
CWF="CMS Pub. 100-04 Ch. 27 §20/§20.2.2 (CWF pre-payment validation: entitlement, not already paid) and Pub. 100-05 Ch. 5 §10.1 (MSP auxiliary file); README 'CWF pre-payment check' (codes demo-defined)"
cases=[]
def c(id,cat,src,ar,exp,inp=None,raw=None,patch=None,mbi=None,dos=None):
    d={"id":id,"category":cat,"source":src,"arithmetic":ar}
    if raw is not None: d["raw"]=raw
    else:
        i=dict(zip(("id","charges","gross","primary","deductible","coinsurance","contract","full"),inp))
        if mbi: i["mbi"]=mbi
        if dos: i["dos"]=dos
        d["input"]=i
    if patch: d["patch"]=patch
    st,pay,rs,cw,cr,rel=exp
    d["expected"]={"claim_id":"@" if (raw is not None or (patch and any(p[0]==0 for p in patch) and st=="INVALID" and rs in("BAD_ID",))) else id,
                   "status":st,"payment_cents":pay,"reason":rs,"cwf":cw,"cwf_reason":cr,"released_cents":rel}
    cases.append(d)
def paid(n): return ("PAID",n,"SECONDARY_PAYABLE","ACCEPTED","DISPOSITION_01",n)
def zero(r): return ("ZERO",0,r,"ACCEPTED","DISPOSITION_01",0)
def inv(r): return ("INVALID",0,r,"NOT_SENT","CLAIM_INVALID",0)
def rej(st,n,r): return (st,n,"SECONDARY_PAYABLE" if st=="PAID" else r[1],"REJECTED",r[0] if st=="PAID" else r[0],0)
P,N=None,"N"
# --- published examples
c("CMS-EX3","policy",EX3+"; CWF: "+CWF,"Limits $: G-P 14000-12500=1500; G-T 14000-1556=12444; A-P 13000-12500=500; A-T 13000-1556=11444; lowest 500 -> 50000 cents. MBI P2MSPEGHP02 entitled 20180701-open, MSP 20240601-20251130 covers 20250610, primary 1250000>0 billed, no history -> ACCEPTED, released 50000",
  paid(50000),("CMS-EX3",1500000,1400000,1250000,155600,0,1300000,N),mbi="P2MSPEGHP02")
c("EX3-NO-OTAF","policy",EX3+" counterfactual without the OTAF; "+LIM,"Same inputs, no contract so basis=C=15000: G-P 1500; G-T 12444; C-P 2500; C-T 13444; lowest 1500 -> 150000 (a $1,000 overstatement vs CMS-EX3)",
  paid(150000),("EX3-NO-OTAF",1500000,1400000,1250000,155600,0,P,N),mbi="P2MSPEGHP02")
c("CMS-EX1","policy",EX1,"G-P 22000-20500=1500; G-T 22000-1556=20444; C-P 25000-20500=4500; C-T 25000-1556=23444; lowest 1500 -> 150000; P2MSPEGHP02 billed primary -> ACCEPTED",
  paid(150000),("CMS-EX1",2500000,2200000,2050000,155600,0,P,N),mbi="P2MSPEGHP02")
# --- each limit controlling
c("LIM-G-P","policy",LIM,"C=1000.00 G=900.00 P=300.00 T=100.00: G-P 600; G-T 800; C-P 700; C-T 900 -> 60000",paid(60000),("LIM-G-P",100000,90000,30000,10000,0,P,N))
c("LIM-G-T","policy",LIM,"C=1000 G=900 P=50 T=150+50=200: G-P 850; G-T 700; C-P 950; C-T 800 -> 70000",paid(70000),("LIM-G-T",100000,90000,5000,15000,5000,P,N))
c("LIM-C-P","policy",LIM,"C=800 G=900 P=300 T=100: G-P 600; G-T 800; C-P 500; C-T 700 -> 50000",paid(50000),("LIM-C-P",80000,90000,30000,10000,0,P,N))
c("LIM-C-T","policy",LIM,"C=800 G=900 P=50 T=200+50=250: G-P 850; G-T 650; C-P 750; C-T 550 -> 55000",paid(55000),("LIM-C-T",80000,90000,5000,20000,5000,P,N))
c("LIM-A-T","policy",OTAF,"C=1000 G=900 A=700 P=100 T=200: G-P 800; G-T 700; A-P 600; A-T 500 -> 50000",paid(50000),("LIM-A-T",100000,90000,10000,20000,0,70000,N))
c("LIM-ALL-EQ","policy",LIM,"C=G=500 P=T=100: all four limits = 400 -> 40000",paid(40000),("LIM-ALL-EQ",50000,50000,10000,10000,0,P,N))
c("LIM-G-EQ-C","policy",LIM,"C=G=500 P=200 T=50: G-P=C-P=300; G-T=C-T=450 -> 30000",paid(30000),("LIM-G-EQ-C",50000,50000,20000,5000,0,P,N))
c("LIM-P-EQ-T","policy",LIM,"C=1000 G=600 P=150 T=100+50=150: G-P=G-T=450; C-P=C-T=850 -> 45000",paid(45000),("LIM-P-EQ-T",100000,60000,15000,10000,5000,P,N))
c("OTAF-EQ-C","interface",OTAF+"; README: contract equal to charges is allowed","A=C=1000 G=1200 P=400 T=0: basis 1000; G-P 800; A-P 600 -> 60000",paid(60000),("OTAF-EQ-C",100000,120000,40000,0,0,100000,N))
c("OTAF-ZERO","interface",OTAF+"; README: explicit zero contract yields a zero cap","A=0: cap=min(900,0)=0; P=0>=0 -> ZERO PRIMARY_AT_CAP; CWF accepts, releases 0",zero("PRIMARY_AT_CAP"),("OTAF-ZERO",100000,90000,0,0,0,0,N))
# --- one-cent boundaries
c("CENT-P-BELOW","policy",LIM,"C=1000 G=800 P=799.99 T=0: cap 80000-79999 = 1",paid(1),("CENT-P-BELOW",100000,80000,79999,0,0,P,N))
c("CENT-P-AT","policy",LIM+"; "+ZPREC,"P=80000 = cap 80000 -> no positive limit -> ZERO PRIMARY_AT_CAP",zero("PRIMARY_AT_CAP"),("CENT-P-AT",100000,80000,80000,0,0,P,N))
c("CENT-P-ABOVE","policy",LIM+"; "+ZPREC,"P=80001 > cap 80000 -> limits negative, floored -> ZERO PRIMARY_AT_CAP",zero("PRIMARY_AT_CAP"),("CENT-P-ABOVE",100000,80000,80001,0,0,P,N))
c("CENT-T-BELOW","policy",LIM,"P=0 T=79998+1=79999 < cap 80000 -> 1",paid(1),("CENT-T-BELOW",100000,80000,0,79998,1,P,N))
c("CENT-T-AT","policy",LIM+"; "+ZPREC,"T=79999+1=80000 = cap -> ZERO DEDUCTIONS_AT_CAP",zero("DEDUCTIONS_AT_CAP"),("CENT-T-AT",100000,80000,0,79999,1,P,N))
c("CENT-T-ABOVE","policy",LIM+"; "+ZPREC,"T=80000+1=80001 > cap -> ZERO DEDUCTIONS_AT_CAP",zero("DEDUCTIONS_AT_CAP"),("CENT-T-ABOVE",100000,80000,0,80000,1,P,N))
c("CENT-A-BELOW","policy",OTAF,"A=500 G=900 C=1000 P=499.99: cap 50000; 50000-49999 = 1",paid(1),("CENT-A-BELOW",100000,90000,49999,0,0,50000,N))
c("CENT-A-AT","policy",OTAF+"; "+ZPREC,"A=500 P=500 -> P at cap -> ZERO PRIMARY_AT_CAP",zero("PRIMARY_AT_CAP"),("CENT-A-AT",100000,90000,50000,0,0,50000,N))
c("CENT-G-UNDER-C","policy",LIM,"C=500.00 G=499.99 P=0 T=0: G-P 49999 < C-P 50000 -> 49999",paid(49999),("CENT-G-UNDER-C",50000,49999,0,0,0,P,N))
c("CENT-C-UNDER-G","policy",LIM,"C=499.99 G=500.00 P=0 T=0: C-P 49999 -> 49999",paid(49999),("CENT-C-UNDER-G",49999,50000,0,0,0,P,N))
c("CENT-P-OVER-T","policy",LIM,"C=G=1000 P=200.01 T=200.00: larger reduction is P -> 100000-20001 = 79999",paid(79999),("CENT-P-OVER-T",100000,100000,20001,20000,0,P,N))
c("CENT-T-OVER-P","policy",LIM,"C=G=1000 P=200.00 T=200.01: larger reduction is T -> 100000-20001 = 79999",paid(79999),("CENT-T-OVER-P",100000,100000,20000,20001,0,P,N))
# --- zeros and precedence
c("FULL-Y","policy",FULL,"Otherwise 900-300=600 payable, but full=Y -> ZERO PAYMENT_IN_FULL; still sent to CWF, accepted, releases 0",zero("PAYMENT_IN_FULL"),("FULL-Y",100000,90000,30000,0,0,P,"Y"))
c("FULL-Y-AND-P-HIGH","policy",FULL+"; "+ZPREC,"full=Y and P 950 > cap 900: payment-in-full wins precedence",zero("PAYMENT_IN_FULL"),("FULL-Y-AND-P-HIGH",100000,90000,95000,0,0,P,"Y"))
c("P-AND-T-AT-CAP","policy",LIM+"; "+ZPREC,"cap 800; P=800 and T=800 both at cap: PRIMARY_AT_CAP wins",zero("PRIMARY_AT_CAP"),("P-AND-T-AT-CAP",100000,80000,80000,80000,0,P,N))
c("ALL-ZERO","interface",ZPREC,"All amounts 0: cap 0, P 0 >= 0 -> PRIMARY_AT_CAP; P1MEDPRIM01 has no MSP period so accepted, releases 0",zero("PRIMARY_AT_CAP"),("ALL-ZERO",0,0,0,0,0,P,N))
c("GROSS-ZERO","policy",LIM+"; "+ZPREC,"G=0: cap 0; P=0 >= 0 -> PRIMARY_AT_CAP",zero("PRIMARY_AT_CAP"),("GROSS-ZERO",100000,0,0,0,0,P,N))
c("NO-PRIMARY","policy",LIM,"P=0 T=100: cap 800 - max(100,0) = 700 -> 70000; P1 no MSP period so CWF accepts with P=0",paid(70000),("NO-PRIMARY",100000,80000,0,10000,0,P,N))
# --- maximums
c("MAX-ALL","interface",MAXS,"C=G=9999999999 P=T=0 -> 9999999999",paid(9999999999),("MAX-ALL",9999999999,9999999999,0,0,0,P,N))
c("MAX-T-SUM","interface",MAXS,"T=9999999999+9999999999=19999999998 (11 digits) >= cap 9999999999 -> DEDUCTIONS_AT_CAP",zero("DEDUCTIONS_AT_CAP"),("MAX-T-SUM",9999999999,9999999999,0,9999999999,9999999999,P,N))
c("MAX-P","interface",MAXS,"P=9999999999 = cap -> PRIMARY_AT_CAP",zero("PRIMARY_AT_CAP"),("MAX-P",9999999999,9999999999,9999999999,0,0,P,N))
c("MAX-OTAF","interface",MAXS+"; "+OTAF,"A=C=G=9999999999 P=1 -> 9999999998",paid(9999999998),("MAX-OTAF",9999999999,9999999999,1,0,0,9999999999,N))
c("G-ABOVE-C","policy",LIM+"; README: gross may exceed charges","G=99999999.99 C=1.00 P=T=0: cap min = C = 100",paid(100),("G-ABOVE-C",100,9999999999,0,0,0,P,N))
# --- validation (interface)
REC=lambda id: (id,100000,90000,30000,0,0,None,N)
c("BAD-LEN-91","interface",IF,"91 bytes -> BAD_LENGTH, provisional @ID",inv("BAD_LENGTH"),raw="SHORT91     "+"0"*79)
c("BAD-LEN-93","interface",IF,"93 bytes (an otherwise valid 92-byte record + 'X') -> BAD_LENGTH, provisional @ID",inv("BAD_LENGTH"),raw="LONG93      "+"0000100000"+"0000090000"+"0000030000"+"0000000000"+"0000000000"+"----------"+"N"+"P1MEDPRIM01"+"20250610"+"X")
c("BAD-LEN-BLANK","interface",IF+"; README: a blank line is an invalid record, not EOF","0 bytes -> BAD_LENGTH",inv("BAD_LENGTH"),raw="")
c("BAD-ID-BLANK","interface",IF,"ID all spaces -> BAD_ID",inv("BAD_ID"),REC("BAD-ID-BLANK"),patch=[[0," "*12]])
c("BAD-ID-LOWER","interface",IF,"lowercase ID -> BAD_ID",inv("BAD_ID"),REC("BAD-ID-LOWER"),patch=[[0,"cms-ex3     "]])
c("BAD-ID-INNER-SP","interface",IF,"'AB CD' embedded space -> BAD_ID",inv("BAD_ID"),REC("BAD-ID-INNER-SP"),patch=[[0,"AB CD       "]])
c("BAD-ID-LEAD-SP","interface",IF,"' ABC' leading space -> BAD_ID",inv("BAD_ID"),REC("BAD-ID-LEAD-SP"),patch=[[0," ABC        "]])
c("BAD-ID-AT","interface",IF+"; README: '@' cannot occur in a valid input ID","'@0000000044' -> BAD_ID (cannot spoof a provisional ID)",inv("BAD_ID"),REC("BAD-ID-AT"),patch=[[0,"@0000000044 "]])
c("BAD-ID-AND-AMT","interface",IF,"bad ID and bad amount: ID checked first -> BAD_ID",inv("BAD_ID"),REC("BAD-ID-AND-AMT"),patch=[[0,"bad         "],[12,"ABCDEFGHIJ"]])
c("ID-12-CHARS","interface",IF,"12-char ID 'AZ09-_AZ09-_' valid; 900-300 = 600",paid(60000),REC("AZ09-_AZ09-_"))
cases[-1]["id"]="AZ09-_AZ09-_"; cases[-1]["expected"]["claim_id"]="AZ09-_AZ09-_"
c("BAD-AMT-SPACE","interface",IF,"charges ' 000100000' -> BAD_AMOUNT (real ID kept)",inv("BAD_AMOUNT"),REC("BAD-AMT-SPACE"),patch=[[12," 000100000"]])
c("BAD-AMT-PLUS","interface",IF+"; rules.md: signed fields unsupported","charges '+000100000' -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-AMT-PLUS"),patch=[[12,"+000100000"]])
c("BAD-AMT-UNDERSCORE","interface",IF,"charges '0000_00000' -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-AMT-UNDERSCORE"),patch=[[12,"0000_00000"]])
c("BAD-AMT-DECIMAL","interface",IF+"; rules.md: fractional cents unsupported","gross '0000900.00' -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-AMT-DECIMAL"),patch=[[22,"0000900.00"]])
c("BAD-AMT-COINS","interface",IF,"coinsurance '000000000A' -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-AMT-COINS"),patch=[[52,"000000000A"]])
c("BAD-CTR-PARTDASH","interface",IF+"; README: contract is digits or exactly ----------","contract '-----00000' -> BAD_AMOUNT (malformed contract is not BAD_CONTRACT)",inv("BAD_AMOUNT"),REC("BAD-CTR-PARTDASH"),patch=[[62,"-----00000"]])
c("BAD-CTR-SPACES","interface",IF+"; rules.md: no missing monetary field defaults","contract 10 spaces -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-CTR-SPACES"),patch=[[62," "*10]])
c("BAD-AMT-OVER-FLAG","interface",IF,"bad primary and bad flag: amounts first -> BAD_AMOUNT",inv("BAD_AMOUNT"),REC("BAD-AMT-OVER-FLAG"),patch=[[32,"00000003O0"],[72,"X"]])
c("BAD-CONTRACT","interface",IF+"; README: contract above charges is invalid","A=1000.01 > C=1000.00 -> BAD_CONTRACT",inv("BAD_CONTRACT"),("BAD-CONTRACT",100000,90000,30000,0,0,100001,N))
c("BAD-CTR-OVER-FLAG","interface",IF,"A>C and flag 'X': contract range first -> BAD_CONTRACT",inv("BAD_CONTRACT"),("BAD-CTR-OVER-FLAG",100000,90000,30000,0,0,100001,N),patch=[[72,"X"]])
c("BAD-FLAG-LOWER","interface",IF,"flag 'y' -> BAD_FLAG",inv("BAD_FLAG"),REC("BAD-FLAG-LOWER"),patch=[[72,"y"]])
c("BAD-FLAG-SPACE","interface",IF,"flag ' ' -> BAD_FLAG",inv("BAD_FLAG"),REC("BAD-FLAG-SPACE"),patch=[[72," "]])
c("STATE-REJ-CTR","interface",IF+"; "+STATE,"valid contract 100.00 parsed, then flag 'X' -> BAD_FLAG",inv("BAD_FLAG"),("STATE-REJ-CTR",100000,90000,30000,0,0,10000,N),patch=[[72,"X"]])
c("STATE-AFTER","interface",STATE+"; "+LIM,"No contract; must not inherit previous record's 100.00 contract: cap min(900,1000)=900 - 300 = 600 (leaked state would give ZERO)",paid(60000),REC("STATE-AFTER"))
c("BAD-FLAG-OVER-MBI","interface",IF,"flag 'X' and lowercase MBI: flag first -> BAD_FLAG",inv("BAD_FLAG"),REC("BAD-FLAG-OVER-MBI"),patch=[[72,"X"],[73,"p1medprim01"]])
c("BAD-MBI-LOWER","interface",IF,"MBI 'p1medprim01' -> BAD_MBI",inv("BAD_MBI"),REC("BAD-MBI-LOWER"),patch=[[73,"p1medprim01"]])
c("BAD-MBI-SPACE","interface",IF,"MBI 'P1MEDPRIM0 ' -> BAD_MBI",inv("BAD_MBI"),REC("BAD-MBI-SPACE"),patch=[[73,"P1MEDPRIM0 "]])
c("BAD-MBI-DASH","interface",IF,"MBI 'P1MED-RIM01' -> BAD_MBI",inv("BAD_MBI"),REC("BAD-MBI-DASH"),patch=[[73,"P1MED-RIM01"]])
c("BAD-MBI-OVER-DATE","interface",IF,"bad MBI and bad date: MBI first -> BAD_MBI",inv("BAD_MBI"),REC("BAD-MBI-OVER-DATE"),patch=[[73,"P1MED-RIM01"],[84,"2025ABCD"]])
c("STATE-AFTER-MBI","interface",STATE,"Valid no-contract record after a rejected BAD_MBI record: 900-300 = 600 (no state carried)",paid(60000),REC("STATE-AFTER-MBI"))
cases.insert(len(cases)-1, None)  # placeholder replaced below
cases.pop(len(cases)-2)
c("BAD-DATE-M13","interface",IF,"20251301 month 13 -> BAD_DATE",inv("BAD_DATE"),REC("BAD-DATE-M13"),dos="20251301")
c("BAD-DATE-M00","interface",IF,"20250001 month 00 -> BAD_DATE",inv("BAD_DATE"),REC("BAD-DATE-M00"),dos="20250001")
c("BAD-DATE-D00","interface",IF,"20250600 day 00 -> BAD_DATE",inv("BAD_DATE"),REC("BAD-DATE-D00"),dos="20250600")
c("BAD-DATE-D32","interface",IF,"20250632 day 32 -> BAD_DATE",inv("BAD_DATE"),REC("BAD-DATE-D32"),dos="20250632")
c("BAD-DATE-TEXT","interface",IF,"'2025-6-1' not digits -> BAD_DATE",inv("BAD_DATE"),REC("BAD-DATE-TEXT"),patch=[[84,"2025-6-1"]])
c("DATE-0631-OK","interface","README interface: date check is month 01-12 and day 01-31 only (no calendar check)","20250631 passes; 900-300=600; P1 entitled -> ACCEPTED",paid(60000),REC("DATE-0631-OK"),dos="20250631")
c("FULL-Y-BAD-AMT","interface",IF+"; README: validation always precedes payment-in-full evaluation","full=Y and charges 'ABC' -> BAD_AMOUNT, not PAYMENT_IN_FULL",inv("BAD_AMOUNT"),("FULL-Y-BAD-AMT",100000,90000,30000,0,0,None,"Y"),patch=[[12,"ABC0000000"]])
# --- CWF
B6=(100000,90000,30000,0,0,None,N)   # 900-300=600 payable
B0=(100000,90000,0,0,0,None,N)       # P=0 -> 900 payable
def r(id,b): return (id,)+b
c("CWF-NOT-ON-FILE","policy",CWF,"payment 60000; MBI P9NOTFILE09 has no B record -> REJECTED NOT_ENTITLED, released 0",("PAID",60000,"SECONDARY_PAYABLE","REJECTED","NOT_ENTITLED",0),r("CWF-NOT-ON-FILE",B6),mbi="P9NOTFILE09")
c("CWF-ENT-START-1","policy",CWF,"P4STARTS004 entitled from 20250601; DOS 20250531 one day before -> NOT_ENTITLED",("PAID",60000,"SECONDARY_PAYABLE","REJECTED","NOT_ENTITLED",0),r("CWF-ENT-START-1",B6),mbi="P4STARTS004",dos="20250531")
c("CWF-ENT-START","policy",CWF,"DOS 20250601 = entitlement start (inclusive) -> ACCEPTED 60000",paid(60000),r("CWF-ENT-START",B6),mbi="P4STARTS004",dos="20250601")
c("CWF-ENT-END","policy",CWF,"P3ENDENT003 entitled to 20250531; DOS 20250531 (inclusive) -> ACCEPTED",paid(60000),r("CWF-ENT-END",B6),mbi="P3ENDENT003",dos="20250531")
c("CWF-ENT-END+1","policy",CWF,"DOS 20250601 one day after entitlement end -> NOT_ENTITLED",("PAID",60000,"SECONDARY_PAYABLE","REJECTED","NOT_ENTITLED",0),r("CWF-ENT-END+1",B6),mbi="P3ENDENT003",dos="20250601")
c("CWF-ENT-OPEN","interface",CWF+"; README: 99999999 = open entitlement","P1 entitled 20200101-99999999; DOS 20991231 -> ACCEPTED",paid(60000),r("CWF-ENT-OPEN",B6),dos="20991231")
c("CWF-DUP","policy",CWF,"H P1MEDPRIM01 20250402 100000 posted; claim same MBI/DOS/charges 1000.00 -> DUPLICATE, payment 60000 kept, released 0",("PAID",60000,"SECONDARY_PAYABLE","REJECTED","DUPLICATE",0),r("CWF-DUP",B6),dos="20250402")
c("CWF-DUP-CENT+","policy",CWF,"charges 1000.01 vs history 1000.00 -> not duplicate; cap min(900,1000.01)=900-300=600 -> ACCEPTED",paid(60000),("CWF-DUP-CENT+",100001,90000,30000,0,0,None,N),dos="20250402")
c("CWF-DUP-CENT-","policy",CWF,"charges 999.99 vs 1000.00 -> not duplicate; 900-300 = 600 -> ACCEPTED",paid(60000),("CWF-DUP-CENT-",99999,90000,30000,0,0,None,N),dos="20250402")
c("CWF-DUP-DAY+","policy",CWF,"DOS 20250403 vs history 20250402 -> not duplicate -> ACCEPTED",paid(60000),r("CWF-DUP-DAY+",B6),dos="20250403")
c("CWF-DUP-OTHER-MBI","policy",CWF,"same DOS/charges as history but MBI P2MSPEGHP02 (history is P1) -> not duplicate; P2 MSP covers 20250402 but P=300>0 -> ACCEPTED",paid(60000),r("CWF-DUP-OTHER-MBI",B6),mbi="P2MSPEGHP02",dos="20250402")
c("CWF-MSP-START","policy",CWF,"P6MSPEDGE06 MSP 20250301-20250331; DOS 20250301, P=0 -> payment 90000, MSP_PRIMARY_NOT_BILLED, released 0",("PAID",90000,"SECONDARY_PAYABLE","REJECTED","MSP_PRIMARY_NOT_BILLED",0),r("CWF-MSP-START",B0),mbi="P6MSPEDGE06",dos="20250301")
c("CWF-MSP-END","policy",CWF,"DOS 20250331 (MSP end, inclusive), P=0 -> MSP_PRIMARY_NOT_BILLED",("PAID",90000,"SECONDARY_PAYABLE","REJECTED","MSP_PRIMARY_NOT_BILLED",0),r("CWF-MSP-END",B0),mbi="P6MSPEDGE06",dos="20250331")
c("CWF-MSP-BEFORE","policy",CWF,"DOS 20250228 day before MSP period, P=0 -> ACCEPTED 90000",paid(90000),r("CWF-MSP-BEFORE",B0),mbi="P6MSPEDGE06",dos="20250228")
c("CWF-MSP-AFTER","policy",CWF,"DOS 20250401 day after MSP period, P=0 -> ACCEPTED 90000",paid(90000),r("CWF-MSP-AFTER",B0),mbi="P6MSPEDGE06",dos="20250401")
c("CWF-MSP-P-1C","policy",CWF,"inside MSP period, primary 0.01 billed -> 90000-1 = 89999 ACCEPTED",paid(89999),("CWF-MSP-P-1C",100000,90000,1,0,0,None,N),mbi="P6MSPEDGE06",dos="20250315")
c("CWF-ENT-OVER-DUP","policy",CWF+"; check order entitlement, duplicate, MSP","P3ENDENT003 has history 20250610 charges 100000 but entitlement ended 20250531 -> NOT_ENTITLED wins",("PAID",60000,"SECONDARY_PAYABLE","REJECTED","NOT_ENTITLED",0),r("CWF-ENT-OVER-DUP",B6),mbi="P3ENDENT003")
c("CWF-DUP-OVER-MSP","policy",CWF+"; check order entitlement, duplicate, MSP","P5HISTORY05 MSP covers 20250610, P=0 and history matches 20250610/1500000 -> DUPLICATE wins; payment min(14000,15000)-max(1556,0)=12444 -> 1244400",("PAID",1244400,"SECONDARY_PAYABLE","REJECTED","DUPLICATE",0),("CWF-DUP-OVER-MSP",1500000,1400000,0,155600,0,None,N),mbi="P5HISTORY05")
c("EX3-DUP","policy",EX3+"; "+CWF,"CMS-EX3 amounts, MBI P5HISTORY05 already posted 20250610/1500000 -> payment 50000, DUPLICATE, released 0",("PAID",50000,"SECONDARY_PAYABLE","REJECTED","DUPLICATE",0),("EX3-DUP",1500000,1400000,1250000,155600,0,1300000,N),mbi="P5HISTORY05")
c("EX3-NOT-ENT","policy",EX3+"; "+CWF,"CMS-EX3 amounts, P3ENDENT003 entitlement ended 20250531 -> payment 50000, NOT_ENTITLED, released 0",("PAID",50000,"SECONDARY_PAYABLE","REJECTED","NOT_ENTITLED",0),("EX3-NOT-ENT",1500000,1400000,1250000,155600,0,1300000,N),mbi="P3ENDENT003")
c("EX3-NOT-BILLED","policy",EX3+"; "+CWF,"CMS-EX3 but primary 0: payment min(14000,13000)-max(1556,0)=11444 -> 1144400; P2 MSP covers DOS and P=0 -> MSP_PRIMARY_NOT_BILLED, released 0",("PAID",1144400,"SECONDARY_PAYABLE","REJECTED","MSP_PRIMARY_NOT_BILLED",0),("EX3-NOT-BILLED",1500000,1400000,0,155600,0,1300000,N),mbi="P2MSPEGHP02")
c("CWF-ZERO-SENT","policy",FULL+"; "+CWF,"full=Y -> ZERO PAYMENT_IN_FULL; valid so still sent to CWF; P9NOTFILE09 -> REJECTED NOT_ENTITLED, released 0",("ZERO",0,"PAYMENT_IN_FULL","REJECTED","NOT_ENTITLED",0),("CWF-ZERO-SENT",100000,90000,30000,0,0,None,"Y"),mbi="P9NOTFILE09")
c("CWF-ZERO-MSP","policy",CWF,"all-zero claim -> ZERO PRIMARY_AT_CAP; P2 MSP covers 20250610 and P=0 -> REJECTED MSP_PRIMARY_NOT_BILLED",("ZERO",0,"PRIMARY_AT_CAP","REJECTED","MSP_PRIMARY_NOT_BILLED",0),("CWF-ZERO-MSP",0,0,0,0,0,None,N),mbi="P2MSPEGHP02")
c("CWF-BATCH-A","interface",CWF+"; README: duplicates are against posted history","first of two identical claims (P1/20250701/1000.00) in this batch: no history match -> ACCEPTED 60000",paid(60000),r("CWF-BATCH-A",B6),dos="20250701")
c("CWF-BATCH-B","interface",CWF+"; README: duplicates are against posted history","second identical claim, different ID: batch claims are not CWF history -> ACCEPTED 60000",paid(60000),r("CWF-BATCH-B",B6),dos="20250701")
c("CWF-INVALID-NOT-SENT","interface","README: invalid claims are NOT_SENT / CLAIM_INVALID","MBI not on file AND bad flag: validation fails first -> INVALID BAD_FLAG, never sent to CWF",inv("BAD_FLAG"),r("CWF-INVALID-NOT-SENT",B6),mbi="P9NOTFILE09",patch=[[72,"Z"]])
assert None not in cases
OK=set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
for n,x in enumerate(cases,1):
    if "input" in x and (len(x["id"])>12 or not set(x["id"])<=OK):
        cid=f"LDG-{n:03d}"
        if x["input"]["id"]==x["id"]: x["input"]["id"]=cid
        if x["expected"]["claim_id"]==x["id"]: x["expected"]["claim_id"]=cid
    x["claim_id_note"]="claim ID field differs from case name (case names may exceed the 12-byte ID field)" if "input" in x and x["input"]["id"]!=x["id"] else None
    if x["claim_id_note"] is None: del x["claim_id_note"]
ref={"beneficiaries":[
 {"mbi":"P1MEDPRIM01","entitled_from":"20200101","entitled_to":"99999999","msp_from":None,"msp_to":None,"story":"Medicare primary, entitled open-ended (default ledger beneficiary)"},
 {"mbi":"P2MSPEGHP02","entitled_from":"20180701","entitled_to":"99999999","msp_from":"20240601","msp_to":"20251130","story":"Employer plan pays first 2024-06-01..2025-11-30"},
 {"mbi":"P3ENDENT003","entitled_from":"20100101","entitled_to":"20250531","msp_from":None,"msp_to":None,"story":"Entitlement ends 2025-05-31"},
 {"mbi":"P4STARTS004","entitled_from":"20250601","entitled_to":"99999999","msp_from":None,"msp_to":None,"story":"Entitlement starts 2025-06-01"},
 {"mbi":"P5HISTORY05","entitled_from":"20190101","entitled_to":"99999999","msp_from":"20250101","msp_to":"20251231","story":"MSP beneficiary with a posted $15,000 claim on 2025-06-10"},
 {"mbi":"P6MSPEDGE06","entitled_from":"20200101","entitled_to":"99999999","msp_from":"20250301","msp_to":"20250331","story":"One-month MSP period for boundary tests"}],
 "history":[
 {"mbi":"P5HISTORY05","dos":"20250610","charges":1500000,"story":"Posted claim matching CMS-EX3 charges"},
 {"mbi":"P1MEDPRIM01","dos":"20250402","charges":100000,"story":"Posted $1,000.00 claim for duplicate boundaries"},
 {"mbi":"P3ENDENT003","dos":"20250610","charges":100000,"story":"Posted claim after entitlement end (precedence test)"}]}
meta={"title":"Independent MSP payment + CWF expectation ledger (Stage 2, written before any Python)",
 "derivation":"Hand-derived from CMS Pub. 100-05 Ch. 5 §40.8-40.8.3 (PDF SHA-256 a2ea49af...f693, see docs/rules.md), Pub. 100-04 Ch. 27 §20, Pub. 100-05 Ch. 5 §10.1 and the README interface. No value was copied from COBOL output or fixtures/expected.json; CWF reference data is new and does not reuse fixtures/cwf.json.",
 "categories":{"policy":"expected value follows from a cited CMS rule (reason/CWF codes themselves are demo-defined)","interface":"expected value follows from the README/rules.md demo interface decisions, not CMS policy"},
 "formula":"payment = 0 if full=Y; else B = A if contract else C; cap = min(G, B); T = D + K; payment = max(0, cap - max(T, P)) == max(0, min(G-P, G-T, B-P, B-T))",
 "limits":"Parity with COBOL on these cases is not proof of Medicare correctness."}
json.dump({"meta":meta,"defaults":{"mbi":"P1MEDPRIM01","dos":"20250610"},"cwf_reference":ref,"cases":cases},open(__import__("pathlib").Path(__file__).with_name("expectations.json"),"w"),indent=1,ensure_ascii=False)
print(len(cases), sum(x["category"]=="policy" for x in cases))
