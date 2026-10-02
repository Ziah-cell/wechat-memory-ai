"""Pure visual diagnostics explain failed gates without exposing pixels or text."""
import json
import unittest

from wechat_memory import live_read
from test_visual_direction import visual_snapshot


FAILURES = ('geometry_invalid','background_unsupported','edges_inconsistent','foreground_evidence_absent',
            'avatar_inconclusive','incoming_bubble_unconfirmed','incoming_green_conflict',
            'self_bubble_unconfirmed')
REASONS = (*FAILURES,'incoming_evidence','self_evidence','not_text')


class VisualReasonTests(unittest.TestCase):
    def test_every_reason_direction_kind_combination_is_validated(self):
        for reason in REASONS:
            for direction in ('incoming_candidate','self_candidate','unknown'):
                for kind in ('text','other'):
                    with self.subTest(reason=reason,direction=direction,kind=kind):
                        raw=visual_snapshot()
                        raw['rows']=[dict(token='private-token',kind=kind,direction=direction,reason=reason)]
                        allowed = ((kind=='other' and reason=='not_text' and direction=='unknown') or
                                   (kind=='text' and ((reason in FAILURES and direction=='unknown') or
                                    (reason=='incoming_evidence' and direction=='incoming_candidate') or
                                    (reason=='self_evidence' and direction=='self_candidate'))))
                        if allowed:
                            self.assertEqual(live_read.visual_report(raw)['reason_counts'][reason],1)
                        else:
                            with self.assertRaises(live_read.ReadError): live_read.visual_report(raw)

    def test_counts_include_zero_reasons_and_do_not_export_private_values(self):
        raw=visual_snapshot()
        report=live_read.visual_report(raw)
        self.assertEqual(set(report['reason_counts']),set(REASONS))
        self.assertEqual(sum(report['reason_counts'].values()),report['rows'])
        self.assertEqual(sum(report['reason_counts'][key] for key in FAILURES),report['unknown_texts'])
        self.assertEqual(report['reason_counts']['not_text'],report['rows']-report['text_rows'])
        self.assertEqual(set(report),{'status','rows','text_rows','incoming_candidates','self_candidates',
            'unknown_texts','reason_counts','capture_attempts','sender_verified','history_boundary_verified',
            'real_send_supported','model_called'})
        self.assertNotIn('wxid_',json.dumps(report))
        self.assertNotIn('token',json.dumps(report))
        raw['rows']=[]
        self.assertEqual(live_read.visual_report(raw)['reason_counts'],dict.fromkeys(REASONS,0))

    def test_malformed_or_missing_reasons_fail_with_a_sanitized_error(self):
        for value in ('PRIVATE',None,False,1,[],{}):
            with self.subTest(value=value):
                raw=visual_snapshot()
                raw['rows'][0]['reason']=value
                with self.assertRaises(live_read.ReadError) as error: live_read.visual_report(raw)
                self.assertEqual(str(error.exception),'invalid_snapshot')
        raw=visual_snapshot()
        del raw['rows'][0]['reason']
        with self.assertRaises(live_read.ReadError): live_read.visual_report(raw)

    def test_capture_attempts_are_bounded_and_required_only_for_pure_diagnostics(self):
        for attempts in (1,2,3):
            raw=visual_snapshot()
            raw['capture_attempts']=attempts
            self.assertEqual(live_read.visual_report(raw)['capture_attempts'],attempts)
        for value in (0,4,True,None,'PRIVATE',[],{}):
            raw=visual_snapshot()
            raw['capture_attempts']=value
            with self.assertRaises(live_read.ReadError): live_read.visual_report(raw)
        raw=visual_snapshot()
        del raw['capture_attempts']
        with self.assertRaises(live_read.ReadError): live_read.visual_report(raw)

    def test_diagnostics_cannot_enter_plain_or_joint_observation_protocols(self):
        raw=visual_snapshot()
        with self.assertRaises(live_read.ReadError): live_read.ReadSession().accept(raw)
        with self.assertRaises(live_read.ReadError): live_read.validate_visual_text_snapshot(raw)
        raw['status']='visual_text_snapshot'
        for row in raw['rows']: row['text']='PRIVATE'
        with self.assertRaises(live_read.ReadError): live_read.validate_visual_text_snapshot(raw)


if __name__=='__main__': unittest.main()
