#!/usr/bin/env python3
"""Teste isolado do soccerdata no NEXUS; NAO grava nos dados de producao."""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2]
def normalise(text):
    s=unicodedata.normalize("NFKD",str(text or "").casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+",s))
def current_teams(base=ROOT/"history",limit_days=3):
    files=sorted(Path(base).glob("20??-??-??.json"),reverse=True)[:limit_days]
    teams=set()
    for f in files:
        try:d=json.loads(f.read_text(encoding="utf-8"))
        except (OSError,ValueError):continue
        for row in (d.get("matches") or {}).values():
            if not isinstance(row,dict):continue
            fix=row.get("fixture") or {}
            for key in ("home","away"):
                name=normalise(fix.get(key))
                if name:teams.add(name)
    return teams

def evaluate(elo_records,team_names):
    """Só comparações EXATAS normalizadas: evita associar times homônimos."""
    name_count={}
    valid=[]
    for record in elo_records:
        if not isinstance(record,dict):continue
        name=normalise(record.get("team"))
        try:elo=float(record.get("elo"))
        except (TypeError,ValueError):continue
        if not name or not math.isfinite(elo) or elo<300 or elo>3500:continue
        name_count[name]=name_count.get(name,0)+1
        valid.append((name,elo))
    unique={name:elo for name,elo in valid if name_count[name]==1}
    matched={name:round(unique[name],2) for name in sorted(team_names) if name in unique}
    return {"source_rows_valid":len(valid),
            "source_names_unique":len(unique),
            "nexus_teams":len(team_names),
            "matched_teams":len(matched),
            "match_rate_pct":round(100*len(matched)/len(team_names),2) if team_names else 0,
            "examples":dict(list(matched.items())[:8]),
            "matched_only_exact":True}

def evaluate_understat(rows):
    """Cobertura historica de xG, sem somar linhas sem valores reais."""
    checked=0
    for row in rows:
        if not isinstance(row,dict):continue
        try:
            h=float(row.get("home_xg"));a=float(row.get("away_xg"))
        except (ValueError,TypeError):continue
        if math.isfinite(h) and math.isfinite(a) and 0<=h<=20 and 0<=a<=20:
            checked+=1
    return {"rows":len(rows),"with_both_verified_xg":checked,
            "note":"Dados HISTÓRICOS de 2025/26, não xG ao vivo nem odds da entrada."}

def run_live(today,source_name):
    import soccerdata as sd
    if source_name=="clubelo":
        source=sd.ClubElo(no_store=True)
        df=source.read_by_date(today)
        frame=df.reset_index()
        if "team" not in frame.columns and frame.columns.size:
            frame=frame.rename(columns={frame.columns[0]:"team"})
        return evaluate(frame[["team","elo"]].to_dict(orient="records"),current_teams())
    if source_name=="understat":
        source=sd.Understat(leagues="ENG-Premier League",seasons="2025/2026",no_store=True)
        frame=source.read_schedule().reset_index()
        return evaluate_understat(frame.to_dict(orient="records"))
    raise ValueError("Fonte nao reconhecida")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="soccerdata-probe.json")
    ap.add_argument("--source",choices=["clubelo","understat"],default="clubelo")
    ap.add_argument("--live",action="store_true")
    args=ap.parse_args()
    status={"schema":1,"checked_at":datetime.now(timezone.utc).isoformat(),
            "package":"soccerdata==1.9.1","source":args.source,
            "status":"not_run","nexus_history_modified":False,
            "note":"Elo nao representa odd/EV+; sem associacao aproximada de clubes."}
    if args.live:
        try:
            status.update(run_live(datetime.now(timezone.utc).date().isoformat(),args.source))
            rows=status.get("source_rows_valid",status.get("with_both_verified_xg",0))
            status["status"]="ok" if rows>0 else "empty"
        except Exception as err:
            status["status"]="unavailable"
            status["error_type"]=type(err).__name__
            status["error"]=str(err)[:240]
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False))
    # A fonte pode estar bloqueada. Registrar falha ao inves de sobrescrever dados.
    return 0 if status["status"] in ("ok","empty","unavailable","not_run") else 1
if __name__=="__main__":sys.exit(main())
