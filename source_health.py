"""NEXUS source/data quality diagnostics: observed fields only, no generated scouts.

The feed is periodic, not a real-time sportsbook API. This module exports
health/freshness metadata rather than assigning probabilities or EV.
"""
from datetime import datetime, timezone
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

def quality_report(games,collector,pregame,now_ts):
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
      'as_of':datetime.fromtimestamp(now_ts,timezone.utc).isoformat(),
      'collector_freshness':freshness(collector.get('updated_at'),now_ts,20),
      'odds_collector_freshness':freshness(pregame.get('updated_at'),now_ts,180),
      'live_games_in_feed':len(live),
      'live_fresh':len(fresh),
      'live_stale_or_unverified':len(live)-len(fresh),
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
