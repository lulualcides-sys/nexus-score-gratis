"""Detecta mudancas de cotações sem misturar casas/fontes/horarios."""
from collections import defaultdict
from datetime import datetime,timezone
import math

def movements(quotes,kickoff,now_ts,limit=2):
    if not isinstance(quotes,list) or now_ts>=kickoff:return []
    grouped=defaultdict(dict)
    for quote in quotes:
        if not isinstance(quote,dict) or quote.get('market')!='1x2':continue
        side=quote.get('selection')
        book=quote.get('bookmaker');source=quote.get('source')
        if side not in ('home','draw','away') or not book or not source:continue
        try:
            price=float(quote.get('odds'))
            instant=datetime.fromisoformat(str(quote.get('captured_at')).replace('Z','+00:00'))
            t=instant.timestamp()
        except (TypeError,ValueError,OverflowError):continue
        if (not math.isfinite(price) or not 1.01<price<1000 or
            t>=kickoff or t>now_ts+120 or now_ts-t>90*60):continue
        grouped[(str(book),str(source),side)][instant.isoformat()]={'price':price,'unix':t}
    results=[]
    for (book,source,side),snapshots in grouped.items():
        prices=sorted(snapshots.values(),key=lambda x:x['unix'])
        if len(prices)<2:continue
        prior,latest=prices[0],prices[-1]
        if latest['unix']-prior['unix']>90*60 or now_ts-latest['unix']>30*60:continue
        change=100*(latest['price']/prior['price']-1)
        if abs(change)<5:continue
        results.append({'market':'1x2','selection':side,
                        'bookmaker':book[:55],'source':source[:40],
                        'first_odd':round(prior['price'],3),'last_odd':round(latest['price'],3),
                        'change_pct':round(change,2),
                        'first_at':datetime.fromtimestamp(prior['unix'],timezone.utc).isoformat(),
                        'last_at':datetime.fromtimestamp(latest['unix'],timezone.utc).isoformat(),
                        'scope':'observed_pregame_quotes'})
    return sorted(results,key=lambda x:-abs(x['change_pct']))[:limit]
