import unittest
from datetime import datetime,timezone
import team_form as f
import web_export as x


class TeamFormTests(unittest.TestCase):
    def fixture(self,i,ts,home='Casa',away='Fora',score='2-1',phase='finished'):
        return {'id':'espn-bra.1-'+str(i),'start_timestamp':ts,'phase':phase,
                'home':home,'away':away,'home_id':'101','away_id':'202','score':score,
                'league':'bra.1'}

    def test_last_ten_by_match_time_not_today(self):
        current=self.fixture(100,3000000000,phase='scheduled')
        older=[self.fixture(i,2999999999-i*86400) for i in range(15)]
        after=[self.fixture(101,3000000100)]
        result=f.history_before(older+after,current,'101')
        self.assertEqual(len(result),10)
        self.assertTrue(all(m['ts']<current['start_timestamp'] for m in result))
        self.assertEqual(result[0]['result'],'V')
        self.assertEqual(result[0]['opponent'],'Fora')
        self.assertTrue(all(m['ts']<=result[0]['ts'] for m in result))

    def test_home_away_orientation_correct(self):
        current=self.fixture(90,3000000000)
        older=[self.fixture(1,2900000000,score='1-3')]
        away=f.history_before(older,current,'202')
        self.assertEqual(away[0]['gf'],3)
        self.assertEqual(away[0]['ga'],1)
        self.assertEqual(away[0]['venue'],'Fora')
        self.assertEqual(away[0]['result'],'V')

    def test_excludes_same_game_and_future(self):
        current=self.fixture(99,3000000000)
        games=[current,self.fixture(1,3000000001),self.fixture(2,2990000000,score='2-0')]
        result=f.history_before(games,current,'101')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['gf'],2)

    def test_short_sample_is_visible_not_fake_ten(self):
        current=self.fixture(99,3000000000)
        result=f.summarise(f.history_before([self.fixture(1,2900000000)],
                                             current,'101'),'ESPN')
        self.assertEqual(result['available'],1)
        self.assertFalse(result['complete'])
        self.assertEqual(result['requested'],10)
        self.assertEqual(result['games'][0]['score'],'2-1')
        publish=x.public_form(result)
        self.assertEqual(publish['available'],1)
        self.assertFalse(publish['complete'])

    def test_form_only_from_past_and_not_ev(self):
        current=self.fixture(99,3000000000)
        current['home_id']='101'
        source=f.summarise(f.history_before([self.fixture(1,2900000000)],
                                              current,'101'),'ESPN')
        row={'fixture':current,'team_form':{'home':source}}
        public=x.public_row(row,'2026-10-09')
        self.assertEqual(public['form']['home']['available'],1)
        self.assertEqual(public['form']['away']['available'],0)
        self.assertNotIn('ev_pct',str(public['form']))

    def test_exact_three_calendar_days_window_present(self):
        from pathlib import Path
        script=Path(x.__file__).read_text(encoding='utf-8')
        self.assertIn('for i in range(3)',script)
        script=Path(f.__file__).read_text(encoding='utf-8')
        self.assertIn('WINDOW_DAYS = 3',script)


if __name__=='__main__':
    unittest.main()
