#!/usr/bin/env python3
"""Arquivo de pesquisa xG histórica do SoccerData/Understat.

Leitura de UMA temporada finalizada, UMA liga, sem sobrescrever odds ou
placares do NEXUS. Não publica raw xG na pasta web pública.
"""
import json
import math
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"history"/"soccerdata_understat_2025_26.json"
STATUS=ROOT/"history"/"soccerdata_xg_status.json"

def finite(value):
    try:
        if value is None:return None
        n=float(value)
        return round(n,4) if math.isfinite(n) and 0<=n<=20 else None
    except (ValueError,TypeError,OverflowError):return None

def score_int(value):
    try:
        if value is None:return None
        n=float(value)
        return int(n) if math.isfinite(n) and n.is_integer() and 0<=n<=40 else None
    except (ValueError,TypeError,OverflowError):return None

def date_value(value):
    try:
        d=value.date() if hasattr(value,"date") else datetime.fromisoformat(str(value).replace("Z","+00:00")).date()
        text=d.isoformat()
        return text if "2025-07-01"<=text<="2026-06-30" else None
    except (ValueError,TypeError,OverflowError):return None

def normalized(records):
    results={}
    for row in records:
        if not isinstance(row,dict):continue
        ident=str(row.get("game_id") or "")
        date=date_value(row.get("date"))
        home=str(row.get("home_team") or "").strip()
        away=str(row.get("away_team") or "").strip()
        xh=finite(row.get("home_xg")); xa=finite(row.get("away_xg"))
        gh=score_int(row.get("home_goals")); ga=score_int(row.get("away_goals"))
        if (not ident.isdigit() or len(ident)>16 or not date or
            not home or not away or home==away or len(home)>100 or len(away)>100 or
            any(v is None for v in (xh,xa,gh,ga)) or
            row.get("is_result") is not True):continue
        item={"source_match_id":ident,"date":date,"home":home,"away":away,
              "home_goals":gh,"away_goals":ga,"home_xg":xh,"away_xg":xa}
        if ident in results and results[ident]!=item:
            raise ValueError("IDs de jogos do Understat conflitantes; arquivo rejeitado")
        results[ident]=item
    return sorted(results.values(),key=lambda x:(x["date"],x["source_match_id"]))

def run():
    import soccerdata as sd
    scraped=sd.Understat(leagues="ENG-Premier League",seasons="2025/2026",no_store=True).read_schedule()
    rows=normalized(scraped.reset_index().to_dict(orient="records"))
    if len(rows)<280:
        raise RuntimeError("Cobertura da temporada inferior a 280 confrontos, recusando publicacao")
    now=datetime.now(timezone.utc).isoformat()
    archive={"schema":1,"source":"soccerdata Understat",
             "source_package":"soccerdata 1.9.1","competition":"ENG-Premier League",
             "season":"2025/2026","kind":"historical_final_xg",
             "collected_at":now,"games":rows,
             "caution":"xG historico final; nao eh xG ao vivo, odd ou EV+. Sem validacao de licenca de redistribuicao."}
    status={"updated_at":now,"source":"soccerdata Understat","season":"2025/2026",
            "league":"ENG-Premier League","matches_verified":len(rows),
            "games_with_home_away_xg":len(rows),
            "ready_for_research":True,"integrated_into_live_ev":False,
            "note":"Uso de pesquisa interna; não combina automaticamente com odds ou alertas."}
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(archive,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False))
if __name__=="__main__":run()
