import json,glob,math,os,sys,collections
H=sys.argv[1]
name2id={};games={}
days=sorted(glob.glob(os.path.join(H,'20??-??-??.json')))
eval_rows=[]
for p in days:
    for k,r in (json.load(open(p)).get('matches') or {}).items():
        f=r.get('fixture') or {}
        hi,ai=str(f.get('home_id') or ''),str(f.get('away_id') or '')
        if hi and ai:name2id.setdefault(f.get('home'),hi);name2id.setdefault(f.get('away'),ai)
        try:gh,ga=map(int,str(f.get('score','')).split('-'))
        except:continue
        ts=f.get('start_timestamp')
        if f.get('phase')!='finished' or not(hi and ai and ts):continue
        games[(ts,hi,ai)]=(gh,ga)
        b=r.get('pregame_baseline') or {}
        if (b.get('forecast') or {}).get('one_x_two'):
            eval_rows.append(dict(ts=ts,h=hi,a=ai,gh=gh,ga=ga,nx=b['forecast']['one_x_two'],odds=(b.get('odds') or {}).get('prices')))
t=json.load(open(os.path.join(H,'fotmob_team_cache.json'))).get('teams') or {}
for tid,v in t.items():
    for g in v.get('games') or []:
        oid=name2id.get(g.get('opponent'));ts=g.get('ts')
        if not oid or not ts or g.get('gf') is None:continue
        if g.get('venue')=='Casa':games.setdefault((ts,tid,oid),(g['gf'],g['ga']))
        elif g.get('venue')=='Fora':games.setdefault((ts,oid,tid),(g['ga'],g['gf']))
seq=sorted(games.items())
print('jogos para o Elo',len(seq),'times',len({x for (_,h,a) in games for x in(h,a)}))
def run(K,HA,dk):
    R=collections.defaultdict(lambda:1500.0);pre={}
    for (ts,h,a),(gh,ga) in seq:
        pre[(ts,h,a)]=(R[h],R[a])
        e=1/(1+10**((R[a]-R[h]-HA)/400));s=1 if gh>ga else 0.5 if gh==ga else 0
        m=math.log(abs(gh-ga)+1)+1 if gh!=ga else 1
        d=K*m*(s-e);R[h]+=d;R[a]-=d
    return pre
def probs(rh,ra,HA,dk):
    # empate por largura dk em torno da expectativa (modelo ordinal simples)
    x=(rh+HA-ra)/400
    ph=1/(1+10**(-(x-dk)));pa=1/(1+10**(x+dk));pd=max(0.02,1-ph-pa)
    s=ph+pd+pa;return {'home':ph/s,'draw':pd/s,'away':pa/s}
er=sorted(eval_rows,key=lambda r:r['ts']);cut=int(len(er)*0.6);tr,te=er[:cut],er[cut:]
res=lambda r:'home' if r['gh']>r['ga'] else 'away' if r['ga']>r['gh'] else 'draw'
B=lambda p,r:sum((p[x]-(x==res(r)))**2 for x in p)
def score(rows,K,HA,dk,w):
    pre=run(K,HA,dk);tot=0;n=0
    for r in rows:
        if (r['ts'],r['h'],r['a']) not in pre:continue
        e=probs(*pre[(r['ts'],r['h'],r['a'])],HA,dk);nx={k:v/100 for k,v in r['nx'].items()}
        p={k:w*e[k]+(1-w)*nx[k] for k in e};tot+=B(p,r);n+=1
    return tot/max(n,1),n
best=min(((K,HA,dk,w) for K in(10,20,30,45) for HA in(40,65,90) for dk in(0.10,0.15,0.20) for w in(0,0.5,0.75,1)),key=lambda g:score(tr,*g)[0])
print('melhor no treino K=%s casa=%s empate=%s peso_elo=%s'%best)
print('TESTE atual  Brier %.4f (n=%d)'%score(te,best[0],best[1],best[2],0))
print('TESTE novo   Brier %.4f (n=%d)'%score(te,*best))
pre=run(*best[:3]);pr=[r for r in te if r['odds'] and len(r['odds'])==3 and (r['ts'],r['h'],r['a']) in pre]
def mk(r):
    i={k:1/v for k,v in r['odds'].items()};t=sum(i.values());return{k:v/t for k,v in i.items()}
for nm,f in(('atual',lambda r:{k:v/100 for k,v in r['nx'].items()}),('novo',lambda r:{k:best[3]*probs(*pre[(r['ts'],r['h'],r['a'])],best[1],best[2])[k]+(1-best[3])*r['nx'][k]/100 for k in('home','draw','away')}),('mercado',mk)):
    print('com odd (n=%d) %-8s Brier %.4f'%(len(pr),nm,sum(B(f(r),r) for r in pr)/max(len(pr),1)))
