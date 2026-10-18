"""Leaders de elenco com evidência de tabela completa de atletas.
Não confundir top 3 da liga com artilheiro de um clube.
"""
from datetime import datetime, timezone

def team_player_leaders(doc, team_id):
    stats=doc.get('stats') or {}
    if not isinstance(stats,dict):return {}
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
