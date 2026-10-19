#!/usr/bin/env python3
"""Snapshot publico do NEXUS: jogos de 3 dias e forma anterior (10 por time), scouts, alertas e resultado paper auditavel.

NUNCA publica operacoes reais da Bolsa, importacao do PC, tokens ou dados privados.
O P/L exibido e somente simulacao retrospectiva de sinais congelados antes do inicio.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import math
import re
from signal_evaluation import evaluate
from nexus_intelligence_v6 import evaluate_v6, read_finished_archive
from market_evidence import audit_markets
from odds_fixture_bridge import bridge_pregame_prices
from scout_snapshots import public_snapshots, snapshot_deltas
from activity_timeline import observed_activity
from pregame_archive_merge import consolidate as consolidate_prelive

ROOT=Path(__file__).resolve().parent
H=ROOT/'history'
OUT=ROOT/'web'/'data.json'
BR=timezone(timedelta(hours=-3))
SCOUTS=('shots_on','shots_off','shots_total','corners','big_chances','dangerous_attacks',
        'possession','fouls','yellow_cards','red_cards','offsides','saves','passes',
        'pass_accuracy','xg')
TYPES={'goal','yellow_card','red_card','penalty_missed','shot_on','shot_off','big_chance_missed','substitution'}

def load(path):
    try:
        doc=json.loads(path.read_text(encoding='utf-8'))
        return doc if isinstance(doc,dict) else {}
    except (OSError,ValueError):
        return {}

def safe(value,maxlen=110):
    return str(value if value is not None else '').strip()[:maxlen]

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and abs(n)<100000 else None
    except (TypeError,ValueError,OverflowError):
        return None

def score_outcomes(score,phase):
    if phase!='finished':return {}
    m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',score)
    if not m:return {}
    home,away=map(int,m.groups())
    total=home+away
    return {'over_15':total>1,'over_25':total>2,'over_35':total>3,
            'btts':home>0 and away>0,'result':'home' if home>away else 'away' if away>home else 'draw',
            'correct_score':score}

def pregame_signal(item,fixture):
    if not isinstance(item,dict) or item.get('market')!='1x2':return None
    try:start=int(fixture.get('start_timestamp'))
    except (TypeError,ValueError,OverflowError):return None
    odds=number(item.get('odds'))
    prob=number(item.get('probability'))
    ev=number(item.get('ev_pct'))
    sample=number(item.get('sample_size'))
    side=safe(item.get('selection'),10)
    if side not in ('home','away','draw') or not start or not odds or odds<=1.01 or odds>=1000:return None
    if prob is None or not 0<=prob<=100 or ev is None or sample is None or sample<8:return None
    try:
        captured=datetime.fromisoformat(str(item.get('captured_at') or '').replace('Z','+00:00'))
        if not captured.tzinfo or captured.timestamp()>=start:return None
    except (TypeError,ValueError):return None
    settled=item.get('status')=='settled' and isinstance(item.get('won'),bool)
    result=round((odds-1) if item['won'] else -1,4) if settled else None
    return {'market':'1x2','selection':side,'odds':round(odds,4),
            'probability':round(prob,2),'ev_pct':round(ev,2),'sample_size':int(sample),
            'model':safe(item.get('model'),70),'captured_at':safe(item.get('captured_at'),40),
            'status':'settled' if settled else 'pending','paper_pl_u':result}

def public_form(doc):
    if not isinstance(doc,dict):return {'available':0,'requested':10,'games':[],'complete':False}
    games=[]
    for g in (doc.get('games') or [])[:10]:
        if not isinstance(g,dict):continue
        if g.get('result') not in ('V','E','D'):continue
        gf=number(g.get('gf'));ga=number(g.get('ga'))
        if gf is None or ga is None or gf<0 or ga<0:continue
        games.append({'day':safe(g.get('day'),10),'opponent':safe(g.get('opponent'),90),
                      'venue':safe(g.get('venue'),8),'score':safe(g.get('score'),10),
                      'result':g['result'],'gf':int(gf),'ga':int(ga)})
    n=len(games)
    base={'requested':10,'available':n,'complete':n==10,
          'source':safe(doc.get('source') or 'ESPN · mesma competição',70),'games':games}
    if not n:return base
    for name in ('wins','draws','losses','goals_for','goals_against',
                 'avg_goals_for','avg_goals_against','over15_pct','over25_pct','btts_pct'):
        val=number(doc.get(name))
        if val is not None:base[name]=val
    return base

def public_lineups(lineups):
    if not isinstance(lineups,dict):return {}
    output={}
    for side in ('home','away'):
        group=lineups.get(side) or {}
        if not isinstance(group,dict):continue
        def people(values):
            if not isinstance(values,list):return []
            output=[]
            for x in values[:25]:
                if not isinstance(x,dict) or not x.get('name'):continue
                item={'name':safe(x.get('name'),80),'number':safe(x.get('number'),4),
                      'id':safe(x.get('id'),16)}
                rating=number(x.get('rating'))
                if rating is not None and 0<=rating<=10:item['rating']=round(rating,2)
                output.append(item)
            return output
        starters=people(group.get('starters'))
        subs=people(group.get('subs'))
        if starters or subs:
            output[side]={'formation':safe(group.get('formation'),25),
                          'starters':starters,'subs':subs,'source':'FotMob',
                          'lineup_type':safe(group.get('lineup_type'),25),
                          'status':'confirmed' if group.get('status')=='confirmed' or
                              str(group.get('lineup_type') or '').lower() in ('standard','confirmed','official','actual','starting')
                              else 'predicted',
                          'updated_at':safe(group.get('updated_at'),40)}
    return output

def public_roster(groups):
    if not isinstance(groups,list):return []
    rows=[]
    for group in groups[:8]:
        if not isinstance(group,dict):continue
        players=[{'name':safe(p.get('name'),80),'number':safe(p.get('number'),4)}
                 for p in (group.get('players') or [])[:24]
                 if isinstance(p,dict) and p.get('name')]
        if players:rows.append({'section':safe(group.get('section'),45),'players':players})
    return rows

def verified_logo(value):
    """Imagens de clubes somente no CDN da ESPN, sem URL arbitraria."""
    import urllib.parse
    raw=safe(value,300)
    try:
        parsed=urllib.parse.urlparse(raw)
        if parsed.scheme=='https' and parsed.netloc in ('a.espncdn.com','a1.espncdn.com') and parsed.path.startswith('/i/teamlogos/'):
            return raw
        if parsed.scheme=='https' and parsed.netloc=='images.fotmob.com':
            import re
            if re.fullmatch(r'/image_resources/logo/teamlogo/\d{1,12}\.png',parsed.path):
                return raw
    except ValueError:
        pass
    return ''

def kickoff_number(value):
    """Timestamp Unix em segundos, sem o limite de valores de scouts."""
    try:
        n=int(value)
        return n if n>0 and n<4102444800 else None
    except (ValueError,TypeError,OverflowError):
        return None

def sort_games(rows):
    """Dia mais recente primeiro; em cada dia, pontape inicial mais cedo primeiro."""
    def key(row):
        stamp=kickoff_number(row.get('start_timestamp'))
        return (-int(row['day'].replace('-','')), 0 if stamp is not None and stamp>0 else 1,
                stamp if stamp is not None and stamp>0 else float('inf'),
                str(row.get('league') or ''),str(row.get('home') or ''))
    return sorted(rows,key=key)

def compact_name(value):
    """Iguala aliases claros como Instituto / Instituto (Cordoba), sem aproximacoes cegas."""
    import unicodedata
    raw=str(value or '').split('(')[0].strip().lower()
    raw=unicodedata.normalize('NFKD',raw)
    return re.sub(r'[^a-z0-9]+','', ''.join(c for c in raw if not unicodedata.combining(c)))

def merge_verified_duplicates(rows):
    """Une apenas mesmo dia, horario, nomes e placar compatíveis.
    Priorizamos ESPN como base (10 jogos / scouts); FotMob fornece pressão e logos
    complementares. Sem critérios suficientes ambos ficam separados.
    """
    output=[]
    for item in sorted(rows,key=lambda r:(r['day'],str(r.get('source')=='ESPN')),reverse=True):
        matched=None
        for base in output:
            if base['day']!=item['day']:continue
            a=kickoff_number(base.get('start_timestamp'))
            b=kickoff_number(item.get('start_timestamp'))
            if a is None or b is None or abs(a-b)>600:continue
            if compact_name(base.get('home'))!=compact_name(item.get('home')):continue
            if compact_name(base.get('away'))!=compact_name(item.get('away')):continue
            if base.get('phase')=='finished' and item.get('phase')=='finished' and base.get('score')!=item.get('score'):
                continue
            matched=base
            break
        if matched is None:
            output.append(item)
            continue
        joined=list(dict.fromkeys((matched.get('sources') or [matched.get('source')])+
                                  (item.get('sources') or [item.get('source')])))
        matched['sources']=[s for s in joined if s]
        for key in ('home_logo','away_logo','venue','round'):
            if key.endswith('_logo') and item.get('source')=='FotMob' and item.get(key):
                # FotMob fornece escudo nativo para esta partida; CDN ESPN pode retornar 404.
                matched[key]=item[key]
            elif not matched.get(key) and item.get(key):
                matched[key]=item[key]
        if item.get('phase')=='live' and matched.get('phase')=='scheduled':
            matched['phase']='live'
            matched['score']=item.get('score') or matched.get('score')
            matched['minute']=item.get('minute') or matched.get('minute')
        if len(item.get('pressure') or [])>len(matched.get('pressure') or []):
            matched['pressure']=item['pressure']
        if len(item.get('scout_snapshots') or [])>len(matched.get('scout_snapshots') or []):
            matched['scout_snapshots']=item['scout_snapshots']
        if len(item.get('head_to_head') or [])>len(matched.get('head_to_head') or []):
            matched['head_to_head']=item['head_to_head']
        if not matched.get('standings') and item.get('standings'):
            matched['standings']=item['standings']
        if not matched.get('pregame_baseline') and item.get('pregame_baseline'):
            matched['pregame_baseline']=item['pregame_baseline']
        for side in ('home','away'):
            if (item.get('lineups') or {}).get(side) and not (matched.get('lineups') or {}).get(side):
                matched.setdefault('lineups',{})[side]=item['lineups'][side]
        for side in ('home','away'):
            mstats=matched.setdefault('stats',{}).setdefault(side,{})
            for key,val in (item.get('stats',{}).get(side) or {}).items():
                if key not in mstats:mstats[key]=val
            mform=matched.setdefault('form',{}).get(side) or {}
            rform=(item.get('form') or {}).get(side) or {}
            if rform.get('available',0)>mform.get('available',0):
                matched['form'][side]=rform
            mroster=(matched.get('roster') or {}).get(side) or []
            eroster=(item.get('roster') or {}).get(side) or []
            if len(eroster)>len(mroster):matched.setdefault('roster',{})[side]=eroster
        for key in ('odds','closing_odds','events','signals'):
            original=matched.get(key) or []
            extra=item.get(key) or []
            seen={json.dumps(e,sort_keys=True,ensure_ascii=False) for e in original}
            for e in extra:
                signature=json.dumps(e,sort_keys=True,ensure_ascii=False)
                if signature not in seen:
                    original.append(e);seen.add(signature)
            matched[key]=original
    return output

def historical_h2h(row, cache, espn_cache=None):
    """Confrontos entre as duas equipes a partir de FotMob e ESPN já coletados.

    Não trata forma individual como H2H, não mistura IDs de provedores e
    não aceita confrontos futuros ou duplicados.
    """
    fixture=row.get('fixture') or {}
    cutoff=kickoff_number(fixture.get('start_timestamp'))
    if not cutoff:return []
    cache=cache if isinstance(cache,dict) else {}
    espn_cache=espn_cache if isinstance(espn_cache,dict) else {}
    found={}
    canonical={compact_name(fixture.get('home')),compact_name(fixture.get('away'))}
    if len(canonical)!=2 or '' in canonical:return []

    def insert(ts,home,away,hg,ag,competition,source):
        ts=kickoff_number(ts)
        if ts is None or ts>=cutoff:return
        if not all(isinstance(n,int) and 0<=n<=50 for n in (hg,ag)):return
        home_name,away_name=compact_name(home),compact_name(away)
        if {home_name,away_name}!=canonical:return
        # O placar é orientado por nome para não duplicar partidas com mandos inversos.
        lo=min(canonical)
        key=(datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),
             tuple(sorted(canonical)),hg if home_name==lo else ag,
             ag if home_name==lo else hg)
        item={'date':datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),
              'at':ts,'home':safe(home,105),'away':safe(away,105),
              'score':str(hg)+'-'+str(ag),'competition':safe(competition,70),
              'source':safe(source,40)}
        if key not in found or (source=='FotMob' and found[key]['source']!='FotMob'):
            found[key]=item

    for side in ('home','away'):
        team_id=str(fixture.get(side+'_id') or '')
        opponent=fixture.get('away' if side=='home' else 'home') or ''
        entry=cache.get(team_id) or {}
        for prev in (entry.get('games') or []):
            if not isinstance(prev,dict) or compact_name(prev.get('opponent'))!=compact_name(opponent):continue
            venue=prev.get('venue')
            if venue not in ('Casa','Fora'):continue
            try:gf=int(prev.get('gf'));ga=int(prev.get('ga'))
            except (ValueError,TypeError):continue
            home=fixture.get(side) if venue=='Casa' else opponent
            away=opponent if venue=='Casa' else fixture.get(side)
            hg,ag=(gf,ga) if venue=='Casa' else (ga,gf)
            insert(prev.get('ts'),home,away,hg,ag,
                   prev.get('league') or fixture.get('league'),'FotMob')

    league=str(fixture.get('league_code') or '')
    home_id=str(fixture.get('home_id') or '')
    away_id=str(fixture.get('away_id') or '')
    # ESPN e FotMob possuem IDs de time diferentes. Só usar o calendário
    # ESPN quando o jogo ATUAL também for uma fixture ESPN.
    if (str(fixture.get('id') or '').startswith('espn-') and
            league and home_id.isdigit() and away_id.isdigit()):
        all_schedules=espn_cache.get('schedules') or {}
        for tid in (home_id,away_id):
            entry=all_schedules.get(league+'/'+tid) or {}
            for old in (entry.get('games') or []):
                if not isinstance(old,dict) or old.get('phase')!='finished':continue
                if {str(old.get('home_id') or ''),str(old.get('away_id') or '')}!={home_id,away_id}:continue
                m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',str(old.get('score') or ''))
                if m:
                    insert(old.get('start_timestamp'),old.get('home'),old.get('away'),
                           int(m.group(1)),int(m.group(2)),old.get('league') or league,'ESPN')

    for prev in (row.get('h2h_verified') or []):
        if not isinstance(prev,dict):continue
        m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',str(prev.get('score') or ''))
        if m:
            insert(prev.get('at'),prev.get('home'),prev.get('away'),
                   int(m.group(1)),int(m.group(2)),prev.get('competition'),prev.get('source') or 'FotMob')
    return sorted(found.values(),key=lambda x:x['at'],reverse=True)[:20]


def public_baseline(row, fixture):
    """Só dados esportivos congelados antes do início; não inventa histórico."""
    original = row.get('pregame_baseline') or {}
    if not isinstance(original, dict) or original.get('schema') != 1:
        return None
    start = kickoff_number(fixture.get('start_timestamp'))
    try:
        captured = datetime.fromisoformat(original['captured_at'].replace('Z', '+00:00'))
        if not captured.tzinfo or not start or captured.timestamp() >= start:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    f = original.get('forecast') or {}
    p = f.get('one_x_two') or {}
    if any(number(p.get(k)) is None for k in ('home', 'draw', 'away')):
        return None
    picks = []
    for item in (original.get('indications') or [])[:4]:
        if not isinstance(item, dict):
            continue
        value = number(item.get('probability'))
        if value is None or not 0 <= value <= 100:
            continue
        picks.append({'market': safe(item.get('market'),30),
                      'selection': safe(item.get('selection'),20),
                      'probability': round(value,2)})
    settlement = original.get('settlement') or {}
    checks = []
    for x in (settlement.get('checks') or [])[:4]:
        if not isinstance(x, dict) or x.get('result') not in ('hit','miss'):
            continue
        checks.append({'market':safe(x.get('market'),30),
                       'selection':safe(x.get('selection'),20),
                       'result':x['result']})
    o = original.get('odds') or {}
    prices = o.get('prices') or {}
    odds = None
    try:
        at = datetime.fromisoformat(str(o.get('captured_at','')).replace('Z','+00:00'))
        if (at.tzinfo and at.timestamp()<start and all(
                number(prices.get(k)) is not None and 1.01<number(prices[k])<1000
                for k in ('home','draw','away'))):
            odds = {'source':safe(o.get('source'),40),
                    'bookmaker':safe(o.get('bookmaker'),55),
                    'captured_at':at.isoformat(),
                    'prices':{k:round(float(prices[k]),4)
                              for k in ('home','draw','away')},
                    'recent_at_check':o.get('recent_at_check') is True}
    except (TypeError,ValueError):
        pass
    estimates = {}
    if odds and odds.get('recent_at_check'):
        for item in picks:
            if item['market']=='1x2':
                side = item['selection']
                price = odds['prices'].get(side)
                if price:
                    estimates = {'market':'1x2','selection':side,'odd':price,
                                 'ev_pct':round(item['probability']*price-100,2),
                                 'classification':'theoretical_uncalibrated'}
    samp = original.get('sample') or {}
    samples = {side:{'n':int(number((samp.get(side) or {}).get('n')) or 0),
                     'gf':number((samp.get(side) or {}).get('gf')),
                     'ga':number((samp.get(side) or {}).get('ga'))}
               for side in ('home','away')}
    return {'captured_at':captured.isoformat(),
            'model':safe(original.get('model'),100),
            'model_status':'experimental_uncalibrated',
            'forecast':{'one_x_two':{k:round(float(p[k]),2)
                                   for k in ('home','draw','away')},
                        'over_2_5_pct':number(f.get('over_2_5_pct')),
                        'btts_yes_pct':number(f.get('btts_yes_pct')),
                        'expected_goals':{
                            k:number((f.get('expected_goals') or {}).get(k))
                            for k in ('home','away')},
                        'top_scores':(f.get('top_scores') or [])[:3]},
            'sample':samples,'indications':picks,
            'odds':odds,'model_ev':estimates or None,
            'settlement':{'status':'finished','score':safe(settlement.get('score'),12),
                          'hits':sum(x['result']=='hit' for x in checks),
                          'count':len(checks),'checks':checks}
                         if checks else None}


def prelive_archive():
    """Até 90 dias de pré-live, uma partida por confronto com variantes originais.

    O histórico fonte não é editado. Consolida previsões FotMob/ESPN de
    mesma partida e compara com placar final CONFIRMADO de qualquer registro
    compatível. Se houver placares divergentes, não liquida no painel.
    """
    last = datetime.now(BR).date()
    cutoff = last - timedelta(days=90)
    records = []
    for path in sorted(H.glob('20??-??-??.json')):
        try:
            day = datetime.strptime(path.stem,'%Y-%m-%d').date()
        except ValueError:
            continue
        if day < cutoff:
            continue
        doc = load(path)
        for row in (doc.get('matches') or {}).values():
            if not isinstance(row,dict):continue
            f = row.get('fixture') or {}
            if not isinstance(f,dict) or not f.get('home') or not f.get('away'):
                continue
            baseline = public_baseline(row,f)
            # Importante: jogos ESPN sem baseline podem conter o placar FT
            # necessário para verificar a previsão FotMob, e vice-versa.
            records.append({'fixture':f,'day':path.stem,'pregame_baseline':baseline})
    return consolidate_prelive(records)


ODDS_SELECTIONS={
 '1x2':('home','draw','away'),
 'over_under_25':('over','under'),
 'btts':('yes','no'),
 'ah_0':('home','away'),
}
def public_odds_comparison(quotes,fixture,phase,now_ts):
    """Comparacao de precos reais, por fase, sem misturar casas e horarios."""
    if fixture.get('phase')!=('live' if phase=='live' else 'scheduled'):return []
    try:kickoff=int(fixture.get('start_timestamp') or 0)
    except (ValueError,TypeError):return []
    if not kickoff:return []
    latest={}
    for q in quotes:
        if not isinstance(q,dict):continue
        market=q.get('market')
        sel=q.get('selection') or q.get('sel')
        if market not in ODDS_SELECTIONS or sel not in ODDS_SELECTIONS[market]:continue
        value=number(q.get('odds',q.get('odd')))
        if value is None or not 1.01<value<1000:continue
        book=safe(q.get('bookmaker'),55)
        source=safe(q.get('source'),40)
        if not book or not source:continue
        try:at=datetime.fromisoformat(str(q.get('captured_at') or q.get('at') or '').replace('Z','+00:00'))
        except (ValueError,TypeError):continue
        if at.tzinfo is None:continue
        t=at.timestamp()
        if t>now_ts+120:continue
        if phase=='pregame' and (t>=kickoff or now_ts-t>24*3600):continue
        if phase=='live' and (t<kickoff or now_ts-t>900):continue
        key=(market,sel,book,source)
        if key not in latest or latest[key]['unix']<t:
            latest[key]={'odds':round(value,3),'bookmaker':book,'source':source,
                         'at':at.isoformat(),'unix':t}
    grouped={}
    for (market,sel,_,_),v in latest.items():
        grouped.setdefault((market,sel),[]).append(v)
    out=[]
    for (market,sel),offers in sorted(grouped.items()):
        offers.sort(key=lambda x:(-x['odds'],-x['unix'],x['bookmaker']))
        clean=[{k:v for k,v in q.items() if k!='unix'} for q in offers[:5]]
        out.append({'market':market,'selection':sel,'best':clean[0],
                    'alternatives':clean[1:4],
                    'books_compared':len(offers),'phase':phase})
    return out[:18]

def public_row(row,day,team_cache=None,espn_cache=None):
    if not isinstance(row,dict):return None
    f=row.get('fixture') or {}
    if not isinstance(f,dict) or not f.get('home') or not f.get('away'):return None
    points=[]
    for point in ((row.get('thermometer') or {}).get('points') or []):
        if not isinstance(point,dict):continue
        try:
            m=int(point.get('minute'));v=number(point.get('value'))
        except (TypeError,ValueError):continue
        if v is not None and 1<=m<=150:points.append({'m':m,'v':round(v,2)})
    points=sorted({p['m']:p for p in points}.values(),key=lambda p:p['m'])[-150:]
    stats={}
    for side in ('home','away'):
        orig=(row.get('stats') or {}).get(side) or {}
        stats[side]={}
        if not isinstance(orig,dict):continue
        for key in SCOUTS:
            n=number(orig.get(key))
            if n is not None:stats[side][key]=n
    odds=[]
    for item in row.get('odds_quotes') or []:
        if not isinstance(item,dict):continue
        val=number(item.get('odds'))
        if val is None or not 1.01<=val<=1000:continue
        if item.get('market')=='1x2' and item.get('selection') in ('home','draw','away'):
            odds.append({'sel':item['selection'],'odd':round(val,3),
                         'source':safe(item.get('source'),24),
                         'bookmaker':safe(item.get('bookmaker'),35),
                         'at':safe(item.get('captured_at'),36)})
    # O trio 1/X/2 deve vir da MESMA captura, casa e fonte: o favorito
    # não pode ser atualizado isoladamente com empate antigo como se
    # fossem odds simultâneas. Mostrar a última captura COMPLETA.
    quote_groups={}
    for offer in odds:
        tag=(offer.get('source') or '',offer.get('bookmaker') or '',offer.get('at') or '')
        group=quote_groups.setdefault(tag,{})
        group[offer['sel']]=offer
    # Preservar uma captura íntegra por casa/fonte. Nunca compor 1X2 usando
    # preços de casas, consultas ou horários diferentes.
    complete_groups=sorted(
        ((tag,group) for tag,group in quote_groups.items()
         if set(group)=={'home','draw','away'} and all(tag)),
        key=lambda item:item[0][2],reverse=True)
    chosen={}
    for tag,group in complete_groups:
        provider=(tag[0],tag[1])
        if provider not in chosen:
            chosen[provider]=group
        if len(chosen)>=5:break
    if chosen:
        odds=[{**group[side],'trio_complete':True} for group in chosen.values()
              for side in ('home','draw','away')]
    else:
        # Legado: manter apenas a última captura de uma casa identificada.
        # Odds isoladas são dados reais, mas NÃO são um trio 1X2 comparável.
        partial=sorted(((tag,g) for tag,g in quote_groups.items()
                        if tag[1] and tag[2]),
                       key=lambda item:item[0][2],reverse=True)
        last=partial[0][1] if partial else {}
        odds=[{**last[side],'trio_complete':False}
              for side in ('home','draw','away') if side in last]
    pre_items=(row.get('market_quotes') or [])
    live_items=(row.get('live_odds_quotes') or [])
    if not isinstance(pre_items,list):pre_items=[]
    if not isinstance(live_items,list):live_items=[]
    pre_comp=public_odds_comparison(
        [{**x,'market':'1x2','selection':x['sel'],'odds':x['odd'],
          'captured_at':x['at']} for x in odds if x.get('trio_complete')]
        +pre_items,f,'pregame',datetime.now(timezone.utc).timestamp())
    live_comp=public_odds_comparison(
        live_items,f,'live',datetime.now(timezone.utc).timestamp())
    events=[]
    for event in row.get('events') or []:
        if not isinstance(event,dict) or event.get('type') not in TYPES:continue
        try:minute=int(event.get('minute'))
        except (ValueError,TypeError):continue
        if not 0<=minute<=130:continue
        public_event={'m':minute,'type':event['type'],
                      'side':event.get('side') if event.get('side') in ('home','away') else '',
                      'text':safe(event.get('text'),125)}
        if event['type']=='goal':
            public_event.update(player=safe(event.get('player'),90),
                                assist=safe(event.get('assist'),90),
                                own_goal=event.get('own_goal') is True,
                                penalty=event.get('penalty') is True,
                                source=safe(event.get('source'),50))
        if event['type']=='substitution' and public_event['side']:
            incoming=safe(event.get('player_in'),80)
            outgoing=safe(event.get('player_out'),80)
            if not incoming or not outgoing:continue
            public_event.update(player_in=incoming,player_out=outgoing)
        events.append(public_event)
    signals=[]
    for item in row.get('paper_signals') or []:
        q=pregame_signal(item,f)
        if q:signals.append(q)
    forms=row.get('team_form') or {}
    rosters=row.get('team_roster') or {}
    lineups=public_lineups(row.get('lineups') or {})
    stars={}
    for side in ('home','away'):
        data=(row.get('match_stars') or {}).get(side) or {}
        if isinstance(data,dict) and data.get('player') and data.get('source')=='FotMob':
            stars[side]={'player':safe(data['player'],80),'label':safe(data.get('label'),75),
                         'kind':safe(data.get('kind'),35),'source':'FotMob',
                         'rating':number(data.get('rating'))}
    leaders={}
    for side in ('home','away'):
        data=(row.get('team_leaders') or {}).get(side) or {}
        if not isinstance(data,dict):continue
        available={}
        for key in ('goals','assists','rating'):
            player=data.get(key) or {}
            if not isinstance(player,dict) or player.get('source')!='FotMob · atletas da equipe':
                continue
            value=number(player.get('value'))
            if value is not None and player.get('name'):
                available[key]={'name':safe(player['name'],80),'value':value,
                                'source':'FotMob · atletas da equipe'}
        if available:
            available['updated_at']=safe(data.get('updated_at'),40)
            available['coverage_players']=data.get('coverage_players')
            leaders[side]=available
    h2h=historical_h2h(row,team_cache,espn_cache)
    context=row.get('standings_context') or {}
    ranking=None
    if isinstance(context,dict) and isinstance(context.get('home'),dict) and isinstance(context.get('away'),dict):
        def compact_rank(x):
            data=context.get(x) or {}
            reasons=[{'kind':safe(t.get('kind'),35),'label':safe(t.get('label'),60),
                      'detail':safe(t.get('detail'),190)}
                     for t in (data.get('reasons') or [])[:3] if isinstance(t,dict)]
            return {'position':data.get('position'),'points':data.get('points'),
                    'played':data.get('played'),'total_teams':data.get('total_teams'),
                    'group':safe(data.get('group'),70),
                    'level':safe(data.get('level'),24),'reasons':reasons}
        canonical=str(f.get('league_id') or '')
        table_url=('https://www.fotmob.com/leagues/'+canonical+'/table'
                   if f.get('league_id_verified') is True and
                      canonical.isdecimal() and 0<int(canonical)<100000 else None)
        ranking={'home':compact_rank('home'),'away':compact_rank('away'),
                 'table_url':table_url,
                 'source':safe(context.get('source'),20),
                 'league':safe(context.get('league'),80),
                 'season':safe(context.get('season'),25),
                 'updated_at':safe(context.get('updated_at'),42),
                 'note':'Urgência situacional, não obrigação matemática de vencer.'}
    sources=list(dict.fromkeys([safe(f.get('source'),45)]+
        [safe(x,45) for x in (row.get('sources') or [])]))[:6]
    closing=[]
    for q in row.get('closing_odds') or []:
        if not isinstance(q,dict) or q.get('type')!='historical_closing':continue
        odd=number(q.get('odd'))
        if odd is None or not 1.01<=odd<=1000:continue
        if q.get('sel') in ('home','draw','away'):
            closing.append({'sel':q['sel'],'odd':round(odd,3),'bookmaker':safe(q.get('bookmaker'),35),
                            'source':'Football-Data.co.uk','type':'historical_closing'})
    return {'day':day,'id':safe(f.get('id'),90),
            'home':safe(f.get('home')),'away':safe(f.get('away')),
            'league':safe(f.get('league'),85),'league_code':safe(f.get('league_code'),40),
            'round':safe(f.get('round'),70),'venue':safe(f.get('venue'),100),
            'home_logo':verified_logo(f.get('home_logo')),'away_logo':verified_logo(f.get('away_logo')),
            'start_timestamp':f.get('start_timestamp'),'minute':f.get('minute') or 0,
            'score':safe(f.get('score'),12),'phase':safe(f.get('phase'),12),
            'halftime':f.get('halftime') is True and f.get('phase')=='live',
            'status_short':'HT' if f.get('halftime') is True and f.get('phase')=='live' else '',
            'source':safe(f.get('source'),30),'sources':sources,'closing_odds':closing[:9],
            'score_verification':(row.get('score_verifications') or {}).get('openfootball_cc0'),
            'observed_at':safe(f.get('collected_at'),36),
             'stats_observed_at':safe(row.get('stats_updated_at'),40),
             'stats_source':safe(row.get('stats_source') or f.get('source'),40),
             'pressure_observed_at':safe(row.get('pressure_updated_at'),40),
             'pressure_last_minute':points[-1]['m'] if points else None,
             'momentum_diagnostic':{
                 'state':safe((row.get('momentum_diagnostic') or {}).get('state'),30),
                 'source_path':safe((row.get('momentum_diagnostic') or {}).get('source_path'),70),
                 'checked_at':safe((row.get('momentum_diagnostic') or {}).get('checked_at'),42)},
            'pressure':points,'stats':stats,'scout_snapshots':public_snapshots(row.get('scout_snapshots')),
            'scout_trend':snapshot_deltas(row.get('scout_snapshots')) if f.get('phase')=='live' else {'status':'not_live'},
            'head_to_head':h2h,'standings':ranking,
            'form':{s:public_form(forms.get(s)) for s in ('home','away')},
            'roster':{s:public_roster(rosters.get(s)) for s in ('home','away')},
            'lineups':lineups,'match_stars':stars,'team_leaders':leaders,
            'odds':odds[:15],
            'odds_comparison':pre_comp,'live_odds_comparison':live_comp,
            'events':events[:130], 'activity_timeline':observed_activity(row.get('events')),
            'signals':signals[:20],
            'pregame_baseline':public_baseline(row,f),
            'outcomes':score_outcomes(safe(f.get('score'),12),f.get('phase'))}

def paper_summary(rows):
    """P/L *paper* em unidades: 1u de risco por sinal BACK 1X2 validado.

    Nunca mistura PL da Bolsa ou odds historicas de fechamento. Ganho e
    perda brutos so existem para sinais efetivamente liquidados.
    """
    signals=[s for r in rows for s in r.get('signals',[]) if isinstance(s,dict)]
    settled=[]
    for signal in signals:
        if signal.get('status')!='settled':continue
        amount=number(signal.get('paper_pl_u'))
        if isinstance(signal.get('paper_pl_u'),bool) or amount is None:continue
        if not isinstance(signal.get('market'),str):continue
        settled.append((signal,amount))
    if not settled:
        return {'unit':'1u nominal por entrada BACK 1X2 (paper, sem taxas)',
                'status':'insufficient_data','settled':0,'pending':len(signals),
                'won':0,'lost':0,'profit_u':None,'loss_u':None,'roi_pct':None,
                'paper_pl_u':None,'markets':[]}
    groups={}
    profit=loss=0.0
    wins=losses=0
    for signal,amount in settled:
        group=groups.setdefault(signal['market'],{'market':signal['market'],
              'entries':0,'wins':0,'losses':0,'profit_u':0.0,'loss_u':0.0,
              'paper_pl_u':0.0})
        group['entries']+=1
        if amount>0:
            wins+=1
            profit+=amount
            group['wins']+=1
            group['profit_u']+=amount
        elif amount<0:
            losses+=1
            loss+=-amount
            group['losses']+=1
            group['loss_u']+=-amount
        group['paper_pl_u']+=amount
    for group in groups.values():
        for key in ('profit_u','loss_u','paper_pl_u'):
            group[key]=round(group[key],3)
        group['roi_pct']=round(group['paper_pl_u']/group['entries']*100,2)
    net=round(profit-loss,3)
    return {'unit':'1u nominal por entrada BACK 1X2 (paper, sem taxas)',
            'status':'with_settlements',
            'settled':len(settled),'pending':len(signals)-len(settled),
            'won':wins,'lost':losses,'profit_u':round(profit,3),
            'loss_u':round(loss,3),'roi_pct':round(net/len(settled)*100,2),
            'paper_pl_u':net,
            'markets':sorted(groups.values(),key=lambda g:g['paper_pl_u'],reverse=True)}

def market_history(rows):
    finished=[g['outcomes'] for g in rows if g.get('outcomes',{}).get('correct_score')]
    n=len(finished)
    if not n:return {'matches':0,'markets':[]}
    selectors=[
        ('Over 1.5 FT',lambda o:o['over_15']),
        ('Over 2.5 FT',lambda o:o['over_25']),
        ('Under 2.5 FT',lambda o:not o['over_25']),
        ('Over 3.5 FT',lambda o:o['over_35']),
        ('BTTS Sim',lambda o:o['btts']),
        ('BTTS Nao',lambda o:not o['btts']),
        ('Match Odds Casa',lambda o:o['result']=='home'),
        ('Match Odds Empate',lambda o:o['result']=='draw'),
        ('Match Odds Fora',lambda o:o['result']=='away'),
    ]
    return {'matches':n,'markets':[{'market':name,'occurred':sum(bool(fn(o)) for o in finished),
             'matches':n,'rate_pct':round(100*sum(bool(fn(o)) for o in finished)/n,1)}
             for name,fn in selectors],
             'note':'Frequencias de placares encerrados, sem odds de entrada e sem indicador de lucro ou EV+'}

def alerts_from(rows):
    alerts=[]
    for g in rows:
        if len(alerts)>=35:break
        if g['phase']=='finished':continue
        for s in g['signals']:
            if (s['status']=='pending' and s['ev_pct']>5 and
                s.get('model_validated') is True and s.get('probability_calibrated') is True):
                alerts.append({'kind':'ev_experimental','match_id':g['id'],'day':g['day'],
                               'title':'EV experimental '+s['selection'].upper()+' · '+safe(g['home'])+' × '+safe(g['away']),
                               'detail':'EV '+str(s['ev_pct'])+'% · odd '+str(s['odds'])+
                                        ' · modelo '+safe(s['model'])+' (nao validado)',
                               'observed_at':s['captured_at']})
        if g['phase']=='scheduled' and g['odds'] and not g['signals']:
            quotes=', '.join(x['sel']+' '+str(x['odd']) for x in g['odds'][:3])
            alerts.append({'kind':'odds_watch','match_id':g['id'],'day':g['day'],
                           'title':'Cotações 1X2 · '+g['home']+' × '+g['away'],
                           'detail':quotes+'. Sem probabilidade validada: EV+ indisponível.',
                           'observed_at':g['odds'][0].get('at')})
        if g['phase']=='live':
            on=[number((g['stats'].get(side) or {}).get('shots_on')) for side in ('home','away')]
            corners=[number((g['stats'].get(side) or {}).get('corners')) for side in ('home','away')]
            if all(x is not None for x in on) and sum(on)>=7:
                alerts.append({'kind':'stat_watch','match_id':g['id'],'day':g['day'],
                               'title':'Finalizacoes no alvo · '+g['home']+' × '+g['away'],
                               'detail':str(int(sum(on)))+' chutes no alvo registrados. Somente monitoramento; EV nao calculado.',
                               'observed_at':g['observed_at']})
            if all(x is not None for x in corners) and sum(corners)>=9:
                alerts.append({'kind':'stat_watch','match_id':g['id'],'day':g['day'],
                               'title':'Escanteios · '+g['home']+' × '+g['away'],
                               'detail':str(int(sum(corners)))+' escanteios registrados. Somente monitoramento; EV nao calculado.',
                               'observed_at':g['observed_at']})
    return alerts[:35]

def historical_xg_summary(status):
    """Metadados seguros, sem divulgar o historico jogo a jogo no site."""
    if not isinstance(status,dict):status={}
    n=status.get('games_with_home_away_xg')
    valid=(status.get('ready_for_research') is True and
           status.get('integrated_into_live_ev') is False and
           status.get('source')=='soccerdata Understat' and
           status.get('season')=='2025/2026' and
           isinstance(n,int) and not isinstance(n,bool) and 0<n<=380)
    return {'available':valid,'source':'soccerdata Understat' if valid else None,
            'matches_verified':n if valid else 0,
            'league':'Premier League' if valid else None,
            'season':'2025/2026' if valid else None,
            'scope':'historico_final','live_xg':False,'ev_plus':False}

def make_listing(rows,exported_at,collector):
    """Feed da agenda: sem detalhes, sem histórico financeiro, sem dados inventados."""
    fields=('id','day','home','away','home_logo','away_logo','league',
            'round','start_timestamp','minute','score','phase','halftime',
            'status_short','source','sources','observed_at',
            'pressure_observed_at','pressure_last_minute','odds','stats')
    games=[]
    for game in rows:
        item={field:game.get(field) for field in fields}
        points=game.get('pressure') or []
        item['pressure']=points if game.get('phase')=='live' else points[-1:]
        games.append(item)
    return {'schema':3,'format':'listing_only','exported_at':exported_at,
            'collector':collector,'games':games}


def main():
    today=datetime.now(BR).date()
    days={(today-timedelta(days=i)).isoformat() for i in range(3)}
    rows=[]
    espn_cache=load(H/'team_schedule_cache.json')
    fotmob_cache=(load(H/'fotmob_team_cache.json').get('teams') or {})
    if not isinstance(fotmob_cache,dict):fotmob_cache={}
    for path in sorted(H.glob('20??-??-??.json'),reverse=True):
        if path.stem not in days:continue
        doc=load(path)
        matches=doc.get('matches') or {}
        if not isinstance(matches,dict):continue
        for row in matches.values():
            fixture=(row or {}).get('fixture') or {}
            stamp=kickoff_number(fixture.get('start_timestamp'))
            # As APIs podem agrupar pela data UTC. O painel de tres dias usa
            # a data do apito inicial no horario de Brasilia.
            local_day=datetime.fromtimestamp(stamp,BR).date().isoformat() if stamp else path.stem
            if local_day not in days:continue
            item=public_row(row,local_day,fotmob_cache,espn_cache)
            if item:rows.append(item)
    rows=sort_games(merge_verified_duplicates(rows))
    odds_bridge=bridge_pregame_prices(rows)
    # Conservar partidas de todos os dias; sem truncamento prematuro que exclua o historico.
    rows=rows[:1800]  # cobertura de todos os campeonatos na janela de 3 dias
    last=load(H/'status.json')
    backfill=load(H/'backfill_status.json')
    team_form=load(H/'team_form_status.json')
    external=load(H/'multi_source_status.json')
    cc0=load(H/'openfootball_cc0_status.json')
    historical_xg=historical_xg_summary(load(H/'soccerdata_xg_status.json'))
    fotmob=load(H/'fotmob_form_status.json')
    status={key:last.get(key) for key in ('day','updated_at','sources','live_found','thermometers_saved','scout_snapshots_saved','momentum_unavailable','momentum_status_counts','stats_detail_available') if key in last}
    standings_status=load(H/'standings_status.json')
    registry=load(H/'signal_registry.json')
    all_signal_items=registry.get('items') or []
    signal_journal={'total_records':len(all_signal_items),
        'export_limit':5000,'truncated':len(all_signal_items)>5000,
        'updated_at':registry.get('updated_at'),
        'diagnostics':registry.get('diagnostics') or {},
        'items':all_signal_items[:5000],
        'note':'Sinais 5.29 na nuvem; gols em janelas de 5 a 40 minutos conforme eventos. EV indisponivel sem odds e modelo calibrado.'}
    archive_stats=read_finished_archive(H,as_of=today)
    radar_v6=evaluate_v6(registry,rows,as_of=today,historical_archive=archive_stats)
    pregame=prelive_archive()
    evidence=audit_markets(pregame)
    payload={'app':'NEXUS SCORE WEB','schema':2,'exported_at':datetime.now(timezone.utc).isoformat(),
             'collector':status,'backfill':{k:backfill.get(k) for k in ('days','games','with_stats','events','checked_at')},
             'team_form_status':{k:team_form.get(k) for k in ('checked_at','teams','games_with_form','complete_team_samples')},
             'historical_xg':historical_xg,
             'source_status':{**{k:external.get(k) for k in ('updated_at','files_checked','cross_verified','stats_filled','added','historical_odds','providers')},
                'openfootball_cc0':{k:cc0.get(k) for k in ('updated_at','checked','cross_verified','conflicts','ambiguous','unmatched','unavailable','datasets_fetched','cache_hits','errors')}},

             'fotmob_form_status':{k:fotmob.get(k) for k in ('updated_at','teams_discovered','requests_succeeded','games_with_form','teams_with_10','roster_teams')},
             'standings_collection_status':{k:standings_status.get(k) for k in (
               'updated_at','leagues_found','leagues_queried','tables_received',
               'fixtures_enriched','with_urgency','cache_tables_present',
               'cache_tables_reused_fresh','fixtures_without_verified_table',
               'unqueried_leagues','by_source')},
             'notice':'Atualizacao periodica, sem odds em tempo real. EV experimental nao e recomendacao nem lucro realizado.',
             'odds_bridge':odds_bridge,
             'pregame_archive':pregame,
             'market_evidence':evidence,
             'odds_collection_status':{k:load(H/'pregame_refresh_status.json').get(k)
               for k in ('updated_at','odds_updated','sofascore_checked','sofascore_quotes_added','the_odds_api','api_football','odds_papi','espn_fallback','errors')},
             'paper':paper_summary(rows),'market_history':market_history(rows),
             'signal_journal':signal_journal,'signal_evaluation':evaluate(registry),
             'intelligence_v6':radar_v6,
             'alerts':alerts_from(rows),'games':rows}
    # Feed de jogos sem dados financeiros nem detalhes extensos.
    OUT.parent.mkdir(parents=True,exist_ok=True)
    lite=make_listing(rows,payload['exported_at'],payload['collector'])
    lite_path=OUT.parent/'listing.json'
    lite_tmp=lite_path.with_suffix('.tmp')
    lite_tmp.write_text(json.dumps(lite,ensure_ascii=False,separators=(',',':'))+'\n',
                        encoding='utf-8')
    lite_tmp.replace(lite_path)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(OUT)
    print('WEB EXPORT:',len(rows),'jogos,',len(payload['alerts']),'alertas de monitoramento,',
          payload['paper']['settled'],'operacoes paper; ZERO dados financeiros privados')
if __name__=='__main__':main()
