import unittest
from datetime import datetime, timezone
import web_export as x


class PublicDashboardTests(unittest.TestCase):
    def test_markets_are_observations_not_profitable_bets(self):
        rows=[{'outcomes':{'correct_score':'2-1','over_15':True,'over_25':True,
                           'over_35':False,'btts':True,'result':'home'},
               'phase':'finished','signals':[]}]
        result=x.market_history(rows)
        self.assertEqual(result['matches'],1)
        self.assertEqual(next(v for v in result['markets'] if v['market']=='Over 2.5 FT')['occurred'],1)
        self.assertNotIn('pl',result)

    def test_paper_only_pregame_and_verified_odds(self):
        f={'start_timestamp':2000000000}
        signal={'market':'1x2','selection':'home','odds':2.4,'probability':46,
                'ev_pct':10.4,'sample_size':12,'model':'test',
                'captured_at':datetime.fromtimestamp(1999999900,timezone.utc).isoformat(),
                'status':'settled','won':True}
        got=x.pregame_signal(signal,f)
        self.assertEqual(got['paper_pl_u'],1.4)
        late={**signal,'captured_at':datetime.fromtimestamp(2000000001,timezone.utc).isoformat()}
        self.assertIsNone(x.pregame_signal(late,f))
        self.assertIsNone(x.pregame_signal({**signal,'sample_size':1},f))

    def test_no_financial_data_from_bolsa_in_public_row(self):
        row={'fixture':{'id':'test','home':'Casa','away':'Fora','score':'2-1','phase':'finished'},
             'stats':{'home':{'shots_on':4,'net_pl':9999},'away':{'corners':5}},
             'paper_signals':[],'bolsa':{'net_pl':123456},
             'odds_quotes':[{'market':'1x2','selection':'home','odds':2.2,
                             'bookmaker':'test','captured_at':'2026-10-08T12:00:00Z'}]}
        public=x.public_row(row,'2026-10-08')
        self.assertNotIn('bolsa',public)
        self.assertNotIn('net_pl',str(public))
        self.assertEqual(public['outcomes']['over_25'],True)
        self.assertEqual(public['stats']['home']['shots_on'],4)
        self.assertEqual(public['odds'][0]['odd'],2.2)

    def test_no_settlements_means_unknown_profit_not_zero(self):
        result=x.paper_summary([{'signals':[]}])
        self.assertIsNone(result['paper_pl_u'])
        self.assertEqual(result['settled'],0)
        self.assertEqual(result['status'],'insufficient_data')

    def test_alerts_never_invent_an_ev_from_only_odds(self):
        row={'phase':'scheduled','home':'A','away':'B','id':'id','day':'2026-10-08',
             'signals':[],'odds':[{'sel':'home','odd':2.5,'at':'2026-10-08T12:00:00Z'}],
             'stats':{'home':{},'away':{}},'observed_at':''}
        alerts=x.alerts_from([row])
        self.assertEqual(alerts[0]['kind'],'odds_watch')
        self.assertIn('EV+ indisponível',alerts[0]['detail'])

if __name__=='__main__':
    unittest.main()
