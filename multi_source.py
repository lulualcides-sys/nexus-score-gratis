#!/usr/bin/env python3
"""NEXUS multi-fonte: Football-Data CSV + OpenLigaDB; ESPN/FotMob no coletor principal.

Nunca confunde odds de fechamento historico com odds de entrada. Dados conflitantes
nao sobrescrevem as fontes anteriores. Sem dependencias pagas.
"""
import csv
import io
import json
import os
import re
import unicodedata
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import Request,urlopen

from coletar import HISTORY, DAY, NOW, fetch, read, write, utc_ts

LEAGUES={
 'E0':('eng.1','Europe/London'),'E1':('eng.2','Europe/London'),
 'SP1':('esp.1','Europe/Madrid'),'I1':('ita.1','Europe/Rome'),
 'D1':('ger.1','Europe/Berlin'),'F1':('fra.1','Europe/Paris'),
 'N1':('ned.1','Europe/Amsterdam'),'P1':('por.1','Europe/Lisbon'),
 'B1':('bel.1','Europe/Brussels'),'SC0':('sco.1','Europe/London')
}
STAT_COLUMNS={'HS':('home','shots_total'),'AS':('away','shots_total'),
 'HST':('home','shots_on'),'AST':('away','shots_on'),
 'HC':('home','corners'),'AC':('away','corners'),
 'HF':('home','fouls'),'AF':('away','fouls'),
 'HY':('home','yellow_cards'),'AY':('away','yellow_cards'),
 'HR':('home','red_cards'),'AR':('away','red_cards')}
CLUB_ALIASES={'man united':'manchester united','man city':'manchester city',
 'nottm forest':'nottingham forest','spurs':'tottenham hotspur',
 'wolves':'wolverhampton wanderers','ath bilbao':'athletic club',
 'ath madrid':'atletico madrid','inter':'internazionale',
 'inter milan':'internazionale','ac milan':'milan','paris sg':'paris saint germain',
 'psg':'paris saint germain','bayern munich':'bayern munchen',
 'bayern münchen':'bayern munchen','dortmund':'borussia dortmund',
 'leverkusen':'bayer leverkusen','m gladbach':'borussia monchengladbach',
 'rb leipzig':'rasenballsport leipzig','rb salzburg':'red bull salzburg',
 'fc koln':'koln','cologne':'koln'}
def norm(value):
    x=unicodedata.normalize('NFKD',str(value or '').casefold())
    x=''.join(c for c in x if not unicodedata.combining(c))
    x=re.sub(r'[^a-z0-9]+',' ',x).strip()
    x=re.sub(r'^(?:afc|fc|cf|sc)\s+','',x)
    x=re.sub(r'\s+(?:fc|cf|sc)$','',x)
    return CLUB_ALIASES.get(x,x)

def num(value):
    try:
        n=float(value)
        return n if n==n and 0<=n<=10000 else None
    except (TypeError,ValueError):return None

def row_date(value):
    for fmt in ('%d/%m/%Y','%d/%m/%y','%d.%m.%Y','%Y-%m-%d'):
        try:return datetime.strptime(str(value or '').strip(),fmt).date()
        except ValueError:pass
    return None

def football_data_fixture(raw,league,zone):
    day=row_date(raw.get('Date'))
    home=raw.get('HomeTeam') or ''
    away=raw.get('AwayTeam') or ''
    hg=num(raw.get('FTHG'));ag=num(raw.get('FTAG'))
    if not day or not home or not away or hg is None or ag is None or not hg.is_integer() or not ag.is_integer():return None
    t=str(raw.get('Time') or '').strip()
    try:
        hh,mm=map(int,t.split(':')[:2])
        dt=datetime(day.year,day.month,day.day,hh,mm,tzinfo=ZoneInfo(zone))
        timestamp=int(dt.timestamp())
    except (TypeError,ValueError):timestamp=None
    return {'id':'fd-'+league+'-'+day.isoformat()+'-'+norm(home).replace(' ','-')+'-'+norm(away).replace(' ','-'),
       'home':str(home)[:105],'away':str(away)[:105],'league':league,
       'league_code':league,'phase':'finished','score':str(int(hg))+'-'+str(int(ag)),
       'start_timestamp':timestamp,'minute':0,'source':'Football-Data.co.uk',
       'collected_at':NOW.isoformat(),'home_logo':'','away_logo':''}

def football_data_csv(code):
    year=datetime.fromisoformat(DAY).year
    season=str(year%100).zfill(2)+str((year+1)%100).zfill(2)
    # Out-Dez = temporada corrente, Jan-Jun = temporada anterior.
    if int(DAY[5:7])<=6:season=str((year-1)%100).zfill(2)+str(year%100).zfill(2)
    url='https://www.football-data.co.uk/mmz4281/'+season+'/'+code+'.csv'
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 NEXUS analytics (public snapshots)',
                             'Accept':'text/csv,text/plain,*/*'})
    with urlopen(req,timeout=8) as r:raw=r.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('CSV excede 2 MB')
    text=raw.decode('utf-8-sig',errors='replace')
    if 'Date' not in text[:450] or 'HomeTeam' not in text[:450]:raise ValueError('CSV sem colunas de partidas')
    return list(csv.DictReader(io.StringIO(text)))

def different_games(a,b):
    return norm(a.get('home'))!=norm(b.get('home')) or norm(a.get('away'))!=norm(b.get('away'))

def merge_football_data(day,code,raw,doc,status):
    lg,zone=LEAGUES[code]
    candidate=football_data_fixture(raw,lg,zone)
    if not candidate or row_date(raw.get('Date')).isoformat()!=day:return
    matches=doc.setdefault('matches',{})
    existing=None
    for row in matches.values():
        f=row.get('fixture') or {}
        if f.get('league_code',f.get('league'))!=lg or different_games(f,candidate):
            continue
        # NUNCA enxertar stats de FT em partidas de outro dia ou ainda ao vivo.
        if f.get('phase')!='finished' or f.get('score') in (None,'?-?'):
            continue
        try:
            current=datetime.fromtimestamp(int(f['start_timestamp']),ZoneInfo(zone))
            incoming=datetime.fromtimestamp(int(candidate['start_timestamp']),ZoneInfo(zone))
        except (ValueError,TypeError,KeyError,OSError,OverflowError):
            continue
        if current.date()!=incoming.date() or abs((current-incoming).total_seconds())>6*3600:
            continue
        existing=row;break
    if existing is None:
        existing=matches.setdefault(candidate['id'],{})
        existing['fixture']=candidate
        status['added']+=1
    else:
        before=existing['fixture']
        if before.get('phase')=='finished' and str(before.get('score'))!=candidate['score']:
            status['conflicts']+=1
            return
        if not before.get('start_timestamp') and candidate.get('start_timestamp'):
            before['start_timestamp']=candidate['start_timestamp']
        status['cross_verified']+=1
    stats=existing.setdefault('stats',{'home':{},'away':{}})
    sources=existing.setdefault('stat_sources',{})
    used=0
    for key,(side,field) in STAT_COLUMNS.items():
        n=num(raw.get(key))
        if n is None:continue
        target=stats.setdefault(side,{})
        if field not in target:
            target[field]=n
            sources[side+'.'+field]='Football-Data.co.uk'
            used+=1
    if used:status['stats_filled']+=used
    # Fecha odds apenas historicas e NUNCA mistura com odds_quotes pre-jogo.
    odds=existing.setdefault('closing_odds',[])
    if not odds:
        for prefix,name in (('B365','Bet365'),('PS','Pinnacle'),('Avg','Media mercado')):
            for column,selection in (('H','home'),('D','draw'),('A','away')):
                odd=num(raw.get(prefix+column))
                if odd is not None and 1.01<=odd<=1000:
                    odds.append({'market':'1x2','sel':selection,'odd':round(odd,3),
                      'source':'Football-Data.co.uk','bookmaker':name,'type':'historical_closing'})
        if odds:status['historical_odds']+=len(odds)
    sources=existing.setdefault('sources',[])
    if 'Football-Data.co.uk' not in sources:sources.append('Football-Data.co.uk')

def openliga_events(season):
    url='https://api.openligadb.de/getmatchdata/bl1/'+str(season)
    req=Request(url,headers={'Accept':'application/json','User-Agent':'NEXUS/5.31'})
    with urlopen(req,timeout=8) as resp:buf=resp.read(2_000_001)
    if len(buf)>2_000_000:raise ValueError('OpenLigaDB JSON acima de 2 MB')
    events=json.loads(buf)
    if not isinstance(events,list):raise ValueError('JSON OpenLigaDB incorreto')
    return events

def openliga_fixture(event):
    if not isinstance(event,dict):return None
    h=event.get('team1') or {};a=event.get('team2') or {}
    ts=utc_ts(event.get('matchDateTimeUTC')) or utc_ts(event.get('matchDateTime'))
    if not h.get('teamName') or not a.get('teamName') or not ts:return None
    final=next((r for r in event.get('matchResults') or [] if r.get('resultTypeID')==2),None)
    finished=bool(event.get('matchIsFinished'))
    score='?-?'
    if finished and final:
        hscore=num(final.get('pointsTeam1'));ascore=num(final.get('pointsTeam2'))
        if hscore is not None and ascore is not None and hscore.is_integer() and ascore.is_integer():
            score=str(int(hscore))+'-'+str(int(ascore))
    return {'id':'openliga-'+str(event.get('matchID') or ''),'home':str(h['teamName'])[:105],
      'away':str(a['teamName'])[:105],'league':'Bundesliga','league_code':'ger.1',
      'phase':'finished' if finished and score!='?-?' else 'scheduled',
      'score':score,'start_timestamp':ts,'source':'OpenLigaDB','collected_at':NOW.isoformat(),
      'minute':0,'home_logo':'','away_logo':'',
      'round':str((event.get('group') or {}).get('groupName') or '')[:70]}

def merge_openliga(day,event,doc,status):
    f=openliga_fixture(event)
    if not f or datetime.fromtimestamp(f['start_timestamp'],timezone(timedelta(hours=-3))).date().isoformat()!=day:
        return
    matches=doc.setdefault('matches',{})
    found=None
    for row in matches.values():
        old=row.get('fixture') or {}
        if old.get('league_code',old.get('league'))!='ger.1':continue
        old_ts=old.get('start_timestamp')
        if old_ts and abs(int(old_ts)-f['start_timestamp'])>180*60:continue
        if not different_games(old,f):found=row;break
    if found is None:
        # Nao criar duplicidade em Bundesliga se outra fonte tem jogos na mesma hora com nomenclatura divergente.
        conflicts=[r for r in matches.values() if (r.get('fixture') or {}).get('league_code')=='ger.1' and
            abs(int((r.get('fixture') or {}).get('start_timestamp') or 0)-f['start_timestamp'])<=15*60]
        if conflicts:
            status['unmatched']+=1
            return
        matches[f['id']]={'fixture':f,'sources':['OpenLigaDB']}
        status['added']+=1
    else:
        old=found['fixture']
        if old.get('phase')=='finished' and f['phase']=='finished' and old.get('score')!=f['score']:
            status['conflicts']+=1
            return
        found.setdefault('sources',[])
        if 'OpenLigaDB' not in found['sources']:found['sources'].append('OpenLigaDB')
        status['cross_verified']+=1

def main():
    now=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(now-timedelta(days=i)).isoformat() for i in range(3)]
    docs={d:read(HISTORY/(d+'.json')) for d in days}
    live_status=read(HISTORY/'status.json')
    fotmob_ok='FotMob' in (live_status.get('sources') or [])
    report={'updated_at':NOW.isoformat(),'days':days,
       'providers':{'ESPN':'retrospectivo (3 dias)',
                    'FotMob':'ativo' if fotmob_ok else 'indisponivel nesta coleta',
                    'Football-Data.co.uk':'desativado: permissao especifica nao configurada',
                    'OpenLigaDB':'consultando Bundesliga'},
       'files_checked':0,'added':0,'cross_verified':0,'stats_filled':0,
       'historical_odds':0,'conflicts':0,'unmatched':0,'errors':[]}
    # Football-Data.co.uk restringe automacao comercial/treinamento.
    # Padrao seguro: NAO consultar. Apenas habilitar com autorizacao apropriada.
    if os.environ.get('NEXUS_FOOTBALL_DATA_LICENSED')=='1':
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending={pool.submit(football_data_csv,code):code for code in LEAGUES}
            for future in as_completed(pending):
                code=pending[future]
                try:
                    matches=future.result();report['files_checked']+=1
                    for raw in matches:
                        day=row_date(raw.get('Date'))
                        if day and day.isoformat() in docs:
                            merge_football_data(day.isoformat(),code,raw,docs[day.isoformat()],report)
                except Exception as ex:
                    if len(report['errors'])<12:report['errors'].append('Football-Data '+code+': '+str(ex)[:130])
        report['providers']['Football-Data.co.uk']='consultado: '+str(report['files_checked'])+' arquivos'
    try:
        for event in openliga_events(now.year if now.month>=7 else now.year-1):
            f=openliga_fixture(event)
            if f:
                day=datetime.fromtimestamp(f['start_timestamp'],timezone(timedelta(hours=-3))).date().isoformat()
                if day in docs:merge_openliga(day,event,docs[day],report)
        report['providers']['OpenLigaDB']='consultado'
    except Exception as ex:
        report['providers']['OpenLigaDB']='indisponivel'
        report['errors'].append('OpenLigaDB: '+str(ex)[:130])
    for day,doc in docs.items():
        if doc:write(HISTORY/(day+'.json'),doc)
    write(HISTORY/'multi_source_status.json',report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
