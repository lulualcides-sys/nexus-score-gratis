import json,glob,math,os,sys,collections,difflib,unicodedata,re
H,OF=sys.argv[1],sys.argv[2]
FM={'47':'en.1','48':'en.2','108':'en.3','109':'en.4','54':'de.1','146':'de.2','87':'es.1','140':'es.2','55':'it.1','86':'it.2','53':'fr.1','110':'fr.2','57':'nl.1','61':'pt.1','40':'be.1','71':'tr.1','230':'mx.1'}
STOP={'fc','cf','afc','sc','ac','as','ss','ssc','us','club','de','sv','vfb','vfl','tsg','rc','rcd','ud','cd','sd','fk','sk','bk','if','ogc','losc','stade','real','athletic','calcio','1','04','05','09','1899','1846','1910'}
def norm(s):
    s=unicodedata.normalize('NFKD',str(s));s=''.join(c for c in s if not unicodedata.combining(c)).lower()
    return ' '.join(w for w in re.findall(r'[a-z0-9]+',s) if w not in STOP)
# OpenFootball games per league code
ofg=collections.defaultdict(list);ofnames=collections.defaultdict(set)
for p in sorted(glob.glob(os.path.join(OF,'*.json'))):
    code=re.search(r'([a-z]{2}\.\d)\.json$',p).group(1)
    for m in json.load(open(p)).get('matches') or []:
        sc=m.get('score');ft=sc.get('ft') if isinstance(sc,dict) else sc if isinstance(sc,list) else None
        if not ft or len(ft)!=2 or m.get('date') is None:continue
        ofg[code].append((m['date'],m['team1'],m['team2'],ft[0],ft[1]));ofnames[code].update((m['team1'],m['team2']))
# FotMob teams per league
fmteam=collections.defaultdict(dict);games={};eval_rows=[]
for p in sorted(glob.glob(os.path.join(H,'20??-??-??.json'))):
    for k,r in (json.load(open(p)).get('matches') or {}).items():
        f=r.get('fixture') or {};lid=str(f.get('league_id') or '') if f.get('league_id_verified') else ''
        hi,ai=str(f.get('home_id') or ''),str(f.get('away_id') or '')
        if lid in FM and hi and ai:fmteam[FM[lid]][hi]=f.get('home');fmteam[FM[lid]][ai]=f.get('away')
        try:gh,ga=map(int,str(f.get('score','')).split('-'))
        except:continue
        ts=f.get('start_timestamp')
        if f.get('phase')!='finished' or not(hi and ai and ts):continue
        games[(ts,hi,ai)]=(gh,ga)
        b=r.get('pregame_baseline') or {}
        if (b.get('forecast') or {}).get('one_x_two'):
            eval_rows.append(dict(ts=ts,h=hi,a=ai,gh=gh,ga=ga,lid=lid,nx=b['forecast']['one_x_two'],odds=(b.get('odds') or {}).get('prices')))
# map names
link={};total=ok=0
for code,teams in fmteam.items():
    cand={norm(n):n for n in ofnames.get(code,())}
    for tid,name in teams.items():
        total+=1;nn=norm(name)
        best=difflib.get_close_matches(nn,list(cand),n=1,cutoff=0.72)
        if not best:
            sub=[c for c in cand if nn and (nn in c or c in nn)]
            best=sub[:1] if len(sub)==1 else []
        if best:link[(code,cand[best[0]])]=tid;ok+=1
print('times FotMob das ligas cobertas',total,'ligados',ok)
import datetime as dt
first=min(ts for ts,_,_ in games)
for code,lst in ofg.items():
    for d,t1,t2,g1,g2 in lst:
        a,b=link.get((code,t1)),link.get((code,t2))
        if not a or not b:continue
        ts=int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())+43200
        if ts<first-86400:games.setdefault((ts,a,b),(g1,g2))
t=json.load(open(os.path.join(H,'fotmob_team_cache.json'))).get('teams') or {}
name2id={}
for p in sorted(glob.glob(os.path.join(H,'20??-??-??.json'))):
    for r in (json.load(open(p)).get('matches') or {}).values():
        f=r.get('fixture') or {}
        for side in('home','away'):
            if f.get(side+'_id'):name2id.setdefault(f.get(side),str(f[side+'_id']))
for tid,v in t.items():
    for g in v.get('games') or []:
        oid=name2id.get(g.get('opponent'));ts=g.get('ts')
        if not oid or not ts or g.get('gf') is None:continue
        if g.get('venue')=='Casa':games.setdefault((ts,tid,oid),(g['gf'],g['ga']))
        elif g.get('venue')=='Fora':games.setdefault((ts,oid,tid),(g['ga'],g['gf']))
seq=sorted(games.items());print('jogos no Elo',len(seq),'(desde %s)'%dt.datetime.fromtimestamp(seq[0][0][0],dt.timezone.utc).date())
def run(K,HA):
    R=collections.defaultdict(lambda:1500.0);N=collections.Counter();pre={}
    for (ts,h,a),(gh,ga) in seq:
        pre[(ts,h,a)]=(R[h],R[a],min(N[h],N[a]));N[h]+=1;N[a]+=1;e=1/(1+10**((R[a]-R[h]-HA)/400));s=1 if gh>ga else .5 if gh==ga else 0
        d=K*(math.log(abs(gh-ga)+1)+1 if gh!=ga else 1)*(s-e);R[h]+=d;R[a]-=d
    return pre
def probs(rh,ra,HA,dk):
    x=(rh+HA-ra)/400;ph=1/(1+10**(-(x-dk)));pa=1/(1+10**(x+dk));pd=max(.02,1-ph-pa);s=ph+pd+pa
    return {'home':ph/s,'draw':pd/s,'away':pa/s}
res=lambda r:'home' if r['gh']>r['ga'] else 'away' if r['ga']>r['gh'] else 'draw'
B=lambda p,r:sum((p[x]-(x==res(r)))**2 for x in p)
er=sorted(eval_rows,key=lambda r:r['ts']);cut=int(len(er)*.6);tr,te=er[:cut],er[cut:]
cache={}
def pred(r,K,HA,dk,w):
    if (K,HA) not in cache:cache[(K,HA)]=run(K,HA)
    pre=cache[(K,HA)];rh,ra,n=pre[(r['ts'],r['h'],r['a'])];e=probs(rh,ra,HA,dk);nx={k:v/100 for k,v in r['nx'].items()}
    if n<MIN:w=0
    return {k:w*e[k]+(1-w)*nx[k] for k in e}
def score(rows,*g):return sum(B(pred(r,*g),r) for r in rows)/len(rows)
MIN=int(os.environ.get('MIN','15'))
mature=lambda r:cache[(15,50)][(r['ts'],r['h'],r['a'])][2]>=MIN if (15,50) in cache else False
grid=[(K,HA,dk,w) for K in(15,25,35,45) for HA in(50,65,80) for dk in(.15,.2,.25) for w in(0,.5,.75,1)]
best=min(grid,key=lambda g:score(tr,*g));print('melhor treino K=%s casa=%s empate=%s peso=%s'%best)
score(tr,15,50,.15,0)
cov=lambda r:cache[(15,50)][(r['ts'],r['h'],r['a'])][2]>=MIN
for nome,rows in(('todos',te),('times com >=MIN jogos',[r for r in te if cov(r)])):
    print('TESTE %-26s n=%4d atual %.4f  novo %.4f'%(nome,len(rows),score(rows,*best[:3],0),score(rows,*best)))
pr=[r for r in te if r['odds'] and len(r['odds'])==3]
def mk(r):
    i={k:1/v for k,v in r['odds'].items()};t=sum(i.values());return {k:v/t for k,v in i.items()}
for nome,rows in(('com odd',pr),('com odd + >=MIN jogos',[r for r in pr if cov(r)])):
    print('%-26s n=%3d atual %.4f novo %.4f mercado %.4f'%(nome,len(rows),score(rows,*best[:3],0),score(rows,*best),sum(B(mk(r),r) for r in rows)/len(rows)))
