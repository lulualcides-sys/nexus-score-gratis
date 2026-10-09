import unittest
from fotmob_h2h import parse_h2h

class FotmobH2HTests(unittest.TestCase):
    def doc(self,old=None):
        old=old if old is not None else [
            {'home':{'id':123,'name':'Gimnasia LP'},'away':{'id':456,'name':'Atlético Tucumán'},
             'finished':True,'time':{'utcTime':'2025-04-06T18:00:00Z'},
             'status':{'finished':True,'scoreStr':'2 - 1'},
             'league':{'name':'Liga Profesional'}},
            {'home':{'id':456,'name':'Atlético Tucumán'},'away':{'id':123,'name':'Gimnasia LP'},
             'finished':True,'time':{'utcTime':'2024-02-08T18:00:00Z'},
             'status':{'finished':True,'scoreStr':'0 - 0'}}]
        return {'general':{'homeTeam':{'id':123},'awayTeam':{'id':456}},
                'content':{'h2h':{'matches':old}}}
    def fixture(self):
        return {'home_id':'123','away_id':'456','league':'arg.1','start_timestamp':1791500000}
    def test_parses_real_past_h2h_twice(self):
        out=parse_h2h(self.doc(),self.fixture())
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]['score'],'2-1')
        self.assertEqual(out[0]['source'],'FotMob')
    def test_disallows_future_unfinished_and_wrong_opponent(self):
        old=self.doc()['content']['h2h']['matches'][0]
        a={**old,'time':{'utcTime':'2027-01-01T16:00:00Z'}}
        b={**old,'finished':False,'status':{'finished':False,'scoreStr':'1-0'}}
        c={**old,'away':{'id':999,'name':'Outro'}}
        self.assertEqual(parse_h2h(self.doc([a,b,c]),self.fixture()),[])
    def test_match_identity_must_match_fixture(self):
        fixture={**self.fixture(),'away_id':'666'}
        self.assertEqual(parse_h2h(self.doc(),fixture),[])
    def test_no_score_does_not_count(self):
        a=self.doc()['content']['h2h']['matches'][0]
        a={**a,'status':{'finished':True},'home':{'id':123,'name':'Gimnasia LP'},
           'away':{'id':456,'name':'Atlético Tucumán'}}
        self.assertEqual(parse_h2h(self.doc([a]),self.fixture()),[])
if __name__=='__main__':unittest.main()
