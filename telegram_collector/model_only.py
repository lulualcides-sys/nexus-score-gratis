#!/usr/bin/env python3
"""NEXUS MODELO PRÓPRIO: odds teóricas de futebol 100% calculadas, sem odds externas.

Entrada: somente placares finalizados do histórico NEXUS e openfootball CC0,
e calendário PRIORITÁRIO (jogos futuros); não lê nem utiliza preços de casas.
FT, HT e HT/FT vêm de uma ÚNICA distribuição conjunta de gols no 1º e 2º
tempo; todos os mercados permanecem matematicamente coerentes.

Não há promessa de calibração, lucro, EV+, odds negociáveis ou liquidez.
Exclui handicaps, cartões, escanteios e mercados de jogadores.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")
MODEL_VERSION = "nexus-poisson-segmented-1.0"
HALF_LIFE_DAYS = 120.0
SHRINK_GAMES = 6.0
MIN_LEAGUE_MATCHES = 28
MIN_TEAM_EFFECTIVE = 2.5
MAX_TRAIN_DAYS = 420
MAX_FUTURE_HOURS = 72
MAX_GOALS_PER_HALF = 10
TOTAL_LINES_FT = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)
TOTAL_LINES_HT = (0.5, 1.5, 2.5)
TEAM_LINES_FT = (0.5, 1.5, 2.5)
CC0_LEAGUES = {
    "de.1": "ger.1", "en.1": "eng.1", "es.1": "esp.1",
    "fr.1": "fra.1", "it.1": "ita.1",
}
MAX_JSON_BYTES = 16_000_000


def normalized_team(name):
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", s)
    skip = {"fc", "cf", "ac", "sc", "afc", "football", "club", "clube", "de", "the"}
    normalized = " ".join(w for w in words if w not in skip)
    # Exact club-name aliases only: no risky fuzzy matching across clubs.
    aliases = {
        "ca osasuna": "osasuna", "osasuna": "osasuna",
        "olympique lyonnais": "lyon", "olympique lyon": "lyon",
        "lyon": "lyon",
        "paris sg": "paris saint germain",
        "paris saint germain": "paris saint germain",
        "sevilla": "sevilla",
    }
    return aliases.get(normalized, normalized)


def canonical_league(code):
    return bool(re.fullmatch(
        r"(?:[a-z]{2,12}\.[1-9]|(?:uefa|conmebol|caf|afc|concacaf)\.[a-z0-9_]+)",
        str(code or ""),
    ))


def utc_date(ts):
    return datetime.fromtimestamp(float(ts), timezone.utc).date()


def integer_goals(x):
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, str) and not re.fullmatch(r"\d{1,2}", x.strip()):
        return None
    try:
        value = int(x)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if 0 <= value <= 15 and str(value) == str(x).strip() else None


def scoreline(value):
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"\s*(\d{1,2})\s*[-:]\s*(\d{1,2})\s*", value)
    if not m:
        return None
    h, a = integer_goals(m.group(1)), integer_goals(m.group(2))
    return (h, a) if h is not None and a is not None else None


def historical_rows(history, as_of):
    """Dedup by league, teams and UTC fixture date; never train on a future game."""
    cutoff = as_of.date()
    records = {}
    base = Path(history)
    for file in sorted(base.glob("20??-??-??.json")):
        if file.stat().st_size > MAX_JSON_BYTES:
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        games = data.get("matches") if isinstance(data, dict) else None
        if not isinstance(games, dict):
            continue
        for item in games.values():
            fixture = item.get("fixture") if isinstance(item, dict) else None
            if not isinstance(fixture, dict) or fixture.get("phase") != "finished":
                continue
            pair = scoreline(fixture.get("score"))
            if pair is None:
                continue
            try:
                ts = int(fixture.get("start_timestamp") or 0)
                date = utc_date(ts)
            except (ValueError, TypeError, OverflowError):
                continue
            if not 0 < (cutoff-date).days <= MAX_TRAIN_DAYS:
                continue
            league = str(fixture.get("league_code") or fixture.get("league") or "")
            h, a = normalized_team(fixture.get("home")), normalized_team(fixture.get("away"))
            if not canonical_league(league) or not h or not a or h == a:
                continue
            key = (league, h, a, date.isoformat())
            records[key] = {"league":league, "home":h, "away":a,
                            "date":date, "ft":pair, "ht":None, "source":"NEXUS finished results"}
    cache = base / "openfootball_cc0_cache.json"
    if cache.is_file() and cache.stat().st_size <= MAX_JSON_BYTES:
        try:
            doc = json.loads(cache.read_text(encoding="utf-8"))
            entries = doc.get("entries") if isinstance(doc, dict) else {}
            if not isinstance(entries, dict):
                entries = {}
            for path, entry in entries.items():
                league = CC0_LEAGUES.get(str(path).split("/")[-1].removesuffix(".json"))
                if not league or not isinstance(entry, dict):
                    continue
                for game in entry.get("matches") or []:
                    if not isinstance(game, dict):
                        continue
                    # A simple [0,0] fixture placeholder must NEVER be treated
                    # as a finished match: require explicit object score.ft.
                    score = game.get("score")
                    if not isinstance(score, dict):
                        continue
                    full = score.get("ft")
                    half = score.get("ht")
                    if not isinstance(full, list) or len(full) != 2:
                        continue
                    f0, f1 = integer_goals(full[0]), integer_goals(full[1])
                    if f0 is None or f1 is None:
                        continue
                    try:
                        date = datetime.strptime(game["date"], "%Y-%m-%d").date()
                    except (KeyError, ValueError, TypeError):
                        continue
                    if not 0 < (cutoff-date).days <= MAX_TRAIN_DAYS:
                        continue
                    h, a = normalized_team(game.get("team1")), normalized_team(game.get("team2"))
                    if not h or not a or h == a:
                        continue
                    ht = None
                    if isinstance(half, list) and len(half) == 2:
                        h0, h1 = integer_goals(half[0]), integer_goals(half[1])
                        if h0 is not None and h1 is not None and h0<=f0 and h1<=f1:
                            ht = (h0, h1)
                    key = (league, h, a, date.isoformat())
                    previous = records.get(key)
                    if previous:
                        if previous["ft"] == (f0, f1) and previous["ht"] is None:
                            previous["ht"] = ht
                        # conflicting sources are never merged or used as
                        # confirmation of a deliberately changed final score.
                        continue
                    records[key] = {"league":league, "home":h, "away":a,
                                    "date":date, "ft":(f0,f1), "ht":ht,
                                    "source":"openfootball CC0"}
        except (ValueError, OSError):
            pass
    return list(records.values())


def team_rates(matches, fixture, as_of):
    """Weighted team attack/defence on venue-adjusted historical goal rates."""
    date = utc_date(fixture["kickoff_unix"])
    league = fixture["league_code"]
    games = [m for m in matches if m["league"] == league and m["date"] < date]
    if len(games) < MIN_LEAGUE_MATCHES:
        return None, "insufficient_league_results"
    weighted=[]
    for m in games:
        days=(date-m["date"]).days
        weight=0.5**(days/HALF_LIFE_DAYS)
        weighted.append((m,weight))
    total_w=sum(w for _,w in weighted)
    if total_w < MIN_LEAGUE_MATCHES*0.50:
        return None, "outdated_league_history"
    home_avg=sum(m["ft"][0]*w for m,w in weighted)/total_w
    away_avg=sum(m["ft"][1]*w for m,w in weighted)/total_w
    home_avg=max(0.45,min(3.25,home_avg))
    away_avg=max(0.40,min(3.00,away_avg))
    home=normalized_team(fixture["home"])
    away=normalized_team(fixture["away"])
    games_by_team=defaultdict(list)
    for m,w in weighted:
        games_by_team[m["home"]].append((m,w,"home"))
        games_by_team[m["away"]].append((m,w,"away"))
    def strengths(team):
        relevant=games_by_team.get(team,[])
        effective=sum(w for _,w,_ in relevant)
        if effective < MIN_TEAM_EFFECTIVE:
            return None
        attack=0.0
        weakness=0.0
        for m,w,side in relevant:
            if side=="home":
                attack+=w*m["ft"][0]/home_avg
                weakness+=w*m["ft"][1]/away_avg
            else:
                attack+=w*m["ft"][1]/away_avg
                weakness+=w*m["ft"][0]/home_avg
        atk=(attack+SHRINK_GAMES)/(effective+SHRINK_GAMES)
        defence=(weakness+SHRINK_GAMES)/(effective+SHRINK_GAMES)
        return atk,defence,effective,len(relevant)
    h,a = strengths(home),strengths(away)
    if h is None or a is None:
        return None,"insufficient_team_results"
    # HT fraction fitted using only matches that happened before kickoff.
    ht_games=[(m,w) for m,w in weighted if m["ht"] is not None]
    global_ht=[m for m in matches if m["ht"] is not None and m["date"] < date]
    if len(ht_games)>=18:
        first=sum((m["ht"][0]+m["ht"][1])*w for m,w in ht_games)
        full=sum((m["ft"][0]+m["ft"][1])*w for m,w in ht_games)
        ratio=first/full if full>0 else None
        split_source="league_observed_halftimes"
        halftime_n=len(ht_games)
    elif len(global_ht)>=60:
        first=sum(m["ht"][0]+m["ht"][1] for m in global_ht)
        full=sum(m["ft"][0]+m["ft"][1] for m in global_ht)
        ratio=first/full if full>0 else None
        split_source="cross_league_halftime_prior"
        halftime_n=len(global_ht)
    else:
        return None, "insufficient_halftime_results"
    if ratio is None or not 0.35<=ratio<=0.60:
        return None, "halftime_ratio_unreliable"
    # Goal rates are shrinkage-stabilised and bounded to avoid extreme implied odds.
    l_home = max(0.35,min(3.40,home_avg*h[0]*a[1]))
    l_away = max(0.35,min(3.40,away_avg*a[0]*h[1]))
    quality=("limited" if len(games)<65 or min(h[2],a[2])<6
             or split_source!="league_observed_halftimes" else "moderate_unvalidated")
    return {
        "lambda_home_ft": l_home, "lambda_away_ft":l_away,
        "first_half_share":ratio,
        "half_time_calibration_source":split_source,
        "ht_training_matches":halftime_n,
        "league_training_games":len(games),
        "league_effective_games":round(total_w,2),
        "home_team_games":h[3],"away_team_games":a[3],
        "home_team_effective_games":round(h[2],2),
        "away_team_effective_games":round(a[2],2),
        "history_quality":quality,
        "league_home_goal_rate":round(home_avg,3),
        "league_away_goal_rate":round(away_avg,3),
    }, None


def pois_vector(mean, top=MAX_GOALS_PER_HALF):
    out=[math.exp(-mean)]
    for k in range(1,top+1):
        out.append(out[-1]*mean/k)
    mass=sum(out)
    if mass<=0:
        raise ValueError("Poisson vector has no probability")
    return [v/mass for v in out]


def result(x,y):
    return "1" if x>y else ("X" if x==y else "2")


def make_probability_book(lh, la, first_half_share):
    """Sum ONE 4D HT+second-half goal distribution for ALL outcome markets."""
    if not all(math.isfinite(v) for v in (lh,la,first_half_share)):
        raise ValueError("Nonfinite expected goals")
    if not (0.30<=lh<=3.5 and 0.30<=la<=3.5 and 0.35<=first_half_share<=0.60):
        raise ValueError("Expected goal input outside validated range")
    ph=pois_vector(lh*first_half_share)
    pa=pois_vector(la*first_half_share)
    sh=pois_vector(lh*(1-first_half_share))
    sa=pois_vector(la*(1-first_half_share))
    ft=defaultdict(float);ht=defaultdict(float);htft=defaultdict(float)
    goals_ft=defaultdict(float);goals_ht=defaultdict(float)
    team_home=defaultdict(float);team_away=defaultdict(float)
    btts_ft=btts_ht=0.0
    scores=defaultdict(float)
    for x,p_x in enumerate(ph):
        for y,p_y in enumerate(pa):
            p_first=p_x*p_y
            halftime=result(x,y)
            ht[halftime]+=p_first
            goals_ht[x+y]+=p_first
            if x and y:
                btts_ht+=p_first
            for z,p_z in enumerate(sh):
                for w,p_w in enumerate(sa):
                    p=p_first*p_z*p_w
                    h,a=x+z,y+w
                    full=result(h,a)
                    ft[full]+=p
                    htft[halftime+"/"+full]+=p
                    goals_ft[h+a]+=p
                    team_home[h]+=p
                    team_away[a]+=p
                    scores[(h,a)]+=p
                    if h and a:
                        btts_ft+=p
    # All derived from the same finite, explicitly normalised joint distribution.
    def pair(p_yes):
        return {"Sim":p_yes,"Não":1-p_yes}
    def totals(distribution,lines):
        return {str(line):{"Under":sum(p for goals,p in distribution.items() if goals < line),
                           "Over":sum(p for goals,p in distribution.items() if goals > line)}
                for line in lines}
    market={
        "ft_1x2":dict(ft),
        "ht_1x2":dict(ht),
        "ht_ft":dict(htft),
        "double_chance_ft":{"1X":ft["1"]+ft["X"],"X2":ft["X"]+ft["2"],"12":ft["1"]+ft["2"]},
        "btts_ft":pair(btts_ft),
        "btts_ht":pair(btts_ht),
        "ft_total_goals":totals(goals_ft,TOTAL_LINES_FT),
        "ht_total_goals":totals(goals_ht,TOTAL_LINES_HT),
        "home_team_goals_ft":totals(team_home,TEAM_LINES_FT),
        "away_team_goals_ft":totals(team_away,TEAM_LINES_FT),
        "correct_score_ft":{f"{h}-{a}":p for (h,a),p in sorted(
            scores.items(),key=lambda entry:-entry[1])[:8]},
    }
    def odds(p):
        if not 0 < p < 1:
            return None
        return {"probability":round(p,6),"percent":round(100*p,2),
                "fair_odds":round(1/p,3)}
    def recurse(item):
        return {key:recurse(value) if isinstance(value,dict) else odds(value)
                for key,value in item.items()}
    return recurse(market)


def future_fixtures(archive,now):
    coverage=Path(archive)/"priority-coverage.json"
    try:
        doc=json.loads(coverage.read_text(encoding="utf-8"))
    except (ValueError,OSError):
        return [], "priority_calendar_unavailable"
    if not isinstance(doc,dict) or not isinstance(doc.get("priority_fixtures"),list):
        return [], "priority_calendar_invalid"
    at=doc.get("checked_at")
    try:
        refresh=datetime.fromisoformat(at.replace("Z","+00:00"))
        if refresh.tzinfo is None or not -120 <= (now-refresh).total_seconds()<=6*3600:
            return [], "priority_calendar_stale"
    except (TypeError,ValueError,AttributeError):
        return [], "priority_calendar_invalid_timestamp"
    out={}
    for g in doc["priority_fixtures"]:
        if not isinstance(g,dict):
            continue
        try:
            kickoff=int(g.get("kickoff_unix") or 0)
        except (TypeError,ValueError,OverflowError):
            continue
        if not now.timestamp()<kickoff<=now.timestamp()+MAX_FUTURE_HOURS*3600:
            continue
        code=str(g.get("league_code") or "")
        h,a=str(g.get("home") or "").strip(),str(g.get("away") or "").strip()
        if not canonical_league(code) or not normalized_team(h) or not normalized_team(a) or normalized_team(h)==normalized_team(a):
            continue
        key=(code,normalized_team(h),normalized_team(a),kickoff)
        out[key]={"league_code":code,"league":g.get("league") or code,
                  "home":h,"away":a,"kickoff_unix":kickoff,
                  "kickoff_utc":datetime.fromtimestamp(kickoff,timezone.utc).isoformat()}
    return sorted(out.values(),key=lambda x:(x["kickoff_unix"],x["league_code"])),None


def generate(history_dir,archive_dir,now):
    matches=historical_rows(history_dir,now)
    fixtures,error=future_fixtures(archive_dir,now)
    result={"schema":1,"model_version":MODEL_VERSION,"generated_at":now.isoformat(),
            "source":"NEXUS independently computed Poisson model",
            "status":"ok" if error is None else error,
            "disclaimer":"ODDS TEORICAS NEXUS. Nao sao odds de casas, nao sao negociaveis, nao comprovam lucro, EV ou liquidez.",
            "market_scope":["FT 1X2","HT 1X2","HT/FT","Ambas marcam FT/HT",
                            "Over/Under FT/HT","Dupla chance FT","Totais por equipe FT",
                            "Placar exato FT"],
            "excluded_markets":["handicap","escanteios","cartoes","jogadores"],
            "historical_finished_games":len(matches),
            "cc0_matches":sum(m["source"]=="openfootball CC0" for m in matches),
            "fixtures_found":len(fixtures),
            "fixtures_priced":0,"fixtures_without_model":0,
            "fixtures":[]}
    for fixture in fixtures[:100]:
        training,reason=team_rates(matches,fixture,now)
        rec={**fixture,"model_status":"available" if training else reason,
             "not_a_bookmaker_quote":True}
        if training:
            rec["estimates"]={k:round(v,4) if isinstance(v,float) else v for k,v in training.items()}
            rec["markets"]=make_probability_book(
                training["lambda_home_ft"],training["lambda_away_ft"],training["first_half_share"])
            result["fixtures_priced"]+=1
        else:
            result["fixtures_without_model"]+=1
        result["fixtures"].append(rec)
    if not result["fixtures_priced"] and not error:
        result["status"]="no_qualified_prediction"
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history-dir",default="history")
    p.add_argument("--archive",default="market-history")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    output=generate(args.history_dir,args.archive,now)
    target=Path(args.archive)/"model-only"
    target.mkdir(parents=True,exist_ok=True)
    # Forecast is modelled, NEVER written into official price history.
    data=json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n"
    (target/"latest.json").write_text(data,encoding="utf-8")
    (target/(now.astimezone(BR).date().isoformat()+".json")).write_text(data,encoding="utf-8")
    print(json.dumps({k:output[k] for k in (
        "status","model_version","historical_finished_games","cc0_matches",
        "fixtures_found","fixtures_priced","fixtures_without_model")},ensure_ascii=False))


if __name__=="__main__":
    main()
