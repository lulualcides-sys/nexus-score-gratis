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
