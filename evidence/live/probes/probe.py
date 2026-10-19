import subprocess, os
EXE=os.path.expanduser('~/repos/devinexecdemo/build/msp-batch')
REC='CMS-EX3     '+'0001500000'+'0001400000'+'0001250000'+'0000155600'+'0000000000'+'0001300000'+'N'+'2MSP0000001'+'20250315'
assert len(REC)==92
B='B2MSP000000120200101999999992025010120251231'
H='H5HIST000001202503150001500000'
cases={
 'ok':(B+'\n').encode(),
 'nofinalnl':B.encode(),
 'crlf':(B+'\r\n').encode(),
 'blankline':(B+'\n\n').encode(),
 'trailspaces64':(B+' '*20+'\n').encode(),
 'trailspaces65':(B+' '*21+'\n').encode(),
 'trailspaces100':(B+' '*56+'\n').encode(),
 'long_garbage65':(B+' '*20+'X\n').encode(),
 'B28':(B[:28]+'\n').encode(),
 'Bpartialdash':(B[:28]+'--------20251231\n').encode(),
 'Bdash_and_space':(B[:28]+'-------- -------\n').encode(),
 'lowerb':('b'+B[1:]+'\n').encode(),
 'mbispaces':('B'+' '*11+B[12:]+'\n').encode(),
 'mbilower':('B2msp0000001'+B[12:]+'\n').encode(),
 'tab':(B[:20]+'\t'+B[21:]+'\n').encode(),
 'H_ok':(H+'\n').encode(),
 'H_trail':(H+'X\n').encode(),
 'H_short':(H[:29]+'\n').encode(),
 'empty':b'',
 'onlynl':b'\n',
 'nul':(B+'\n').encode().replace(b'2025',b'20\x0025',1),
 'B_badentdate':(B[:13]+'2020013199999999'+B[29:]+'\n').encode(),
 'B1000':''.join('B%011d'%i+B[12:]+'\n' for i in range(1000)).encode(),
 'B1001':''.join('B%011d'%i+B[12:]+'\n' for i in range(1001)).encode(),
 'cr_mid':(B+'\r'+'\n').encode().replace(b'\r\n',b'\rX\n'),
 'dupB_first_wins':(B+'\n'+'B2MSP0000001'+'2030010199999999'+'----------------'+'\n').encode(),
}
open('in.dat','wb').write((REC+'\n').encode())
for k,v in cases.items():
    open('cwf.dat','wb').write(v)
    for f in ('o.csv','t.csv'):
        if os.path.exists(f): os.remove(f)
    p=subprocess.run([EXE,'in.dat','cwf.dat','o.csv','t.csv'],capture_output=True)
    row=open('o.csv').read().splitlines()[1:] if os.path.exists('o.csv') else None
    print(k,p.returncode,p.stderr.decode().strip().replace('\n',' | ')[:90],row)
