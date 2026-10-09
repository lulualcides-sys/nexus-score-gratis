import unittest
from web_export import paper_summary


class PaperPlBreakdownTests(unittest.TestCase):
    def test_settled_only_and_profit_loss_separate(self):
        rows=[{'signals':[
            {'market':'1x2','status':'settled','paper_pl_u':1.8},
            {'market':'1x2','status':'settled','paper_pl_u':-1.0},
            {'market':'over25','status':'settled','paper_pl_u':2.1},
            {'market':'over25','status':'settled','paper_pl_u':-1.0},
            {'market':'over25','status':'pending','paper_pl_u':None},
        ]}]
        data=paper_summary(rows)
        self.assertEqual(data['settled'],4)
        self.assertEqual(data['pending'],1)
        self.assertEqual(data['won'],2)
        self.assertEqual(data['lost'],2)
        self.assertAlmostEqual(data['profit_u'],3.9)
        self.assertAlmostEqual(data['loss_u'],2)
        self.assertAlmostEqual(data['paper_pl_u'],1.9)
        self.assertAlmostEqual(data['roi_pct'],47.5)
        self.assertEqual(len(data['markets']),2)
        match=next(x for x in data['markets'] if x['market']=='1x2')
        self.assertEqual(match['wins'],1)
        self.assertEqual(match['losses'],1)
        self.assertAlmostEqual(match['profit_u'],1.8)
        self.assertAlmostEqual(match['loss_u'],1.0)
        self.assertAlmostEqual(match['paper_pl_u'],.8)

    def test_no_settlement_yields_unknown_not_fake_zero(self):
        data=paper_summary([{'signals':[{'market':'1x2','status':'pending','paper_pl_u':None}]}])
        self.assertEqual(data['settled'],0)
        for key in ('paper_pl_u','profit_u','loss_u','roi_pct'):
            self.assertIsNone(data[key])

    def test_only_settled_numeric_entries(self):
        rows=[{'signals':[
           {'market':'1x2','status':'settled','paper_pl_u':None},
           {'market':'1x2','status':'pending','paper_pl_u':100},
           {'market':'1x2','status':'settled','paper_pl_u':-1},
        ]}]
        data=paper_summary(rows)
        self.assertEqual(data['settled'],1)
        self.assertEqual(data['paper_pl_u'],-1)
        self.assertEqual(data['profit_u'],0)
        self.assertEqual(data['loss_u'],1)


if __name__=='__main__':
    unittest.main()
