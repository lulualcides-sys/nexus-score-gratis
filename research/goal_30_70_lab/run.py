#!/usr/bin/env python3
"""Auditable, out-of-time NEXUS goal 30–70 research. Never promotes models."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from random import Random

from goal_window_30_70 import _eligible, _fit, _estimate, features


def make_dataset(journal, now):
    entries=_eligible(journal,now)
    settled=[r for r in entries if r["outcomes"]["15"] in
             ("gol_confirmado","sem_gol_confirmado")]
    return entries, sorted(settled,key=lambda r:(r["day"],r["match_id"]))


def vector(r, interval=None):
    x=features(r)
    x["liga"]=str(r.get("league") or "indisponivel")[:60]
    if interval is not None:
        x["intervalo"]="%02d-%02d"%(interval*5+1,interval*5+5)
    return x


def label(row):
    return int(row["outcomes"]["15"]=="gol_confirmado")


def split_day(rows):
    days=sorted({r["day"] for r in rows})
    if len(days)<10:
        return [],[],None
    day=days[max(1,int(len(days)*.70))]
    return ([r for r in rows if r["day"]<day],
            [r for r in rows if r["day"]>=day],day)


def calculate(y, p):
    from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
    if len(y)!=len(p) or not y:
        return None
    safe=[min(.999999,max(.000001,float(z))) for z in p]
    bins=[{"n":0,"pred":0.0,"hit":0} for _ in range(5)]
    for target,guess in zip(y,safe):
        b=bins[min(4,int(guess*5))]
        b["n"]+=1;b["pred"]+=guess;b["hit"]+=int(target)
    return {"n":len(y),"goals":sum(y),
            "brier":round(float(brier_score_loss(y,safe)),6),
            "auc":round(float(roc_auc_score(y,safe)),5) if len(set(y))==2 else None,
            "log_loss":round(float(log_loss(y,safe,labels=[0,1])),6),
            "ece":round(sum(abs(x["pred"]-x["hit"]) for x in bins)/len(y),5),
            "bins":[{"n":b["n"],"predicted_pct":round(100*b["pred"]/b["n"],1) if b["n"] else None,
                     "observed_pct":round(100*b["hit"]/b["n"],1) if b["n"] else None}
                    for b in bins]}


def bootstrap_gain(rows, baseline, candidate):
    if not rows:return None
    buckets=defaultdict(list)
    for row,base,p in zip(rows,baseline,candidate):
        y=label(row)
        buckets[row["day"]].append((base-y)**2-(p-y)**2)
    days=sorted(buckets)
    rng=Random(3070)
    vals=[]
    for _ in range(600):
        chosen=[days[rng.randrange(len(days))] for _ in days]
        samples=[v for day in chosen for v in buckets[day]]
        vals.append(sum(samples)/len(samples))
    vals.sort()
    return {"holdout_days":len(days),"brier_gain_ci95":[round(vals[14],6),round(vals[584],6)],
            "method":"600 blocked day bootstrap replicates; exploratory"}


def fit_logit(train):
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    model=Pipeline([("encode",DictVectorizer(sparse=True)),
                    ("clf",LogisticRegression(C=.45,max_iter=300,solver="liblinear",
                                              random_state=3070))])
    model.fit([vector(r) for r in train],[label(r) for r in train])
    return model


def fit_catboost(train):
    from catboost import CatBoostClassifier
    cols=sorted(vector(train[0]))
    X=[[str(vector(r).get(k,"indisponivel")) for k in cols] for r in train]
    model=CatBoostClassifier(iterations=160,depth=4,learning_rate=.04,
       l2_leaf_reg=12,loss_function="Logloss",random_seed=3070,
       thread_count=2,verbose=False,allow_writing_files=False)
    model.fit(X,[label(r) for r in train],cat_features=list(range(len(cols))))
    return model,cols


def hazard_rows(rows):
    """Discrete 5-min hazard: exclude any positive without timed goal."""
    X=[];Y=[];skipped=0
    for r in rows:
        y=label(r)
        delay=r.get("first_goal_delay")
        if y and not (isinstance(delay,int) and 1<=delay<=15):
            skipped+=1
            continue
        for bucket in range(3):
            if y and delay<=bucket*5:
                break
            X.append(vector(r,bucket))
            Y.append(int(bool(y and bucket*5 < delay <= (bucket+1)*5)))
            if Y[-1]:
                break
    return X,Y,skipped


def fit_hazard(train):
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    X,Y,skipped=hazard_rows(train)
    if len(X)<80 or len(set(Y))<2:return None,{"risk_rows":len(X),"untimed_positive_skipped":skipped}
    model=Pipeline([("encode",DictVectorizer(sparse=True)),
                    ("clf",LogisticRegression(C=.35,max_iter=300,solver="liblinear",
                                              random_state=3070))])
    model.fit(X,Y)
    return model,{"risk_rows":len(X),"untimed_positive_skipped":skipped}


def predict_hazard(model,rows):
    X=[vector(r,k) for r in rows for k in range(3)]
    hazards=model.predict_proba(X)[:,1].tolist()
    return [1-math.prod(1-h for h in hazards[i*3:i*3+3]) for i in range(len(rows))]


def rolling_days(rows):
    days=sorted({r["day"] for r in rows})
    if len(days)<15:return []
    output=[]
    for cutoff,finish in ((.5,.65),(.65,.8),(.8,1)):
        first=days[int(len(days)*cutoff)]
        stop=days[min(len(days)-1,int(len(days)*finish))] if finish<1 else None
        tr=[r for r in rows if r["day"]<first]
        te=[r for r in rows if r["day"]>=first and (stop is None or r["day"]<stop)]
        if len(tr)<100 or len(te)<20 or len(set(label(r) for r in tr))<2:continue
        prior=_fit(tr);baseline=prior["base_rate"]
        logit=fit_logit(tr)
        y=[label(r) for r in te]
        models={
            "constant":calculate(y,[baseline]*len(te)),
            "nexus":calculate(y,[_estimate(prior,r)[0] for r in te]),
            "logistic":calculate(y,logit.predict_proba([vector(r) for r in te])[:,1].tolist())
        }
        output.append({"start":first,"stop":stop,"train":len(tr),"test":len(te),
                       "metrics":models})
    return output


def duckdb_audit(all_rows, settled):
    import duckdb
    con=duckdb.connect(":memory:")
    con.execute("CREATE TABLE alerts (match_id VARCHAR, league VARCHAR, day VARCHAR, minute INTEGER, settled BOOLEAN, goal BOOLEAN)")
    settled_ids={r["match_id"] for r in settled}
    con.executemany("INSERT INTO alerts VALUES (?,?,?,?,?,?)",[
        (r["match_id"],str(r.get("league") or "unknown")[:80],r["day"],int(r["minute"]),
         r["match_id"] in settled_ids,
         r["outcomes"]["15"]=="gol_confirmado")
        for r in all_rows
    ])
    dup=con.execute("SELECT COUNT(*)-COUNT(DISTINCT match_id) FROM alerts").fetchone()[0]
    groups=con.execute("""SELECT league,COUNT(*) AS total,
       SUM(CASE WHEN settled THEN 1 ELSE 0 END) AS verified,
       SUM(CASE WHEN settled AND goal THEN 1 ELSE 0 END) AS hits
       FROM alerts GROUP BY league ORDER BY verified DESC,league LIMIT 25""").fetchall()
    con.close()
    return {"observations":len(all_rows),"duplicates_after_first_match_filter":dup,
            "excluded_unknown_or_unresolved":len(all_rows)-len(settled),
            "leagues":[{"league":x[0],"all":x[1],"settled":x[2],"hits":x[3]} for x in groups]}


def run(journal, now=None):
    now=now or datetime.now(timezone.utc)
    all_rows,settled=make_dataset(journal,now)
    train,test,split=split_day(settled)
    result={"schema":1,"status":"sample_insufficient","generated_at":now.isoformat(),
      "target":"any confirmed goal in 15min after first signal during minute 30..70",
      "no_model_promotion":True,"no_live_signals":True,
      "evidence":"only chronological previously observed and settled labels",
      "data_quality":duckdb_audit(all_rows,settled),
      "sample":{"total":len(all_rows),"verified":len(settled),
                "development":len(train),"holdout":len(test),
                "holdout_start":split,"holdout_days":len({r["day"] for r in test})},
      "models":{},"walk_forward":[],
      "limitations":[
        "All model settings predetermined; historical holdout is not prospective validation.",
        "Historical signals are a selected subset of matches, not league base rates.",
        "Missing minute-level events/pressure are not reconstructed.",
        "Unverified market entry prices and liquidity prohibit ROI/EV claims."]}
    if len(train)<100 or len(test)<40 or len({label(r) for r in train})<2:
        return result
    y=[label(r) for r in test]
    prior=_fit(train)
    baseline=[prior["base_rate"]]*len(test)
    predictions={"constant_baseline":baseline,
                 "nexus_existing":[_estimate(prior,r)[0] for r in test],
                 "logistic_regularized":fit_logit(train).predict_proba(
                    [vector(r) for r in test])[:,1].tolist()}
    model,cols=fit_catboost(train)
    predictions["catboost_shallow"]=model.predict_proba(
        [[str(vector(r).get(k,"indisponivel")) for k in cols] for r in test])[:,1].tolist()
    h,diagnostic=fit_hazard(train)
    if h:
        predictions["discrete_time_hazard_5m"]=predict_hazard(h,test)
    result["hazard_data_quality"]=diagnostic
    for name,pred in predictions.items():
        result["models"][name]={
            "metrics":calculate(y,pred),
            "gain_vs_constant_day_bootstrap":bootstrap_gain(test,baseline,pred)
        }
    result["walk_forward"]=rolling_days(settled)
    result["status"]="research_evaluated_not_approved"
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--journal",default="history/signal_registry.json")
    p.add_argument("--output",default="artifacts/goal3070-lab-report.json")
    args=p.parse_args()
    journal=json.loads(Path(args.journal).read_text(encoding="utf-8"))
    if not isinstance(journal,dict) or not isinstance(journal.get("items"),list):
        raise ValueError("journal invalid or incomplete")
    result=run(journal)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"sample":result["sample"],
      "scores":{k:v["metrics"] for k,v in result["models"].items()},
      "artifact":str(out)},ensure_ascii=False))


if __name__=="__main__":main()
