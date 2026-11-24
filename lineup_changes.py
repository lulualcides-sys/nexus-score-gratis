#!/usr/bin/env python3
"""Aviso de escalação: titulares habituais ausentes do XI de um jogo.

Habitual = titular em >= 80% dos últimos jogos anteriores do mesmo time
(mínimo de 4 jogos com escalação real). Usa só escalações publicadas pela
fonte; sem XI no jogo, não há aviso. Não infere motivo (lesão, poupado etc.).
"""
HABITUAL_SHARE = 0.8  # 60% marcava 3+ ausentes em 47% dos times (rodízio normal); 80% -> 9%
MIN_PRIOR = 4
MAX_PRIOR = 6


def _starters(lineup):
    if not isinstance(lineup, dict):
        return None
    out = {}
    for p in lineup.get("starters") or []:
        if isinstance(p, dict) and str(p.get("id") or "").strip():
            out[str(p["id"])] = str(p.get("name") or "")[:60]
    return out if len(out) >= 9 else None


def build(docs):
    """docs: {dia: {'matches': {id: row}}} -> {id_do_jogo: {'home'|'away': relatório}}."""
    by_team = {}
    entries = []
    for doc in docs.values():
        for gid, row in ((doc or {}).get("matches") or {}).items():
            if not isinstance(row, dict):
                continue
            f = row.get("fixture") or {}
            try:
                ts = int(f.get("start_timestamp") or 0)
            except (TypeError, ValueError):
                continue
            for side in ("home", "away"):
                team = str(f.get(side + "_id") or "")
                xi = _starters((row.get("lineups") or {}).get(side))
                if not team or not ts:
                    continue
                entries.append((gid, side, team, ts, xi, f.get(side) or ""))
                if xi:
                    by_team.setdefault(team, {})[gid] = (ts, xi)
    report = {}
    for gid, side, team, ts, xi, name in entries:
        if not xi:
            continue
        prior = sorted((v for k, v in by_team.get(team, {}).items() if k != gid and v[0] < ts),
                       key=lambda v: v[0], reverse=True)[:MAX_PRIOR]
        if len(prior) < MIN_PRIOR:
            continue
        counts, names = {}, {}
        for _, starters in prior:
            for pid, pname in starters.items():
                counts[pid] = counts.get(pid, 0) + 1
                names.setdefault(pid, pname)
        habitual = {pid for pid, c in counts.items() if c / len(prior) >= HABITUAL_SHARE}
        missing = sorted(habitual - set(xi), key=lambda pid: (-counts[pid], names[pid]))
        report.setdefault(gid, {})[side] = {
            "team": str(name)[:80], "prior_games": len(prior),
            "habitual": len(habitual), "missing": [names[p] for p in missing][:8],
            "missing_count": len(missing)}
    return report
