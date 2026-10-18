"""Leaders de elenco com evidência de tabela completa de atletas.
Não confundir top 3 da liga com artilheiro de um clube.
"""
from datetime import datetime, timezone

def team_player_leaders(doc, team_id):
    stats=doc.get('stats') or {}
    if not isinstance(stats,dict):return {}
    # FotMob teams.stats.players: grupos nomeados com o primeiro participante
    # do próprio CLUBE, não o top 3 global de uma liga.
    groups=stats.get('players') or []
    if isinstance(groups,list):
        result={}
        for group in groups:
            if not isinstance(group,dict) or not group.get('header'):continue
            title=str(group.get('header') or '').casefold()
            kind=('assists' if 'assist' in title else
                  'rating' if 'rating' in title or 'nota' in title else
                  'goals' if 'scorer' in title or 'goal' in title else None)
            if not kind:continue
            first=group.get('participant') or {}
            if not isinstance(first,dict):continue
            if str(first.get('teamId') or '')!=str(team_id):continue
            value=first.get('value')
            if isinstance(value,dict):value=value.get('value')
            if value is None:value=(first.get('stat') or {}).get('value')
            try:stat=float(value)
            except (ValueError,TypeError):continue
            if not 0<=stat<=1000 or (kind=='rating' and stat>10):continue
            if not first.get('name'):continue
            result[kind]={'name':str(first['name'])[:80],'value':stat,
                'label':{'goals':'Artilheiro do time','assists':'Líder de assistências',
                         'rating':'Melhor nota do time'}[kind],
                'source':'FotMob · atletas da equipe'}
        if result:
            result['coverage_players']=None
            result['updated_at']=datetime.now(timezone.utc).isoformat()
            return result
    table=[]
    for key in ('players','playerStats','squadPlayerStats'):
        rows=stats.get(key) or []
        if isinstance(rows,dict):rows=rows.get('players') or rows.get('rows') or []
        if not isinstance(rows,list):continue
        for row in rows:
            if not isinstance(row,dict) or not row.get('name'):continue
            if 'topThree' in row or 'header' in row or 'participant' in row:continue
            if str(row.get('teamId') or team_id)!=str(team_id):continue
            def metric(name):
                v=row.get(name)
                if v is None and isinstance(row.get('stats'),dict):v=row['stats'].get(name)
                if isinstance(v,dict):v=v.get('value')
                try:
                    n=float(v)
                    return n if 0<=n<=1000 else None
                except (ValueError,TypeError):return None
            table.append({'name':str(row['name'])[:80],
                          'goals':metric('goals'),'assists':metric('assists'),
                          'rating':metric('rating')})
        if table:break
    if len(table)<4:return {}
    result={}
    for metric,title in (('goals','Artilheiro do clube'),('assists','Líder de assistências'),
                         ('rating','Maior nota registrada')):
        eligible=[p for p in table if p[metric] is not None]
        if len(eligible)<4:continue
        winner=max(eligible,key=lambda p:p[metric])
        if metric=='rating' and winner[metric]>10:continue
        result[metric]={'name':winner['name'],'value':winner[metric],
                        'label':title,'source':'FotMob · atletas da equipe'}
    if result:
        result['coverage_players']=len(table)
        result['updated_at']=datetime.now(timezone.utc).isoformat()
    return result
