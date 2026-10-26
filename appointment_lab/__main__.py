import argparse
import json
from pathlib import Path
from .core import Workflow
p=argparse.ArgumentParser(description='GHL-oriented appointment automation simulator')
p.add_argument('--db',default='workflow.sqlite')
s=p.add_subparsers(dest='command',required=True)
a=s.add_parser('replay');a.add_argument('events')
s.add_parser('snapshot')
a=s.add_parser('due');a.add_argument('at')
a=p.parse_args();w=Workflow(a.db)
try:
    if a.command=='replay':result=[w.apply(e) for e in json.loads(Path(a.events).read_text())]
    elif a.command=='snapshot':result=w.snapshot()
    else:result={'mode':'preview_only','reminders':w.due(a.at)}
    print(json.dumps(result,indent=2))
finally:w.close()
