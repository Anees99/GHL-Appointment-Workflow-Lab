"""Local appointment state machine. Does not connect to GHL or send messages."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime,timedelta,timezone

KINDS={'booked','rescheduled','cancelled','completed','no_show','opted_out'}
def stamp(value):
    if not isinstance(value,str):raise ValueError('Timestamp must be ISO text')
    try:d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('Invalid timestamp') from None
    if d.utcoffset() is None:raise ValueError('Timezone offset required')
    return d.astimezone(timezone.utc)

def normalized(e):
    required={'event_id','location_id','contact_id','appointment_id','sequence','kind','occurred_at'}
    if not isinstance(e,dict) or not required<=set(e) or set(e)-required-{'start_at','consent'}:raise ValueError('Invalid event fields')
    for k in ['event_id','location_id','contact_id','appointment_id']:
        if not isinstance(e[k],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',e[k]):raise ValueError('Invalid identifier')
    if type(e['sequence'])!=int or e['sequence']<1:raise ValueError('Positive integer sequence required')
    if e['kind'] not in KINDS:raise ValueError('Unknown event kind')
    stamp(e['occurred_at'])
    if e['kind'] in {'booked','rescheduled'}:
        if type(e.get('consent'))!=bool:raise ValueError('Explicit boolean consent required')
        if stamp(e.get('start_at'))<=stamp(e['occurred_at']):raise ValueError('Appointment must be in future')
    return e

class Workflow:
    def __init__(self,path):
        self.db=sqlite3.connect(path,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events(location TEXT,event_id TEXT,digest TEXT,outcome TEXT,PRIMARY KEY(location,event_id));
        CREATE TABLE IF NOT EXISTS appointments(location TEXT,id TEXT,contact TEXT,sequence INTEGER,state TEXT,start_at TEXT,PRIMARY KEY(location,id));
        CREATE TABLE IF NOT EXISTS suppressions(location TEXT,contact TEXT,PRIMARY KEY(location,contact));
        CREATE TABLE IF NOT EXISTS reminders(location TEXT,appointment TEXT,contact TEXT,sequence INTEGER,due_at TEXT,state TEXT,PRIMARY KEY(location,appointment,sequence));
        """)
    def close(self):self.db.close()
    def apply(self,event):
        e=normalized(event);loc=e['location_id'];aid=e['appointment_id'];contact=e['contact_id']
        digest=hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            previous=self.db.execute('SELECT digest,outcome FROM events WHERE location=? AND event_id=?',(loc,e['event_id'])).fetchone()
            if previous:
                if previous['digest']!=digest:raise ValueError('Event ID reused with different payload')
                self.db.execute('COMMIT');return {'outcome':'duplicate','original_outcome':previous['outcome']}
            old=self.db.execute('SELECT * FROM appointments WHERE location=? AND id=?',(loc,aid)).fetchone()
            if old and old['contact']!=contact:raise ValueError('Appointment/contact mismatch')
            if e['kind']=='opted_out':
                self.db.execute('INSERT OR IGNORE INTO suppressions VALUES(?,?)',(loc,contact))
                self.db.execute("UPDATE reminders SET state='cancelled' WHERE location=? AND contact=? AND state='planned'",(loc,contact))
                outcome='suppressed'
            elif old and e['sequence']<=old['sequence']:outcome='stale_ignored'
            else:
                if not old and e['kind']!='booked':raise ValueError('Unknown appointment requires booking first')
                if old and (old['state'] in {'cancelled','completed','no_show'} or e['kind']=='booked'):raise ValueError('Invalid state transition')
                self.db.execute("UPDATE reminders SET state='cancelled' WHERE location=? AND appointment=? AND state='planned'",(loc,aid))
                start=e.get('start_at',old['start_at'] if old else None)
                self.db.execute('INSERT OR REPLACE INTO appointments VALUES(?,?,?,?,?,?)',(loc,aid,contact,e['sequence'],e['kind'],start))
                blocked=self.db.execute('SELECT 1 FROM suppressions WHERE location=? AND contact=?',(loc,contact)).fetchone()
                if e['kind'] in {'booked','rescheduled'} and e['consent'] and not blocked:
                    due=stamp(start)-timedelta(hours=1)
                    if due>stamp(e['occurred_at']):
                        self.db.execute('INSERT INTO reminders VALUES(?,?,?,?,?,?)',(loc,aid,contact,e['sequence'],due.isoformat(),'planned'))
                outcome='applied'
            self.db.execute('INSERT INTO events VALUES(?,?,?,?)',(loc,e['event_id'],digest,outcome))
            self.db.execute('COMMIT');return {'outcome':outcome}
        except Exception:self.db.execute('ROLLBACK');raise
    def snapshot(self):
        return {name:[dict(r) for r in self.db.execute('SELECT * FROM '+name+' ORDER BY 1,2')] for name in ['appointments','reminders','suppressions','events']}
    def due(self,now):
        current=stamp(now)
        result=[]
        for row in self.db.execute("SELECT r.*,a.start_at FROM reminders r JOIN appointments a ON a.location=r.location AND a.id=r.appointment WHERE r.state='planned' AND NOT EXISTS(SELECT 1 FROM suppressions s WHERE s.location=r.location AND s.contact=r.contact)"):
            if stamp(row['due_at'])<=current<stamp(row['start_at']):result.append(dict(row))
        return result # Preview only; no messages sent or marked delivered.
