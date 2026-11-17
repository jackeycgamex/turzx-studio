from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from claude_token_usage import ClaudeTokenUsage, estimate_cost

NOW = datetime.fromisoformat('2026-11-17T15:00:00+08:00').timestamp()
RATES = {'claude-test': {'input_cost_per_token': 2e-6, 'output_cost_per_token': 10e-6,
                         'cache_read_input_token_cost': .2e-6, 'cache_creation_input_token_cost': 2.5e-6,
                         'cache_creation_input_token_cost_above_1hr':4e-6}}


def row(key='msg1', timestamp='2026-11-17T01:00:00Z', **usage):
    return {'type':'assistant','timestamp':timestamp,'requestId':'request-'+key,
            'message':{'id':key,'model':'claude-test','content':[{'type':'text','text':'PRIVATE CONTENT'}],
                       'usage':dict(input_tokens=10,output_tokens=20,cache_creation_input_tokens=100,
                                    cache_read_input_tokens=1000,**usage)}}


class TokenUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.logs=self.root/'projects'
        self.logs.mkdir()
        self.pricing=self.root/'prices.json'
        self.pricing.write_text(json.dumps({'models':RATES}))
        self.counter=ClaudeTokenUsage([self.logs],self.root/'usage.sqlite',clock=lambda:NOW,pricing_path=self.pricing)

    def write(self,name,rows):
        path=self.logs/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        return path

    def test_daily_and_monday_week_boundaries(self):
        self.write('one.jsonl',[row('before','2026-11-15T15:59:59Z'),row('monday','2026-11-15T16:00:00Z'),
                               row('yesterday','2026-11-16T15:59:59Z'),row('today','2026-11-16T16:00:00Z'),
                               row('future','2026-11-17T16:00:00Z')])
        value=self.counter.collect(NOW)
        self.assertEqual(value['today']['tokens'],1130)
        self.assertEqual(value['week']['tokens'],3390)
        self.assertAlmostEqual(value['today']['cost_usd'],.00067)

    def test_duplicates_across_blocks_files_and_restarts_count_once(self):
        self.write('one.jsonl',[row(),row()])
        self.write('subagents/two.jsonl',[row()])
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)
        self.assertEqual(self.counter.collect(NOW)['today']['messages'],1)
        restarted=ClaudeTokenUsage([self.logs],self.root/'usage.sqlite',clock=lambda:NOW,pricing_path=self.pricing)
        self.assertEqual(restarted.collect(NOW)['today']['tokens'],1130)
        self.assertNotIn(b'PRIVATE CONTENT',(self.root/'usage.sqlite').read_bytes())

    def test_append_partial_record_and_streaming_final_update(self):
        path=self.write('one.jsonl',[row()])
        self.counter.collect(NOW)
        final=row();final['message']['usage']['output_tokens']=50
        with path.open('a') as f:f.write(json.dumps(final))
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)
        with path.open('a') as f:f.write('\n'+json.dumps(row('second'))+'\n')
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],2290)

    def test_truncated_and_deleted_files_do_not_keep_old_totals(self):
        path=self.write('one.jsonl',[row(),row('second')])
        self.counter.collect(NOW)
        self.write('one.jsonl',[row('replacement')])
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)
        path.unlink()
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],0)

    def test_unknown_model_keeps_tokens_without_fabricated_dollars(self):
        item=row();item['message']['model']='claude-unknown'
        self.write('one.jsonl',[item])
        result=self.counter.collect(NOW)['today']
        self.assertEqual(result['tokens'],1130)
        self.assertIsNone(result['cost_usd'])
        self.assertEqual(result['unpriced_messages'],1)

    def test_invalid_and_nonassistant_lines_are_ignored(self):
        user=row();user['type']='user'
        synthetic=row();synthetic['message']['model']='<synthetic>'
        bad=row();bad['timestamp']='bad'
        self.write('one.jsonl',[user,synthetic,bad,{'type':'assistant'},row()])
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)

    def test_empty_and_missing_roots_are_distinct(self):
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],0)
        self.logs.rmdir()
        self.assertIsNone(self.counter.collect(NOW)['today'])

    def test_pricing_change_recalculates_persistent_cache(self):
        self.write('one.jsonl',[row()])
        first=self.counter.collect(NOW)['today']['cost_usd']
        pricing={'claude-test':{k:v*2 for k,v in RATES['claude-test'].items()}}
        self.pricing.write_text(json.dumps({'models':pricing}))
        self.assertAlmostEqual(self.counter.collect(NOW)['today']['cost_usd'],first*2)

    def test_clock_crossing_weeks_rebuilds_existing_file_offsets(self):
        self.write('one.jsonl',[row()])
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)
        self.assertEqual(self.counter.collect(NOW+7*86400)['week']['tokens'],0)
        self.assertEqual(self.counter.collect(NOW)['today']['tokens'],1130)

    def test_shared_cache_separates_source_roots(self):
        self.write('one.jsonl',[row()])
        self.assertEqual(self.counter.collect(NOW)['week']['tokens'],1130)
        other=self.root/'other'
        other.mkdir()
        counter=ClaudeTokenUsage([other],self.counter.cache_path,pricing_path=self.pricing)
        self.assertEqual(counter.collect(NOW)['week']['tokens'],0)
        self.assertEqual(self.counter.collect(NOW)['week']['tokens'],1130)

    def test_cache_hour_split_and_long_context_pricing(self):
        pricing={'claude-test':dict(RATES['claude-test'],input_cost_per_token_above_100k_tokens=4e-6)}
        usage={'input_tokens':100001,'cache_creation_input_tokens':100,
               'cache_creation':{'ephemeral_1h_input_tokens':25}}
        self.assertAlmostEqual(estimate_cost('claude-test',usage,pricing),100001*4e-6+75*2.5e-6+25*4e-6)
        self.assertEqual(estimate_cost('claude-test-20261117',usage,pricing),estimate_cost('claude-test',usage,pricing))

    def test_failed_read_preserves_last_totals_with_error_status(self):
        self.write('one.jsonl',[row()])
        self.counter.refresh_if_due()
        self.pricing.write_text('invalid')
        self.counter.last_refresh=None
        self.counter.refresh_if_due()
        result=self.counter.snapshot()
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['today']['tokens'],1130)


if __name__=='__main__':
    unittest.main()
