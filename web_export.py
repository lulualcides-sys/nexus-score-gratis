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

ROOT=Path(__file__).resolve().parent
H=ROOT/'history'
OUT=ROOT/'web'/'data.json'
BR=timezone(timedelta(hours=-3))
SCOUTS=('shots_on','shots_off','shots_total','corners','big_chances','dangerous_attacks',
        'possession','fouls','yellow_cards','red_cards','offsides','saves','passes',
        'pass_accuracy','xg')
TYPES={'goal','yellow_card','red_card','penalty_missed','shot_on','shot_off'}

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
            return [{'name':safe(x.get('name'),80),'number':safe(x.get('number'),4)}
                     for x in values[:25] if isinstance(x,dict) and x.get('name')]
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
        if len(item.get('head_to_head') or [])>len(matched.get('head_to_head') or []):
            matched['head_to_head']=item['head_to_head']
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

def historical_h2h(row, cache):
    """Confrontos diretos verificaveis anteriores ao jogo a partir do cache FotMob.
    Identidades precisam coincidir e o horario da partida deve ser anterior ao duelo.
    """
    fixture=row.get('fixture') or {}
    cutoff=kickoff_number(fixture.get('start_timestamp'))
    if not cutoff:return []
    if not isinstance(cache,dict):return []
    found={}
    for side in ('home','away'):
        team_id=str(fixture.get(side+'_id') or '')
        opponent=fixture.get('away' if side=='home' else 'home') or ''
        entry=cache.get(team_id) or {}
        for prev in (entry.get('games') or []):
            if not isinstance(prev,dict):continue
            ts=kickoff_number(prev.get('ts'))
            if ts is None or ts>=cutoff:continue
            if compact_name(prev.get('opponent'))!=compact_name(opponent):continue
            venue=prev.get('venue')
            if venue not in ('Casa','Fora'):continue
            try:
                gf=int(prev.get('gf'));ga=int(prev.get('ga'))
                if not (0<=gf<=50 and 0<=ga<=50):continue
            except (ValueError,TypeError):continue
            home=fixture.get(side) if venue=='Casa' else opponent
            away=opponent if venue=='Casa' else fixture.get(side)
            hg,ag=(gf,ga) if venue=='Casa' else (ga,gf)
            item={'date':str(prev.get('day') or '')[:10],
                  'at':ts,'home':safe(home,105),'away':safe(away,105),
                  'score':str(hg)+'-'+str(ag),
                  'competition':safe(prev.get('league') or fixture.get('league'),70),
                  'source':'FotMob'}
            found[(ts,compact_name(home),compact_name(away),hg,ag)]=item
    return sorted(found.values(),key=lambda x:x['at'],reverse=True)[:15]

def public_row(row,day,team_cache=None):
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
    # Mostrar a cotação mais recente por seleção; o histórico integral fica
    # no arquivo privado de coleta. Nunca misturar odds históricas simuladas.
    latest={}
    for offer in odds:
        side=offer['sel']
        previous=latest.get(side)
        if not previous or str(offer.get('at') or '')>=str(previous.get('at') or ''):
            latest[side]=offer
    odds=[latest[side] for side in ('home','draw','away') if side in latest]
    events=[]
    for event in row.get('events') or []:
        if not isinstance(event,dict) or event.get('type') not in TYPES:continue
        try:minute=int(event.get('minute'))
        except (ValueError,TypeError):continue
        if not 0<=minute<=130:continue
        events.append({'m':minute,'type':event['type'],
                       'side':event.get('side') if event.get('side') in ('home','away') else '',
                       'text':safe(event.get('text'),125)})
    signals=[]
    for item in row.get('paper_signals') or []:
        q=pregame_signal(item,f)
        if q:signals.append(q)
    forms=row.get('team_form') or {}
    rosters=row.get('team_roster') or {}
    lineups=public_lineups(row.get('lineups') or {})
    h2h=historical_h2h(row,team_cache)
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
            'source':safe(f.get('source'),30),'sources':sources,'closing_odds':closing[:9],
            'observed_at':safe(f.get('collected_at'),36),
            'pressure':points,'stats':stats,'head_to_head':h2h,
            'form':{s:public_form(forms.get(s)) for s in ('home','away')},
            'roster':{s:public_roster(rosters.get(s)) for s in ('home','away')},
            'lineups':lineups,'odds':odds[:5],
            'events':events[:130],'signals':signals[:20],
            'outcomes':score_outcomes(safe(f.get('score'),12),f.get('phase'))}

def paper_summary(rows):
    signals=[s for r in rows for s in r['signals']]
    settled=[s for s in signals if s['status']=='settled' and s['paper_pl_u'] is not None]
    wins=sum(1 for s in settled if s['paper_pl_u']>0)
    groups={}
    for s in settled:
        group=groups.setdefault(s['market'],{'market':s['market'],'entries':0,'wins':0,'paper_pl_u':0.0})
        group['entries']+=1
        group['wins']+=s['paper_pl_u']>0
        group['paper_pl_u']+=s['paper_pl_u']
    for v in groups.values():v['paper_pl_u']=round(v['paper_pl_u'],3)
    return {'unit':'1u nominal por entrada BACK 1X2 (teste sem taxas)',
            'status':'with_settlements' if settled else 'insufficient_data',
            'settled':len(settled),'pending':len(signals)-len(settled),
            'won':wins,'paper_pl_u':round(sum(s['paper_pl_u'] for s in settled),3) if settled else None,
            'markets':list(groups.values())}

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
            if s['status']=='pending' and s['ev_pct']>5:
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

def main():
    today=datetime.now(BR).date()
    days={(today-timedelta(days=i)).isoformat() for i in range(3)}
    rows=[]
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
            item=public_row(row,local_day,fotmob_cache)
            if item:rows.append(item)
    rows=sort_games(merge_verified_duplicates(rows))
    # Conservar partidas de todos os dias; sem truncamento prematuro que exclua o historico.
    rows=rows[:1800]  # cobertura de todos os campeonatos na janela de 3 dias
    last=load(H/'status.json')
    backfill=load(H/'backfill_status.json')
    team_form=load(H/'team_form_status.json')
    external=load(H/'multi_source_status.json')
    fotmob=load(H/'fotmob_form_status.json')
    status={key:last.get(key) for key in ('day','updated_at','sources','live_found','thermometers_saved') if key in last}
    payload={'app':'NEXUS SCORE WEB','schema':2,'exported_at':datetime.now(timezone.utc).isoformat(),
             'collector':status,'backfill':{k:backfill.get(k) for k in ('days','games','with_stats','events','checked_at')},
             'team_form_status':{k:team_form.get(k) for k in ('checked_at','teams','games_with_form','complete_team_samples')},
             'source_status':{k:external.get(k) for k in ('updated_at','files_checked','cross_verified','stats_filled','added','historical_odds','providers')},
             'fotmob_form_status':{k:fotmob.get(k) for k in ('updated_at','teams_discovered','requests_succeeded','games_with_form','teams_with_10','roster_teams')},
             'notice':'Atualizacao periodica, sem odds em tempo real. EV experimental nao e recomendacao nem lucro realizado.',
             'paper':paper_summary(rows),'market_history':market_history(rows),
             'alerts':alerts_from(rows),'games':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(OUT)
    print('WEB EXPORT:',len(rows),'jogos,',len(payload['alerts']),'alertas de monitoramento,',
          payload['paper']['settled'],'operacoes paper; ZERO dados financeiros privados')
if __name__=='__main__':main()
