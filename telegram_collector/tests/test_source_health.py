import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram_collector.source_health import assess, run

NOW=datetime(2026,10,25,20,0,tzinfo=timezone.utc)

class SourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.path=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def put(self,filename,data):
        p=self.path/filename
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(data),encoding="utf-8")

    def test_healthy_all_sources_and_priority(self):
        self.put("status.json",{"collected_at":NOW.isoformat(),"quotes_observed":1300})
        self.put("priority-espn-status.json",{"checked_at":NOW.isoformat(),
                                             "boards_ok":8,"priority_fixtures_seen":32,
                                             "new_quotes":9})
        self.put("public-no-key/status.json",{"checked_at":NOW.isoformat(),
                                               "status":"ok","quotes_indicative":50})
        self.put("public-no-key/pinnacle-status.json",{"checked_at":NOW.isoformat(),
                    "status":"ok","odds_observed":100,"matches_checked":5,"errors":[]})
        self.put("priority-coverage.json",{"checked_at":NOW.isoformat(),
                   "important_games":20,"verified_bookmaker_games":10,
                   "missing_bookmaker_price_games":7})
        out=run(self.path,NOW)
        self.assertEqual(out["sources_ok"],4)
        self.assertEqual(out["overall_status"],"ok")
        self.assertEqual(out["priority_coverage"]["verified_bookmaker_games"],10)
        self.assertEqual(out["source_status"]["pinnacle"]["games_priced"],5)
        self.assertTrue((self.path/"source-health.json").is_file())

    def test_blocked_or_stale_sources_never_reported_healthy(self):
        self.put("status.json",{"collected_at":(NOW-timedelta(hours=2)).isoformat(),
                                 "quotes_observed":800})
        self.put("public-no-key/pinnacle-status.json",{
            "checked_at":NOW.isoformat(),"status":"partial_blocked",
            "odds_observed":300,"errors":[{"http_status":403}]})
        report=assess(self.path,NOW)
        self.assertEqual(report["sources_ok"],0)
        self.assertEqual(report["overall_status"],"unavailable")
        self.assertEqual(report["source_status"]["nexus"]["status"],"stale")
        self.assertEqual(report["source_status"]["pinnacle"]["status"],"partial_blocked")
        self.assertEqual(report["source_status"]["pinnacle"]["denied_requests"],1)
        self.assertEqual(report["priority_coverage"]["status"],"unavailable")

    def test_status_file_corruption_no_invented_data(self):
        self.put("status.json",[1,2,3])
        report=assess(self.path,NOW)
        self.assertEqual(report["source_status"]["nexus"]["status"],"unavailable")
        self.assertIsNone(report["source_status"]["nexus"]["odds_observed"])

if __name__=="__main__":
    unittest.main()
