import unittest
from coletar import confirmed_halftime
from web_export import public_row


class HalftimeSourceTests(unittest.TestCase):
    def test_fotmob_half_time_is_explicit(self):
        self.assertTrue(confirmed_halftime({'started':True,'liveTime':{'short':'HT'}},True))
        self.assertTrue(confirmed_halftime({'started':True,'reason':{'short':'Half Time'}},True))
        self.assertTrue(confirmed_halftime({'started':True,'reason':{'short':'Half-time'}},True))
        self.assertFalse(confirmed_halftime({'started':True,'liveTime':{'short':"45'"}},True))
        self.assertFalse(confirmed_halftime({'started':True,'liveTime':{'short':"45+4'"}},True))
        self.assertFalse(confirmed_halftime({'started':True,'liveTime':{'short':"48'"}},True))
        self.assertFalse(confirmed_halftime({'started':False,'liveTime':{'short':'HT'}},False))

    def test_espn_half_time_is_explicit(self):
        self.assertTrue(confirmed_halftime(
            {'type':{'name':'STATUS_HALFTIME','state':'in'},'displayClock':'45:00'},True))
        self.assertTrue(confirmed_halftime(
            {'type':{'description':'Halftime','state':'in'}},True))
        self.assertFalse(confirmed_halftime(
            {'type':{'name':'STATUS_IN_PROGRESS'},'displayClock':'45:00'},True))
        self.assertFalse(confirmed_halftime(
            {'type':{'description':'Final'},'displayClock':'90:00'},False))

    def test_export_only_live_confirmed_half_time(self):
        fx={'id':'fotmob-234','home':'A','away':'B','league':'Liga',
            'phase':'live','halftime':True,'status_short':'HT','minute':45,
            'score':'0-0','start_timestamp':1792000000}
        doc=public_row({'fixture':fx},'2026-10-17')
        self.assertTrue(doc['halftime'])
        self.assertEqual(doc['status_short'],'HT')
        concluded=public_row({'fixture':{**fx,'phase':'finished'}},'2026-10-17')
        self.assertFalse(concluded['halftime'])
        self.assertEqual(concluded['status_short'],'')
        unconfirmed=public_row({'fixture':{**fx,'halftime':False}},'2026-10-17')
        self.assertFalse(unconfirmed['halftime'])


if __name__=='__main__':
    unittest.main()
