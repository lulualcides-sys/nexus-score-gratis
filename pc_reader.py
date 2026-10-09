#!/usr/bin/env python3
"""NEXUS PC: importa exportacoes CSV/JSON locais, sem instalar pacotes.

Somente o resumo agregado entra em history/pc_netpl.json no repositorio privado.
Nunca acessa o PC remotamente, le credenciais ou deduz unidades de stakes ausentes.
"""
import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "history" / "pc_netpl.json"
STATUS = ROOT / "history" / "pc_status.json"
MARKET = ("market", "marketname", "markettype", "mercado", "nomemercado", "tipo_mercado")
PROFIT = ("netpl", "netpnl", "netprofit", "plliquido", "lucroliquido",
          "lucroprejuizo", "pnl", "profitloss", "profit", "pl")
ALIASES = ("operations", "trades", "entries", "records", "bets", "operacoes", "apostas")

def norm(value):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(c for c in s if c.isalnum())

MARKET_KEYS = {norm(x) for x in MARKET}
PROFIT_KEYS = {norm(x) for x in PROFIT}

def choose(row, names):
    if not isinstance(row, dict):
        return None
    for key, val in row.items():
        if norm(key) in names and val is not None and str(val).strip():
            return val
    return None

def decimal_amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("valor ausente")
    s = str(value).strip().replace("\u00a0", "").replace(" ", "").replace("R$", "")
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    if not s or any(ch not in "+-0123456789.," for ch in s):
        raise ValueError("P/L nao numerico")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        n = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("P/L invalido") from exc
    if not n.is_finite() or abs(n) > Decimal("1000000000"):
        raise ValueError("P/L fora do limite")
    return -n if negative else n

def rows_from(path):
    if path.stat().st_size > 20_000_000:
        raise ValueError("Arquivo acima de 20 MB")
    if path.suffix.lower() == ".json":
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(doc, list):
            return doc
        if isinstance(doc, dict):
            for key, val in doc.items():
                if norm(key) in {norm(x) for x in ALIASES} and isinstance(val, list):
                    return val
        raise ValueError("JSON sem lista de operacoes; arquivos agregados nao sao reimportados")
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        header = fp.readline()
        fp.seek(0)
        delim = ";" if header.count(";") > header.count(",") else ","
        data = csv.DictReader(fp, delimiter=delim)
        if not data.fieldnames:
            raise ValueError("CSV sem cabecalho")
        return list(data)

def summarize(path, currency):
    rows = rows_from(path)
    by_market = defaultdict(lambda: {"operations": 0, "net_pl": Decimal("0")})
    errors = 0
    for row in rows:
        if not isinstance(row, dict):
            errors += 1
            continue
        market = choose(row, MARKET_KEYS)
        profit = choose(row, PROFIT_KEYS)
        if not market or profit is None:
            errors += 1
            continue
        try:
            amount = decimal_amount(profit)
        except ValueError:
            errors += 1
            continue
        key = str(market).strip()[:110]  # preserva Back/Lay e linhas Over/Under
        by_market[key]["operations"] += 1
        by_market[key]["net_pl"] += amount
    count = sum(x["operations"] for x in by_market.values())
    if not count:
        raise ValueError("Nenhuma operacao valida: requer colunas Mercado e netPl/P&L")
    markets = sorted(
        ({"market": name, "operations": val["operations"], "net_pl": float(val["net_pl"])}
         for name, val in by_market.items()),
        key=lambda x: (-x["net_pl"], -x["operations"], x["market"])
    )
    total = sum((v["net_pl"] for v in by_market.values()), Decimal("0"))
    return {
        "provider": "NEXUS PC - exportacao local", "source": path.name,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "snapshot_only": True, "currency": currency,
        "operations": count, "net_pl": float(total),
        "rows_rejected": errors, "markets": markets,
        "note": "P/L do arquivo original, sem simulacao. Nao e retorno do NEXUS, nem EV+, nem lucro em unidades."
    }

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def push_private():
    # Nunca envia o arquivo CSV/JSON original. Requer Git ja autenticado localmente.
    subprocess.run(["git", "-C", str(ROOT), "add", "--", "history/pc_netpl.json", "history/pc_status.json"], check=True)
    changes = subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"], check=False)
    if changes.returncode == 0:
        return
    if changes.returncode != 1:
        raise RuntimeError("Nao foi possivel verificar a alteracao do Git")
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", "NEXUS PC: atualiza resumo privado das operacoes"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "push"], check=True)

def cycle(folder, currency, push=False):
    candidates = [p for p in folder.iterdir()
                  if p.is_file() and not p.is_symlink() and p.suffix.lower() in (".csv", ".json")]
    if not candidates:
        raise FileNotFoundError("Sem CSV/JSON em " + str(folder))
    # Um unico snapshot por ciclo evita duplicar operacoes repetidas entre exportacoes.
    latest = max(candidates, key=lambda p: (p.stat().st_mtime, p.name))
    result = summarize(latest, currency)
    write_json(OUT, result)
    write_json(STATUS, {"ok": True, "checked_at": result["observed_at"],
                        "source": latest.name, "operations": result["operations"]})
    if push:
        push_private()
    print(json.dumps({"file": latest.name, "operations": result["operations"],
                      "net_pl": result["net_pl"], "currency": result["currency"],
                      "market_count": len(result["markets"])}, ensure_ascii=False), flush=True)

def main():
    parser = argparse.ArgumentParser(description="Ler automaticamente exportacoes locais do NEXUS")
    parser.add_argument("--folder", type=Path, default=Path.home() / "NEXUS_IMPORT")
    parser.add_argument("--currency", default="BRL", choices=("BRL", "USD", "EUR"))
    parser.add_argument("--watch", action="store_true", help="Verificar novamente a cada 60 segundos")
    parser.add_argument("--push", action="store_true", help="Enviar SOMENTE o resumo ao GitHub privado autenticado")
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    last = None
    while True:
        try:
            files = [p for p in args.folder.iterdir() if p.is_file() and not p.is_symlink()
                     and p.suffix.lower() in (".csv", ".json")]
            current = max(((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files), default=None,
                          key=lambda x: (x[1], x[0]))
            if current != last:
                cycle(args.folder, args.currency, args.push)
                last = current
        except Exception as exc:
            print("NEXUS PC: " + str(exc), file=sys.stderr, flush=True)
            if not args.watch:
                return 1
        if not args.watch:
            break
        time.sleep(60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
