import unittest
from datetime import datetime, timezone
from openfootball_cc0_source import audit_documents, dataset_key, fresh_cache_entry

NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
TS = int(datetime(2026, 10, 9, 19, tzinfo=timezone.utc).timestamp())


def fixture(**changes):
    f = {'id': 'espn-eng.1-77', 'home': 'Arsenal', 'away': 'Chelsea',
         'league_code': 'eng.1', 'phase': 'finished', 'score': '2-1',
         'start_timestamp': TS}
    f.update(changes)
    return {'fixture': f, 'stats': {'home': {'shots_on': 4}}}


class OpenFootballCC0SourceTests(unittest.TestCase):
    def test_dataset_mapping_and_tz(self):
        self.assertEqual(dataset_key(fixture()['fixture']), '2026-27/en.1.json')
        self.assertIsNone(dataset_key(fixture(start_timestamp=None)['fixture']))
        self.assertIsNone(dataset_key(fixture(league_code='bra.1')['fixture']))

    def test_verified_and_conflict_do_not_modify_scouts_or_score(self):
        good = fixture()
        bad = fixture(score='1-0')
        docs = {'2026-10-09': {'matches': {'a': good, 'b': bad}}}
        def fetch(key):
            self.assertEqual(key, '2026-27/en.1.json')
            return [{'date': '2026-10-09', 'team1': 'Arsenal',
                     'team2': 'Chelsea', 'score': {'ft': [2, 1]}}]
        status, cache = audit_documents(docs, {}, fetch, NOW)
        self.assertEqual((status['cross_verified'], status['conflicts']), (1, 1))
        self.assertEqual(status['checked'], 2)
        self.assertEqual(status['datasets_fetched'], 1)
        self.assertEqual(bad['fixture']['score'], '1-0')
        self.assertEqual(good['stats']['home']['shots_on'], 4)
        self.assertEqual(good['score_verifications']['openfootball_cc0']['status'], 'cross_verified')
        self.assertIn('2026-27/en.1.json', cache['entries'])

    def test_no_live_mutation_no_odd_invention_and_cache(self):
        live = fixture(phase='live')
        final = fixture()
        cache = {'entries': {'2026-27/en.1.json': {
            'fetched_at': NOW.isoformat(),
            'matches': [{'date': '2026-10-09', 'team1': 'Arsenal',
                        'team2': 'Chelsea', 'score': {'ft': [2, 1]}}]}}}
        status, _ = audit_documents({'2026-10-09': {'matches': {'l': live, 'f': final}}},
                                    cache, lambda key: self.fail('unexpected request'), NOW)
        self.assertEqual(status['cache_hits'], 1)
        self.assertNotIn('score_verifications', live)
        self.assertNotIn('closing_odds', final)
        self.assertNotIn('odds_quotes', final)

    def test_unavailable_source_never_claims_verification(self):
        f = fixture()
        def fail(key):
            raise OSError('offline')
        status, _ = audit_documents({'2026-10-09': {'matches': {'x': f}}}, {}, fail, NOW)
        self.assertEqual(status['unavailable'], 1)
        self.assertEqual(status['cross_verified'], 0)
        self.assertNotIn('score_verifications', f)

    def test_ambiguous_duplicate_rejected(self):
        row = {'date': '2026-10-09', 'team1': 'Arsenal',
               'team2': 'Chelsea', 'score': {'ft': [2, 1]}}
        f = fixture()
        status, _ = audit_documents({'2026-10-09': {'matches': {'x': f}}},
                                    {}, lambda key: [row, row.copy()], NOW)
        self.assertEqual(status['ambiguous'], 1)
        self.assertNotIn('score_verifications', f)


if __name__ == '__main__':
    unittest.main()
