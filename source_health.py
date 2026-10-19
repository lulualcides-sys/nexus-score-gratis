"""NEXUS source/data quality diagnostics: observed fields only, no generated scouts.

The feed is periodic, not a real-time sportsbook API. This module exports
health/freshness metadata rather than assigning probabilities or EV.
"""
from datetime import datetime, timezone, timedelta
from oddspapi_odds import MONTHLY_BUDGET, SLOTS_UTC
import math

def timestamp(value):
    if not isinstance(value,str) or not value:return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt.timestamp() if dt.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def freshness(value,now_ts,max_minutes):
    t=timestamp(value)
    if t is None:return 'unknown'
    age=(now_ts-t)/60
    if age < -2:return 'invalid_future'
    return 'fresh' if age<=max_minutes else 'stale'

def _observed_scouts(game):
    stats=game.get('stats') or {}
    if not isinstance(stats,dict):return False
    valid=('shots_on','shots_total','corners','big_chances','xg','possession')
    for side in ('home','away'):
        values=stats.get(side) or {}
        if not isinstance(values,dict):continue
        for key in valid:
            v=values.get(key)
            if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0:
                return True
    return False

def live_league_quality(fresh_games,now_ts,limit=16):
    """Cobertura por liga somente sobre partidas AO VIVO com horario recente."""
    groups={}
    for g in fresh_games:
        league=str(g.get('league') or 'Campeonato não informado').strip()[:85]
        entry=groups.setdefault(league,{'league':league,'fresh_live_games':0,
               'with_recent_scouts':0,'with_recent_pressure':0})
        entry['fresh_live_games']+=1
        if (_observed_scouts(g) and
            freshness(g.get('stats_observed_at'),now_ts,20)=='fresh'):
            entry['with_recent_scouts']+=1
        if (isinstance(g.get('pressure'),list) and g['pressure'] and
            freshness(g.get('pressure_observed_at'),now_ts,20)=='fresh'):
            entry['with_recent_pressure']+=1
    results=[]
    for item in groups.values():
        n=item['fresh_live_games']
        results.append({**item,
                        'scouts_coverage_pct':round(100*item['with_recent_scouts']/n,1),
                        'pressure_coverage_pct':round(100*item['with_recent_pressure']/n,1)})
    results.sort(key=lambda x:(-x['fresh_live_games'],-x['with_recent_pressure'],x['league']))
    return results[:limit]


def odds_budget_health(now_ts,ledger=None,historical=None):
    """Resumo PUBLICO do limite autoimposto, sem IDs, chaves ou URLs."""
    ledger=ledger if isinstance(ledger,dict) else {}
    historical=historical if isinstance(historical,dict) else {}
    date=datetime.fromtimestamp(now_ts,timezone.utc)
    month=date.strftime('%Y-%m')
    recorded=ledger.get('month')==month
    try:
        consumed=int(ledger.get('requests') or 0) if recorded else 0
    except (TypeError,ValueError,OverflowError):consumed=0
    consumed=max(0,min(consumed,MONTHLY_BUDGET))
    next_slot=None
    for offset in (0,1):
        day=date+timedelta(days=offset)
        for hour in SLOTS_UTC:
            candidate=day.replace(hour=hour,minute=0,second=0,microsecond=0)
            if candidate>date:
                next_slot=candidate.isoformat()
                break
        if next_slot:break
    attempts=historical.get('attempts') or {}
    if not isinstance(attempts,dict):attempts={}
    successful=sum(bool(v.get('result')=='collected') for v in attempts.values() if isinstance(v,dict))
    return {'status':'recorded' if recorded else 'no_monthly_record',
            'monthly_limit_conservative':MONTHLY_BUDGET,
            'used_this_month':consumed if recorded else None,
            'remaining_this_month':MONTHLY_BUDGET-consumed if recorded else None,
            'next_collection_window_utc':next_slot,
            'historical_attempts':len(attempts),
            'historical_collected':successful,
            'historical_status':'recorded' if attempts else 'not_yet_recorded',
            'note':'Limite conservador da automacao, nao saldo oficial do provedor. Sem extrair chave, IDs ou preco ficticio.'}


def quality_report(games,collector,pregame,now_ts,odds_usage=None,historical_status=None):
    """Describe coverage denominators and provider problems explicitly."""
    games=games if isinstance(games,list) else []
    collector=collector if isinstance(collector,dict) else {}
    pregame=pregame if isinstance(pregame,dict) else {}
    live=[g for g in games if isinstance(g,dict) and g.get('phase')=='live']
    fresh=[g for g in live if freshness(g.get('observed_at'),now_ts,20)=='fresh']
    scouts=[g for g in fresh if _observed_scouts(g)]
    recent_scouts=[g for g in scouts if freshness(g.get('stats_observed_at'),now_ts,20)=='fresh']
    pressure=[g for g in fresh if isinstance(g.get('pressure'),list) and
              len(g['pressure'])>0 and freshness(g.get('pressure_observed_at'),now_ts,20)=='fresh']
    prematch=[g for g in games if isinstance(g,dict) and g.get('phase')=='scheduled']
    live_odds=sum(bool(g.get('live_odds_comparison')) for g in live)
    pre_odds=sum(bool(g.get('odds_comparison')) for g in prematch)
    details=collector.get('details_collected')
    try: details=int(details)
    except (TypeError,ValueError):details=0
    details=max(0,details)
    measured=collector.get('stats_detail_available')
    momentum=(collector.get('momentum_status_counts') or {}).get('observed') or 0
    try:measured=int(measured);momentum=int(momentum)
    except (TypeError,ValueError):measured=0;momentum=0
    measured=max(0,min(details,measured));momentum=max(0,min(details,momentum))
    ratio=lambda x,y:round(x*100/y,1) if y else None
    odds_papi=pregame.get('odds_papi') or {}
    espn=pregame.get('espn_fallback') or {}
    errors=[str(e)[:110] for e in (pregame.get('errors') or []) if isinstance(e,str)]
    return {
      'scope':'observed_data_quality_not_ev',
      'odds_budget_health':odds_budget_health(now_ts,odds_usage,historical_status),
      'as_of':datetime.fromtimestamp(now_ts,timezone.utc).isoformat(),
      'collector_freshness':freshness(collector.get('updated_at'),now_ts,20),
      'odds_collector_freshness':freshness(pregame.get('updated_at'),now_ts,180),
      'live_games_in_feed':len(live),
      'live_fresh':len(fresh),
      'live_stale_or_unverified':len(live)-len(fresh),
      'live_by_league':live_league_quality(fresh,now_ts),
      'fresh_live_with_any_scouts':len(scouts),
      'fresh_live_with_recent_scouts':len(recent_scouts),
      'fresh_live_with_recent_pressure':len(pressure),
      'scouts_pct_of_fresh_live':ratio(len(recent_scouts),len(fresh)),
      'pressure_pct_of_fresh_live':ratio(len(pressure),len(fresh)),
      'collector_details_queried':details,
      'collector_details_with_scouts':measured,
      'collector_scout_yield_pct':ratio(measured,details),
      'collector_details_with_pressure':momentum,
      'collector_pressure_yield_pct':ratio(momentum,details),
      'pregame_matches_with_price_comparison':pre_odds,
      'live_matches_with_price_comparison':live_odds,
      'providers':{
        'fotmob':{'status':'observed' if details else 'no_recent_details',
                  'observed_scouts':measured,'details_queried':details},
        'espn':{'status':'prices_observed' if (espn.get('quotes_added') or 0)>0 else 'no_recent_quotes',
                'quotes_added':max(0,int(espn.get('quotes_added') or 0))},
        'oddspapi':{'status':str(odds_papi.get('status') or 'not_configured')[:48],
                    'requests':max(0,int(odds_papi.get('requests') or 0)),
                    'quotes_added':max(0,int(odds_papi.get('quotes_added') or 0)),
                    'extra_markets_added':max(0,int(odds_papi.get('markets_added') or 0)),
                    'live_quotes_added':max(0,int(odds_papi.get('live_quotes_added') or 0))},
        'sofascore':{'status':'blocked_403' if any('SofaScore' in e and '403' in e for e in errors) else 'not_verified'}
      },
      'warnings':[
        *(['Coleta de scouts com mais de 20 minutos ou horario nao verificavel.']
          if freshness(collector.get('updated_at'),now_ts,20)!='fresh' else []),
        *(['Fonte SofaScore retornou HTTP 403; sem dados dessa fonte.']
          if any('SofaScore' in e and '403' in e for e in errors) else []),
        *(['Nenhuma odd ao vivo verificada no feed atual.'] if not live_odds else [])
      ],
      'note':'Amostras observadas e horarios por fonte. Jogo listado nao significa scouts completos, odds em tempo real, liquidez ou EV+.'
    }
