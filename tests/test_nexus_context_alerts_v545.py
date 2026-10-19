import unittest
from datetime import datetime,timedelta,timezone
from odds_movements import movements
NOW=datetime(2026,10,19,16,tzinfo=timezone.utc)
K=int((NOW+timedelta(hours=1)).timestamp())
def q(book,sel,odd,minutes=0,src='OddsPapi'):
 return {'market':'1x2','selection':sel,'bookmaker':book,'source':src,'odds':odd,
         'captured_at':(NOW+timedelta(minutes=minutes)).isoformat()}
class ContextAlertTests(unittest.TestCase):
 def test_only_same_book_and_selection(self):
  found=movements([q('Betano','home',2,minutes=-12),
                   q('Pinnacle','home',5,minutes=-10),
                   q('Betano','home',2.2,minutes=-2)],K,NOW.timestamp())
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['bookmaker'],'Betano')
  self.assertAlmostEqual(found[0]['change_pct'],10)
 def test_no_alert_from_one_quote_or_historical(self):
  self.assertEqual(movements([q('Betano','home',2)],K,NOW.timestamp()),[])
  self.assertEqual(movements([q('Betano','home',2,-12),
                             q('Betano','home',2.5,-2)],K,NOW.timestamp()+7200),[])
 def test_different_selection_never_mixed(self):
  self.assertEqual(movements([q('Betano','home',2,-12),
                             q('Betano','draw',3,-2)],K,NOW.timestamp()),[])
if __name__=='__main__':unittest.main()
