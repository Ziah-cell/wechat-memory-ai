"""A recycled UI token may yield a candidate, never a verified message."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wechat_memory import live_read

OccurrenceSession = getattr(live_read, 'OccurrenceSession', None)


def snapshot(*rows, **identity):
    result = dict(status='snapshot',process=12,started='123456',window=34,
                  root='ChatSingleWindowwxid_fixture',list_token='list',rows=[
                      dict(token=token,text=text,kind=kind) for token,text,kind in rows])
    result.update(identity)
    return result


def text(token, content=None):
    return token, token if content is None else content, 'text'


class OccurrenceTests(unittest.TestCase):
    def session(self):
        self.assertIsNotNone(OccurrenceSession, 'occurrence observer is missing')
        return OccurrenceSession()

    def test_baseline_and_restart_do_not_replay_visible_history(self):
        baseline=snapshot(text('a'),text('b'),text('c'))
        session=self.session()
        self.assertEqual(session.accept(baseline),[])
        self.assertEqual(session.accept(baseline),[])
        new=snapshot(text('a'),text('b'),text('c'),text('d','same'))
        self.assertEqual(len(session.accept(new)),1)
        self.assertEqual(self.session().accept(new),[])
        self.assertEqual(session.report()['candidate_texts'],1)

    def test_empty_initialization_waits_for_a_nonempty_baseline(self):
        session=self.session()
        self.assertEqual(session.accept(snapshot()),[])
        self.assertEqual(session.report()['status'],'initializing')
        self.assertEqual(session.accept(snapshot(text('a'),text('b'))),[])
        self.assertEqual(session.report()['candidate_rows'],0)

    def test_recycled_tokens_and_same_text_keep_distinct_local_occurrences(self):
        session=self.session()
        session.accept(snapshot(text('a','old a'),text('b','old b'),text('c'),text('d')))
        first=session.accept(snapshot(text('b','old b'),text('c'),text('d'),text('a','same')))
        second=session.accept(snapshot(text('c'),text('d'),text('a','same'),text('b','same')))
        self.assertEqual([row.text for row in first+second],['same','same'])
        self.assertNotEqual(first[0].observation_id,second[0].observation_id)
        self.assertTrue(all(row.direction=='unverified' for row in first+second))
        self.assertEqual(session.report()['reused_token_candidates'],2)
        self.assertEqual(session.report()['candidate_texts'],2)
        self.assertEqual(session.report()['front_evictions'],2)
        self.assertEqual(session.report()['seen_occurrences'],6)

    def test_old_token_and_content_reappearance_stops_whole_batch(self):
        session=self.session()
        session.accept(snapshot(text('a'),text('b'),text('c'),text('d')))
        session.accept(snapshot(text('c'),text('d'),text('e')))
        before=session.report()
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(text('d'),text('e'),text('fresh'),text('a')))
        after=session.report()
        self.assertEqual(after['stop_reason'],'occurrence_reappeared')
        for key in ('candidate_rows','candidate_texts','front_evictions','seen_occurrences','snapshots'):
            self.assertEqual(after[key],before[key])
        with self.assertRaises(live_read.ReadError): session.accept(snapshot(text('d'),text('e')))

    def test_later_generation_does_not_forget_an_earlier_token_content_pair(self):
        session=self.session()
        session.accept(snapshot(text('a','old'),text('b'),text('c')))
        session.accept(snapshot(text('b'),text('c'),text('a','new')))
        session.accept(snapshot(text('c'),text('a','new'),text('d')))
        session.accept(snapshot(text('a','new'),text('d'),text('e')))
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(text('d'),text('e'),text('a','old')))
        self.assertEqual(session.report()['stop_reason'],'occurrence_reappeared')

    def test_anchor_changes_weak_overlap_and_removal_never_become_candidates(self):
        for next_rows in ((text('c'),text('d')), (text('b'),text('c')),
                          (text('a','changed'),text('b'),text('c')),
                          (text('b'),text('a'),text('c'),text('d')),
                          (text('x'),text('y'),text('z'))):
            session=self.session()
            session.accept(snapshot(text('a'),text('b'),text('c')))
            with self.assertRaises(live_read.ReadError): session.accept(snapshot(*next_rows))
            self.assertEqual(session.report()['stop_reason'],'message_continuity_lost')
            self.assertEqual(session.report()['candidate_rows'],0)

    def test_binding_change_invalid_and_visual_snapshots_stop_without_private_output(self):
        for change in ({'window':35},{'process':13},{'started':'999'},
                       {'root':'ChatSingleWindowwxid_other'},{'list_token':'other'},
                       {'status':'visual_snapshot'},{'rows':'PRIVATE'}):
            session=self.session()
            session.accept(snapshot(text('a'),text('b')))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot(text('a'),text('b'),**change))
            report=json.dumps(session.report())
            self.assertNotIn('PRIVATE',report)
            self.assertNotIn('wxid_',report)
            self.assertEqual(session.report()['status'],'stopped')

    def test_occurrence_capacity_counts_recycled_generations_and_is_atomic(self):
        session=self.session()
        # A bounded sliding viewport with three reused tokens. Each generation
        # changes content, so capacity must count occurrences, not unique tokens.
        rows=[text(str(i),str(i)) for i in range(3)]
        session.accept(snapshot(*rows))
        for i in range(3,4096):
            rows=rows[1:]+[text(str(i%3),str(i))]
            session.accept(snapshot(*rows))
        self.assertEqual(session.report()['seen_occurrences'],4096)
        self.assertEqual(session.accept(snapshot(*rows)),[])
        before=session.report()
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(*rows[1:],text(str(4096%3),'4096')))
        self.assertEqual(session.report()['stop_reason'],'session_occurrence_limit')
        self.assertEqual(session.report()['candidate_rows'],before['candidate_rows'])

    def test_nontext_and_blank_rows_count_but_do_not_produce_text_candidates(self):
        session=self.session()
        session.accept(snapshot(text('a'),text('b')))
        result=session.accept(snapshot(text('a'),text('b'),('c','time','other'),text('d','  '),text('e','x')))
        self.assertEqual([row.text for row in result],['x'])
        self.assertEqual(session.report()['candidate_rows'],3)
        report=session.report()
        self.assertEqual(report['mode'],'occurrence_candidates')
        for field in ('sender_verified','history_boundary_verified','server_message_ids_available',
                      'real_send_supported','model_called'):
            self.assertFalse(report[field])

    def test_strict_default_still_rejects_recycled_tokens_with_changed_content(self):
        session=live_read.ReadSession()
        session.accept(snapshot(text('a'),text('b'),text('c')))
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(text('b'),text('c'),text('a','new')))
        self.assertEqual(session.report()['stop_reason'],'message_token_reused')

    def test_cli_explicit_candidate_mode_reports_counts_and_preserves_native_failure(self):
        stream=io.StringIO()
        with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream), \
                patch.object(live_read.time,'sleep'):
            reader.return_value.__enter__.return_value.read.side_effect=[
                snapshot(text('a'),text('b'),text('c')),
                snapshot(text('b'),text('c'),text('a','new')),
                live_read.ReadError('window_minimized')]
            result=live_read.main(['--client-path','fixture.exe','--observe-occurrences'])
        self.assertEqual(result,3)
        reports=[json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(reports[-1]['mode'],'occurrence_candidates')
        self.assertEqual(reports[-1]['candidate_texts'],1)
        self.assertEqual(reports[-1]['stop_reason'],'window_minimized')
        self.assertNotIn('wxid_',stream.getvalue())
        self.assertNotIn('"new"',stream.getvalue())


if __name__=='__main__': unittest.main()
