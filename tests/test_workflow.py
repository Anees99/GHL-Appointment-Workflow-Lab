import tempfile
from pathlib import Path
import unittest
from appointment_lab.core import *
BASE={'event_id':'a','location_id':'loc','contact_id':'c','appointment_id':'x','sequence':1,'kind':'booked','occurred_at':'2026-10-26T09:00:00+05:00','start_at':'2026-10-27T11:00:00+05:00','consent':True}
class WorkflowTests(unittest.TestCase):
    def setUp(self):self.w=Workflow(':memory:')
    def tearDown(self):self.w.close()
    def event(self,**kw):return {**BASE,**kw}
    def test_booking(self):
        self.w.apply(BASE);self.assertEqual(len(self.w.snapshot()['reminders']),1)
    def test_duplicate(self):
        self.w.apply(BASE);self.assertEqual(self.w.apply(BASE)['outcome'],'duplicate')
    def test_reused_id_conflict(self):
        self.w.apply(BASE)
        with self.assertRaises(ValueError):self.w.apply(self.event(consent=False))
    def test_reschedule_cancels_previous(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',kind='rescheduled',sequence=2,start_at='2026-10-28T11:00:00+05:00'))
        self.assertEqual([r['state'] for r in self.w.snapshot()['reminders']],['cancelled','planned'])
    def test_cancel(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',kind='cancelled',sequence=2))
        self.assertEqual(self.w.snapshot()['reminders'][0]['state'],'cancelled')
    def test_stale_event(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',kind='cancelled',sequence=2))
        self.assertEqual(self.w.apply(self.event(event_id='c'))['outcome'],'stale_ignored')
    def test_no_consent(self):self.w.apply(self.event(consent=False));self.assertEqual(self.w.snapshot()['reminders'],[])
    def test_string_consent_rejected(self):
        with self.assertRaises(ValueError):self.w.apply(self.event(consent='true'))
    def test_timezone_required(self):
        with self.assertRaises(ValueError):self.w.apply(self.event(start_at='2026-10-27T11:00:00'))
    def test_past_booking(self):
        with self.assertRaises(ValueError):self.w.apply(self.event(start_at='2020-01-01T00:00:00Z'))
    def test_optout_blocks_reschedule(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',kind='opted_out',sequence=2))
        self.w.apply(self.event(event_id='c',kind='rescheduled',sequence=3))
        self.assertEqual(len(self.w.snapshot()['reminders']),1)
        self.assertEqual(self.w.snapshot()['reminders'][0]['state'],'cancelled')
    def test_optout_all_appointments(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',appointment_id='y'))
        self.w.apply(self.event(event_id='c',kind='opted_out',sequence=2))
        self.assertTrue(all(r['state']=='cancelled' for r in self.w.snapshot()['reminders']))
    def test_location_isolation(self):
        self.w.apply(BASE);self.w.apply(self.event(location_id='other'))
        self.w.apply(self.event(event_id='b',kind='opted_out',sequence=2))
        self.assertEqual(sum(r['state']=='planned' for r in self.w.snapshot()['reminders']),1)
    def test_due_preview(self):
        self.w.apply(BASE);self.assertEqual(len(self.w.due('2026-10-27T05:30:00Z')),1)
    def test_after_appointment_no_reminder(self):
        self.w.apply(BASE);self.assertEqual(self.w.due('2026-10-27T06:00:00Z'),[])
    def test_no_catchup_late_booking(self):
        self.w.apply(self.event(occurred_at='2026-10-27T10:30:00+05:00'));self.assertEqual(self.w.snapshot()['reminders'],[])
    def test_unknown_appointment_transition(self):
        with self.assertRaises(ValueError):self.w.apply(self.event(kind='cancelled'))
    def test_terminal_state(self):
        self.w.apply(BASE);self.w.apply(self.event(event_id='b',kind='completed',sequence=2))
        with self.assertRaises(ValueError):self.w.apply(self.event(event_id='c',kind='rescheduled',sequence=3))
    def test_transaction_rollback(self):
        with self.assertRaises(ValueError):self.w.apply(self.event(kind='cancelled'))
        self.assertEqual(self.w.snapshot()['events'],[])
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'q.sqlite';a=Workflow(p);a.apply(BASE);a.close();b=Workflow(p)
            try:self.assertEqual(b.apply(BASE)['outcome'],'duplicate')
            finally:b.close()
