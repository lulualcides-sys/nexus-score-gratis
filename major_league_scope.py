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


WOMEN=re.compile(r"\b(?:women|womens|woman|female|feminino|feminina|femenino|femenina|feminin|feminine|ladies|frauen|femminile|wsl|nwsl|liga f|w league)\b")
REJECT=re.compile(r"\b(?:youth|juvenil|reserves|reservas|amateur|amador|friendly|amistoso|primavera|qualifier|qualifying|2 bundesliga|bundesliga 2|primera b|serie a2|liga expansion|sub ?(?:17|19|20|21|23)|u ?(?:17|19|20|21|23))\b")
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


def league_id(league):
    name=normalize(league)
    if not name or WOMEN.search(name) or REJECT.search(name):
        return None
    code=ESPN_CODES.get(str(league or "").strip().lower())
    if code:
        return code
    # "Brasileirao Serie B" must not be misread as "Brasileirao".
    if re.search(r"\bserie b\b",name) and re.search(r"\b(?:brasileirao|brasil|brasileiro|brazil|brazilian)\b",name):
        return "br_b"
    for key,pattern in COMPETITIONS:
        if re.search(pattern,name):
            return key
    return None


def major_men(row):
    if not isinstance(row,dict):
        return False
    gender=normalize(row.get("gender") or row.get("competition_gender"))
    if gender in ("female","women","womens","feminino","feminina","femenino","femenina"):
        return False
    if not league_id(row.get("league")):
        return False
    return not any(WOMEN.search(normalize(row.get(k))) for k in ("home","away","team"))
