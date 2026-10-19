import subprocess, os
EXE=os.path.expanduser('~/repos/devinexecdemo/build/msp-batch')
B='B2MSP000000120200101999999992025010120251231'
cases={
 'crcr':(B+'\r\r\n').encode(),
 'cr_only_line':(B+'\n\r\n').encode(),
 'cr_eof_nolf':(B+'\r').encode(),
 'ff':(B+'\n\x0c').encode(),
 'ff_start':('\x0c'+B+'\n').encode(),
 'cr_at_65':(B+' '*20+'\r\n').encode(),
 'X_at_64':(B+' '*19+'X\n').encode(),
 'highbyte_after64':(B+' '*20).encode()+b'\xff\n',
 'nul_after64':(B+' '*20).encode()+b'\x00\n',
 'tab_after64':(B+' '*20+'\t\n'),
 'sp_then_cr':(B+'   \r\n').encode(),
 'B_lead_space_line':(' '+B+'\n').encode(),
}
REC='CMS-EX3     0001500000000140000000012500000000155600000000000000130000N2MSP000000120250315'
open('in.dat','w').write(REC+'\n')
for k,v in cases.items():
    if isinstance(v,str): v=v.encode()
    open('cwf.dat','wb').write(v)
    for f in ('o.csv','t.csv'):
        if os.path.exists(f): os.remove(f)
    p=subprocess.run([EXE,'in.dat','cwf.dat','o.csv','t.csv'],capture_output=True)
    row=open('o.csv').read().splitlines()[1:] if os.path.exists('o.csv') else None
    print(k,p.returncode,row)
