#!/usr/bin/env python3
"""Run a deliberate overflow mutant and the same regression on the fixed RTL."""
import json
import argparse
import signal
import os
import pathlib
import platform
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=pathlib.Path, default=ROOT/'evidence/local')
OUT = parser.parse_args().out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
versions = {'platform': platform.platform(), 'machine': platform.machine(), 'python': platform.python_version()}
for name, cmd in {'icarus':['iverilog','-V'], 'cocotb':['cocotb-config','--version']}.items():
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    versions[name] = p.stdout.splitlines()[0]
if platform.system() == 'Darwin':
    for key in ['machdep.cpu.brand_string', 'hw.memsize']:
        versions[key] = subprocess.check_output(['/usr/sbin/sysctl','-n',key], text=True).strip()
results = []
with tempfile.TemporaryDirectory(prefix='fifo-evidence-') as tmp:
    tmp = pathlib.Path(tmp)
    source = (ROOT/'rtl/async_fifo.sv').read_text()
    needle = 'if (winc && !wfull) mem[wbin[ASIZE-1:0]] <= wdata;'
    assert source.count(needle) == 1
    # Deliberately introduced bug, only in a temporary copy: full writes overwrite unread data.
    mutant = tmp/'async_fifo_bug.sv'
    mutant.write_text(source.replace(needle, 'if (winc) mem[wbin[ASIZE-1:0]] <= wdata;'))
    for name, bug, wp, rp in [('seeded_overflow',True,10,13), ('fixed_10_13',False,10,13), ('fixed_17_10',False,17,10), ('fixed_7_19',False,7,19)]:
        build = tmp/name
        xml = tmp/(name+'.xml')
        rtl = mutant if bug else ROOT/'rtl/async_fifo.sv'
        cmd = ['make', f'SIM_BUILD={build}', f'COCOTB_RESULTS_FILE={xml}', f'VERILOG_SOURCES={rtl} {ROOT}/rtl/sync_2ff.sv']
        env = dict(os.environ, WRITE_NS=str(wp), READ_NS=str(rp))
        start = time.monotonic()
        with (OUT/(name+'.log')).open('w') as log:
            p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                p.wait(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                log.write('HARNESS_TIMEOUT: killed process group after 90 seconds\n')
        try:
            cases = ET.parse(xml).getroot().findall('.//testcase')
        except (OSError, ET.ParseError):
            cases = []
        failures = [c for c in cases if c.find('failure') is not None or c.find('error') is not None]
        log_text = (OUT/(name+'.log')).read_text()
        expected = (len(cases)==2 and len(failures)==1 and failures[0].attrib['name']=='test_full_empty_reset_ordering' and 'ORDER_MISMATCH' in log_text and p.returncode != 0) if bug else (len(cases)==2 and not failures and p.returncode==0)
        results.append(dict(name=name, seeded=bug, clocks_ns=[wp,rp], seconds=round(time.monotonic()-start,3), rc=p.returncode, tests=len(cases), failures=len(failures), expected_result=expected, command=cmd))
        if xml.exists(): (OUT/(name+'.xml')).write_bytes(xml.read_bytes())
        print(results[-1])
(OUT/'summary.json').write_text(json.dumps(dict(environment=versions, results=results),indent=2)+'\n')
assert all(r['expected_result'] for r in results), 'unexpected verification result; inspect evidence'
