"""Must Win: league primaryId, tabela verificável e conferências sem ranking fictício."""
import unittest
from unittest.mock import patch
from coletar import canonical_league_ids, fotmob_list
from fotmob_three_days import assign_fixture
from standings_context import (league_table, make_context, espn_table,
                                espn_league_code, fetch_table)


def table_rows(prefix, count=15, first_id=1000):
    return [
        {'idx':i,'id':first_id+i,'name':f'{prefix} {i}',
         'played':24,'pts':63-i,'goalConDiff':i}
        for i in range(1,count+1)]


class CanonicalLeagueTests(unittest.TestCase):
    def test_primary_id_replaces_season_specific_id(self):
        self.assertEqual(canonical_league_ids({'id':1000001407,'primaryId':268}),
                         ('268','1000001407'))
        self.assertEqual(canonical_league_ids({'id':913550,'primaryId':130}),
                         ('130','913550'))
        self.assertEqual(canonical_league_ids({'id':230}),('230','230'))
        self.assertEqual(canonical_league_ids({'id':'not-verified'}),('','not-verified'))

    def test_fotmob_match_keeps_both_ids_and_fixture_identity(self):
        packet={'leagues':[{'id':1000001407,'primaryId':268,'name':'Série A',
          'matches':[{'id':4839201,'home':{'id':10277,'name':'São Paulo'},
                      'away':{'id':10276,'name':'Vasco da Gama'},
                      'status':{'started':True,'finished':False,
                                'liveTime':{'short':"30'"},
                                'utcTime':'2026-10-17T21:00:00Z'}}]}]}
        with patch('coletar.fetch', return_value=packet):
            matches=fotmob_list('2026-10-17')
        self.assertEqual(len(matches),1)
        f=matches[0]
        self.assertEqual(f['league_id'],'268')
        self.assertEqual(f['league_edition_id'],'1000001407')
        self.assertTrue(f['league_id_verified'])
        self.assertEqual(f['home_id'],'10277')
        self.assertEqual(f['away_id'],'10276')
        prior={'fixture':{**f,'league_id':'1000001407'},
               'pregame_baseline':{'captured_at':'2026-10-17T19:00:00Z'},
               'odds_quotes':[{'odds':2.1}], 'thermometer':{'points':[{'m':28,'v':31}]}}
        updated=assign_fixture(prior,f)
        self.assertEqual(updated['fixture']['league_id'],'268')
        self.assertEqual(updated['odds_quotes'][0]['odds'],2.1)
        self.assertEqual(updated['thermometer']['points'][0]['m'],28)
        self.assertIn('pregame_baseline',updated)

    def test_fotmob_table_and_mustwin_uses_same_canonical_id(self):
        rows=table_rows('Brazil',20,first_id=10270)
        t=league_table({'details':{'id':268,'name':'Série A','selectedSeason':'2026'},
                        'table':[{'data':{'table':{'all':rows}}}]},'268')
        self.assertIsNotNone(t)
        f={'league_id':'268','home_id':'10277','away_id':'10276','home':'Brazil 7',
           'away':'Brazil 6'}
        ctx=make_context(f,t)
        self.assertEqual(ctx['home']['position'],7)
        self.assertEqual(ctx['away']['position'],6)
        self.assertEqual(ctx['home']['points'],56)
        self.assertEqual(ctx['source'],'FotMob')
        self.assertIsNone(make_context({**f,'league_id':'1000001407'},t))

    def test_mls_conferences_not_mixed_or_named_playoff_zones(self):
        groups=[
          {'name':'Conferência Leste','data':{'table':{'all':table_rows('East',15,1000)}}},
          {'name':'Conferência Oeste','data':{'table':{'all':table_rows('West',15,2000)}}}
        ]
        table=league_table({'details':{'id':130,'name':'MLS','selectedSeason':'2026'},
                            'table':groups},'130')
        self.assertIsNotNone(table)
        self.assertEqual(len(table['groups']),2)
        self.assertEqual(table['teams'],[])
        same_rank={'league_id':'130','home_id':'1002','away_id':'2002'}
        ctx=make_context(same_rank,table)
        self.assertIsNotNone(ctx,'Empate de posições entre conferências não é erro')
        self.assertEqual(ctx['home']['group'],'Conferência Leste')
        self.assertEqual(ctx['away']['group'],'Conferência Oeste')
        self.assertFalse(any(r['kind'] in ('buscar_g4','sair_z4','evitar_z4')
                             for side in ('home','away') for r in ctx[side]['reasons']))
        self.assertIsNone(league_table({'details':{'id':42,'name':'Copa'},
                                         'table':groups},'42'))
        overlapping=groups+[groups[0]]
        self.assertIsNone(league_table({'details':{'id':130},'table':overlapping},'130'))

    def test_espn_mls_conferences_match_names_only_uniquely(self):
        children=[]
        for conf,prefix,first in [('Eastern','East',4000),('Western','West',5000)]:
            entries=[]
            for i in range(1,16):
                entries.append({'team':{'id':str(first+i),'displayName':prefix+' '+str(i)},
                                'stats':[{'name':'rank','value':i},
                                         {'name':'points','value':42-i},
                                         {'name':'gamesPlayed','value':25}]})
            children.append({'name':conf,'standings':{'entries':entries}})
        packet={'season':{'year':2026},'children':children}
        table=espn_table(packet,'130','usa.1')
        self.assertIsNotNone(table)
        context=make_context({'league_id':'130','home':'East 1','away':'West 1'},table)
        self.assertIsNotNone(context)
        self.assertEqual(context['home']['group'],'Eastern')
        self.assertEqual(context['away']['group'],'Western')
        self.assertIsNone(make_context({'league_id':'130','home':'East 1',
                                        'away':'West unknown'},table))
        self.assertIsNone(espn_table(packet,'268','bra.1'))

    def test_direct_fotmob_fetch_prefers_primary_league_id(self):
        p={'details':{'id':268,'name':'Brasileirão'},
           'table':[{'data':{'table':{'all':table_rows('Brazil',20)}}}]}
        calls=[]
        def fake(url,timeout=7):
            calls.append(url)
            return p
        with patch('standings_context.fetch',side_effect=fake):
            table=fetch_table('268','Série A')
        self.assertEqual(table['source'],'FotMob')
        self.assertIn('id=268',calls[0])
        self.assertNotIn('id=1000001407',calls[0])

    def test_espn_backup_canonical_mapping(self):
        self.assertEqual(espn_league_code('268','Série A'),'bra.1')
        self.assertEqual(espn_league_code('130','Major League Soccer'),'usa.1')
        self.assertEqual(espn_league_code('230','Liga MX'),'mex.1')
        self.assertEqual(espn_league_code('274','Primera A'),'col.1')
        self.assertIsNone(espn_league_code('1000001407','Série A'))


if __name__=='__main__':
    unittest.main()
