import unittest
from datetime import datetime, timezone, timedelta

from pregame_refresh import fixture_candidates, compare_lineups, new_quote, espn_quotes, update_live_details
from unittest.mock import patch

class PregameRefreshTests(unittest.TestCase):
    def test_refresh_includes_live_minute_44_but_excludes_finished(self):
        now=1800000000
        doc={'matches':{
          'fotmob-1':{'fixture':{'phase':'live','start_timestamp':now-44*60}},
          'fotmob-2':{'fixture':{'phase':'live','start_timestamp':now-115*60}},
          'fotmob-3':{'fixture':{'phase':'finished','start_timestamp':now-44*60}},
          'fotmob-4':{'fixture':{'phase':'scheduled','start_timestamp':now+60*60}}
        }}
        found={x[1] for x in fixture_candidates({'today':doc},now)}
        self.assertEqual(found,{'fotmob-1','fotmob-2','fotmob-4'})

    def test_live_details_merge_only_confirmed_measurements_and_events(self):
        row={'fixture':{'phase':'live','minute':44},'thermometer':{
            'points':[{'minute':5,'value':-30}]},
             'stats':{'home':{'shots_on':1},'away':{}},
             'events':[{'minute':4,'type':'goal','side':'away','text':'A'}]}
        with patch('pregame_refresh.momentum',return_value=[
              {'minute':5,'value':-30},{'minute':42,'value':35}]), \
             patch('pregame_refresh.fotmob_stats',return_value={
                 'home':{'shots_on':2},'away':{'shots_on':4}}), \
             patch('pregame_refresh.fotmob_events',return_value=[
                {'minute':4,'type':'goal','side':'away','text':'A'},
                {'minute':40,'type':'goal','side':'away','text':'B'}]):
            outcome=update_live_details(row,{})
        self.assertEqual(outcome['pressure_added'],1)
        self.assertEqual(outcome['events_added'],1)
        self.assertEqual(row['thermometer']['points'][-1]['minute'],42)
        self.assertEqual(row['stats']['away']['shots_on'],4)
        self.assertEqual(len(row['events']),2)

    def test_scheduled_never_gets_live_scouts(self):
        row={'fixture':{'phase':'scheduled'}}
        self.assertEqual(update_live_details(row,{}),{'pressure_added':0,
                         'events_added':0,'stats_added':0})
        self.assertNotIn('thermometer',row)

    def test_only_matches_near_start(self):
        now=1800000000
        doc={'matches':{
            'fotmob-1':{'fixture':{'phase':'scheduled','start_timestamp':now+30*60}},
            'fotmob-2':{'fixture':{'phase':'scheduled','start_timestamp':now+90*60}},
            'fotmob-3':{'fixture':{'phase':'finished','start_timestamp':now-5*60}},
            'fotmob-4':{'fixture':{'phase':'live','start_timestamp':now-9*60}}
        }}
        selected=fixture_candidates({'2026-10-09':doc},now)
        ids={x[1] for x in selected}
        self.assertEqual(ids,{'fotmob-1','fotmob-4'})

    def test_confirmed_lineup_replaces_prediction(self):
        row={'lineups':{'home':{'status':'predicted','starters':[{'name':'Provável'}]}}}
        n=compare_lineups(row,{'home':{'status':'confirmed','starters':[{'name':'Titular'}]}})
        self.assertEqual(n,1)
        self.assertEqual(row['lineups']['home']['status'],'confirmed')
        self.assertEqual(compare_lineups(row,{'home':{'status':'predicted','starters':[{'name':'Provável'}]}}),0)
        self.assertEqual(row['lineups']['home']['starters'][0]['name'],'Titular')

    def test_timestamp_only_does_not_trigger_new_lineup(self):
        row={'lineups':{'home':{'status':'confirmed','updated_at':'2026-10-09T11:10:00Z',
                               'starters':[{'name':'Jogador'}]}}}
        same={'home':{'status':'confirmed','updated_at':'2026-10-09T11:20:00Z',
                      'starters':[{'name':'Jogador'}]}}
        self.assertEqual(compare_lineups(row,same),0)

    def test_real_espn_prices_are_recorded_pre_kickoff(self):
        now=int(datetime.now(timezone.utc).timestamp())
        row={'fixture':{'phase':'scheduled','start_timestamp':now+1800}}
        packet={'pickcenter':[{'homeTeamOdds':{'decimalOdds':2.1},
           'drawOdds':{'decimalOdds':3.25},'awayTeamOdds':{'decimalOdds':3.4},
           'provider':{'name':'Bookmaker verificado'}}]}
        self.assertEqual(espn_quotes(packet,row,now),3)
        self.assertEqual(espn_quotes(packet,row,now),0)
        self.assertEqual(len(row['odds_quotes']),3)
        self.assertEqual(row['odds_quotes'][0]['source'],'ESPN')
        self.assertEqual(row['odds_quotes'][0]['bookmaker'],'Bookmaker verificado')
        self.assertEqual(espn_quotes(packet,row,now+1801),0)

    def test_no_offers_means_no_invented_odds(self):
        now=int(datetime.now(timezone.utc).timestamp())
        row={'fixture':{'phase':'scheduled','start_timestamp':now+2000}}
        self.assertEqual(espn_quotes({'pickcenter':[]},row,now),0)
        self.assertFalse(row.get('odds_quotes'))

    def test_price_history_keeps_first_and_last_values(self):
        row={}
        self.assertTrue(new_quote(row,'home',2.15,'Casa A','ESPN','t1'))
        for k in range(12):
            new_quote(row,'home',2.16+k/100,'Casa A','ESPN',f't{k+2}')
        offers=[q for q in row['odds_quotes'] if q.get('selection')=='home']
        self.assertLessEqual(len(offers),6)
        self.assertEqual(offers[0]['odds'],2.15)
        self.assertEqual(offers[-1]['odds'],2.27)

if __name__=='__main__':unittest.main()
