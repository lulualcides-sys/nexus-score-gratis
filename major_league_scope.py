#!/usr/bin/env python3
"""NEXUS curated major men's competition scope; presentation/research only.

Strictly filters visible 30-70 candidates and laboratory research.
Does not delete archived results or alter general collection.
"""
import re
import unicodedata


def normalize(value):
    value=unicodedata.normalize("NFD",str(value or ""))
    value="".join(c for c in value if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9]+"," ",value.lower()).strip()


WOMEN=re.compile(r"\b(?:women|womens|woman|female|feminino|feminina|femenino|femenina|femenil|vrouwen|feminin|feminine|ladies|frauen|femminile|wsl|nwsl|liga f|w league)\b")
REJECT=re.compile(r"\b(?:youth|juvenil|reserves|reservas|amateur|amador|friendly|amistoso|primavera|qualifier|qualifying|2 bundesliga|bundesliga 2|primera b|serie a2|liga expansion|liga portugal 2|premier league 2|u ?18|caf|sub ?(?:17|19|20|21|23)|u ?(?:17|19|20|21|23))\b")
COMPETITIONS=[
 ("br_b",r"\b(?:brasileirao serie b|campeonato brasileiro serie b|(?:brazil|brazilian|brasil|brasileiro) serie b|serie b do brasil)\b"),
 ("br_a",r"\b(?:brasileirao(?: serie a)?|campeonato brasileiro serie a|(?:brazil|brazilian|brasil|brasileiro) serie a)\b"),
 ("copa_br",r"\bcopa do brasil\b"),
 ("libertadores",r"\b(?:copa )?libertadores\b"),
 ("sudamericana",r"\b(?:copa )?(?:sudamericana|sul americana)\b"),
 ("champions",r"\b(?:uefa )?champions league\b"),
 ("premier",r"\b(?:english )?premier league\b"),
 ("championship",r"^(?:efl |english |england |sky bet |football league )?championship(?: england)?$|^english league championship$"),
 ("laliga",r"\b(?:la liga|laliga|primera division spain|spain primera division)\b"),
 ("italy",r"\b(?:serie a|serie a tim|italian serie a|italy serie a|serie a italy|serie a italiana)\b"),
 ("bundesliga",r"\b(?:german )?bundesliga\b"),
 ("ligue1",r"\bligue 1\b"),
 ("portugal",r"\b(?:primeira liga|liga portugal|portuguese primeira)\b"),
 ("eredivisie",r"\beredi(?:visie)?\b"),
 ("eerste",r"\b(?:eerste divisie|keuken kampioen divisie|dutch first division|netherlands first division)\b"),
 ("europa",r"\b(?:uefa )?europa league\b"),
 ("conference",r"\b(?:uefa )?(?:europa )?conference league\b"),
 ("argentina",r"\b(?:liga profesional|argentine primera|argentina primera division|superliga argentina|primera division argentina)\b"),
 ("mls",r"\b(?:mls|major league soccer)\b"),
 ("ligamx",r"\b(?:liga mx|mexican primera|mexico primera division)\b"),
 ("saudi",r"\b(?:saudi(?: arabia| arabian)? (?:pro|professional) league|roshn saudi league|saudi league|saudi pro league)\b"),
 ("worldcup",r"\b(?:fifa )?(?:world cup|copa do mundo)\b"),
]


ESPN_CODES={
    "bra.1":"br_a", "bra.2":"br_b", "eng.1":"premier",
    "eng.2":"championship", "ned.1":"eredivisie", "ned.2":"eerste",
    "ksa.1":"saudi", "uefa.europa.conf":"conference",
    "uefa.champions":"champions", "uefa.europa":"europa",
    "conmebol.libertadores":"libertadores",
    "conmebol.sudamericana":"sudamericana",
    "esp.1":"laliga", "ita.1":"italy", "ger.1":"bundesliga",
    "fra.1":"ligue1", "por.1":"portugal", "arg.1":"argentina",
    "usa.1":"mls", "mex.1":"ligamx", "fifa.world":"worldcup",
}


# IDs canônicos FotMob (primaryId), conferidos contra clubes reais do histórico.
# O nome é ambíguo ("Premier League" de Gana, Rússia, Ucrânia...); o ID não.
FOTMOB_IDS={
    "268":"br_a", "8814":"br_b", "9067":"copa_br", "45":"libertadores",
    "299":"sudamericana", "42":"champions", "47":"premier", "48":"championship",
    "87":"laliga", "55":"italy", "54":"bundesliga", "53":"ligue1", "61":"portugal",
    "57":"eredivisie", "111":"eerste", "73":"europa", "10216":"conference",
    "112":"argentina", "130":"mls", "230":"ligamx", "536":"saudi", "77":"worldcup",
}


# Escopo ampliado do site (mesmos IDs de web/nexus-league-coverage.js). Usado só
# para PRIORIZAR consultas; não entra no recorte de sinais/30-70 (major_men).
EXTENDED_FOTMOB_IDS=frozenset((
    "114", "9821", "10608", "140", "86", "146", "110", "108", "109", "8965",
    "71", "40", "64", "38", "69", "46", "59", "67", "135", "196", "63", "441",
    "138", "132", "274", "273", "161", "246", "131", "8972", "223", "9080", "525",
))


def catalog_rank(fotmob_id):
    """0 = liga principal, 1 = ampliada, 2 = demais (prioridade de coleta)."""
    canonical=_canonical(fotmob_id)
    if canonical in FOTMOB_IDS:
        return 0
    if canonical in EXTENDED_FOTMOB_IDS:
        return 1
    return 2


def _canonical(value):
    value=str(value if value is not None else "").strip()
    return value if value.isdecimal() and 0<int(value)<10_000_000 else ""


def league_id(league, fotmob_id=None):
    name=normalize(league)
    if not name or WOMEN.search(name):
        return None
    canonical=_canonical(fotmob_id)
    if canonical:
        # Com ID oficial, ele decide: liga homônima de outro país fica fora.
        return FOTMOB_IDS.get(canonical)
    if REJECT.search(name):
        return None
    code=ESPN_CODES.get(str(league or "").strip().lower())
    if code:
        return code
    raw=str(league or "").strip()
    # FotMob grafa o Brasileirão com acento; a italiana é "Serie A".
    if re.match(r"S[ée]rie B\b",raw) and (raw.startswith("Série") or re.search(r"\b(?:brasileirao|brasil|brasileiro|brazil|brazilian)\b",name)):
        return "br_b"
    # "Brasileirao Serie B" must not be misread as "Brasileirao".
    if re.search(r"\bserie b\b",name) and re.search(r"\b(?:brasileirao|brasil|brasileiro|brazil|brazilian)\b",name):
        return "br_b"
    if raw.startswith("Série A"):
        return "br_a"
    for key,pattern in COMPETITIONS:
        if re.search(pattern,name):
            return key
    return None


def attach_league_ids(items, fixtures_by_id):
    """Completa league_id de registros antigos a partir das partidas salvas.

    Não altera o arquivo original: devolve cópias só para o filtro público.
    """
    out=[]
    for item in items or []:
        if isinstance(item,dict) and not item.get("league_id"):
            fixture=fixtures_by_id.get(str(item.get("match_id") or "")) or {}
            found=_canonical(fixture.get("league_id"))
            if found:
                item={**item,"league_id":found}
        out.append(item)
    return out


def major_men(row):
    if not isinstance(row,dict):
        return False
    gender=normalize(row.get("gender") or row.get("competition_gender"))
    if gender in ("female","women","womens","feminino","feminina","femenino","femenina"):
        return False
    if not league_id(row.get("league"),row.get("league_id")):
        return False
    return not any(WOMEN.search(normalize(row.get(k))) for k in ("home","away","team"))
