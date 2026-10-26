import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
out=ROOT/'evaluation';out.mkdir(exist_ok=True)
r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
(out/'tests.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
if r.returncode:print(r.stdout+r.stderr);raise SystemExit(r.returncode)
if 'HubSpot' in ROOT.name:
    from sync_lab.core import plan,read_csv,reconcile
    report=plan(read_csv((ROOT/'examples/contacts.csv').read_text()))
    assert report['summary']=={'input_rows':6,'planned_contacts':2,'duplicate_rows_skipped':1,'rejected_rows':3}
    (out/'plan.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    result=reconcile(report['batches'][0],json.loads((ROOT/'examples/response.json').read_text()))
    assert len(result['confirmed'])==2
    (out/'reconciliation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
else:
    from appointment_lab.core import Workflow
    with tempfile.TemporaryDirectory() as d:
        w=Workflow(Path(d)/'demo.sqlite')
        try:
            events=json.loads((ROOT/'examples/events.json').read_text())
            outcomes=[w.apply(e) for e in events]
            assert outcomes[2]['outcome']=='duplicate'
            snap=w.snapshot();assert all(r['state']=='cancelled' for r in snap['reminders'])
            assert not w.due('2026-10-27T07:30:00Z')
            (out/'demo.json').write_text(json.dumps({'fixture_kind':'synthetic','outcomes':outcomes,'snapshot':snap},indent=2),encoding='utf-8')
        finally:w.close()
(out/'verification.json').write_text(json.dumps({'python':platform.python_version(),'unit_test_exit':r.returncode,'synthetic_demo_passed':True,'live_crm_tested':False},indent=2),encoding='utf-8')
print(r.stderr.split('----------------------------------------------------------------------')[-1].strip())
print('Synthetic integration demo passed; live CRM not tested.')
