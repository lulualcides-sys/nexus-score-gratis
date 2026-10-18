"""Cotações 1X2 auditáveis compartilhadas entre os coletores ESPN."""
import math
from datetime import datetime, timezone
from odds_capture import threeway

def new_quote(row,selection,value,bookmaker,source,when):
    if selection not in ('home','draw','away'):return False
    if not isinstance(value,(float,int)) or not math.isfinite(value) or not 1.01<=value<=1000:
        return False
    if not isinstance(bookmaker,str) or not bookmaker.strip():return False
    items=row.setdefault('odds_quotes',[])
    previous=[q for q in items if q.get('market')=='1x2' and
              q.get('selection')==selection and q.get('bookmaker')==bookmaker
              and q.get('source')==source]
    if previous and float(previous[-1].get('odds') or 0)==value:return False
    items.append({'market':'1x2','selection':selection,'odds':value,
                  'bookmaker':bookmaker[:55],'source':source,'captured_at':when})
    indices=[i for i,q in enumerate(items) if q.get('selection')==selection
        and q.get('market')=='1x2' and q.get('bookmaker')==bookmaker
        and q.get('source')==source]
    if len(indices)>6:
        for i in reversed(indices[1:-5]):items.pop(i)
    return True



def append_trio(row, prices, bookmaker, source, now_ts, source_ts=None):
    """Grava um pacote 1/X/2 atômico. Valores não alterados também compõem a foto.

    Rejeita pacotes parciais, apostas já iniciadas, odds falsas e
    captura onde cada seleção teria horário/casa diferente.
    """
    fixture = row.get('fixture') or {}
    try:
        kickoff = int(fixture.get('start_timestamp') or 0)
    except (TypeError, ValueError):
        return 0
    if fixture.get('phase') != 'scheduled' or not kickoff or now_ts >= kickoff:
        return 0
    if not isinstance(prices, dict) or set(prices) != {'home','draw','away'}:
        return 0
    if not isinstance(bookmaker, str) or not bookmaker.strip() or not isinstance(source, str) or not source.strip():
        return 0
    if not all(isinstance(prices[k], (float,int)) and not isinstance(prices[k],bool)
               and math.isfinite(prices[k]) and 1.01 < prices[k] < 1000
               for k in ('home','draw','away')):
        return 0
    offers = row.setdefault('odds_quotes',[])
    groups = {}
    for item in offers:
        if (item.get('market')!='1x2' or item.get('source')!=source or
                item.get('bookmaker')!=bookmaker):
            continue
        key=item.get('captured_at')
        if key:
            groups.setdefault(key,{})[item.get('selection')]=item.get('odds')
    last = sorted((when,group) for when,group in groups.items()
                  if set(group)=={'home','draw','away'})
    if last and all(float(last[-1][1][k])==float(prices[k])
                    for k in ('home','draw','away')):
        return 0
    measured=now_ts if source_ts is None else source_ts
    if (not isinstance(measured,(int,float)) or not math.isfinite(measured) or
            measured>now_ts+120 or measured>=kickoff or measured<=0):
        return 0
    when=datetime.fromtimestamp(measured,timezone.utc).isoformat()
    if last and last[-1][0]==when:
        return 0
    for selection in ('home','draw','away'):
        offers.append({'market':'1x2','selection':selection,
                       'odds':round(float(prices[selection]),4),
                       'bookmaker':bookmaker[:55],'source':source[:40],
                       'captured_at':when})
    return 3

def append_quote(row,selection,value,bookmaker,source,now_ts):
    f=row.get('fixture') or {}
    if f.get('phase')!='scheduled':return False
    try:
        if int(f.get('start_timestamp') or 0)<=now_ts:return False
    except (TypeError,ValueError):return False
    when=datetime.fromtimestamp(now_ts,timezone.utc).isoformat()
    return new_quote(row,selection,value,bookmaker,source,when)

def threeway_offers(offers):
    """Só mercados 1X2 completos do MESMO provedor e momento."""
    if isinstance(offers,dict):offers=[offers]
    if not isinstance(offers,list):return None
    for offer in offers:
        if not isinstance(offer,dict):continue
        prices=threeway(offer)
        if set(prices)!={'home','draw','away'}:continue
        provider=offer.get('provider') or {}
        bookmaker=(provider.get('name') if isinstance(provider,dict) else provider) or offer.get('providerName')
        bookmaker=str(bookmaker or 'Não informado').strip()[:55]
        return prices,bookmaker
    return None
