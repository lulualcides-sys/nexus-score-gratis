import unittest
from datetime import datetime,timezone,timedelta
from research.goal_30_70_lab.run import (
    make_dataset,vector,split_day,bootstrap_gain
)

NOW=datetime(2026,11,9,12,tzinfo=timezone.utc)


def fixture(i,outcome="gol_confirmado",minute=35):
    return {"id":f"alert-{i}","match_id":f"game-{i}",
      "minute":minute,"league":"Brasileirão Série B",
      "captured_at":(NOW-timedelta(days=i//5)).isoformat(),
      "home":"Casa","away":"Fora","team":"home",
      "icon":"🔥","rule":"pressao_forte_10min",
      "pressure10":{"score":65},"pressure5":{"score":78},
      "score_at_alert":"0-0",
      "scout_delta":{"status":"observed_delta","changes":{
       "home":{"shots_on":2,"big_chances":1,"xg":.32}}},
      "outcomes":{"15":outcome}}


class LabResearchTests(unittest.TestCase):
    def test_features_scout_acceleration_and_ordered_holdout(self):
        items=[fixture(i, "gol_confirmado" if i%3==0 else "sem_gol_confirmado")
               for i in range(110)]
        entries,settled=make_dataset({"items":items},NOW)
        self.assertEqual(len(entries),110)
        self.assertEqual(len(settled),110)
        f=vector(settled[0])
        self.assertEqual(f["liga"],"Brasileirão Série B")
        self.assertEqual(f["aceleracao_pressao"],"subindo")
        self.assertEqual(f["novos_chutes_alvo"],"2+")
        self.assertEqual(f["variacao_xg"],"alta")
        self.assertEqual(f["placar_atual"],"0-0")
        train,test,cut=split_day(settled)
        self.assertLess(max(r["day"] for r in train),cut)
        self.assertGreaterEqual(min(r["day"] for r in test),cut)
        self.assertEqual(len(train)+len(test),110)

    def test_exclusions_censor_unknown_and_bootstrap_by_day(self):
        items=[fixture(i,"gol_confirmado" if i%2 else "sem_gol_confirmado")
               for i in range(60)]
        items.extend([fixture(60,"indeterminado"),fixture(61,"pendente")])
        entries,settled=make_dataset({"items":items},NOW)
        self.assertEqual(len(entries)-len(settled),2)
        p=[.48]*len(settled)
        z=bootstrap_gain(settled,[.5]*len(settled),p)
        self.assertLessEqual(z["brier_gain_ci95"][0],z["brier_gain_ci95"][1])


if __name__=="__main__":
    unittest.main()
