import json
import os
from pathlib import Path
import tempfile
import unittest

import pc_reader


class PcReaderTests(unittest.TestCase):
    def make(self, folder, name, text):
        path = Path(folder) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_brazilian_csv_keeps_exact_market_and_real_pl(self):
        with tempfile.TemporaryDirectory() as td:
            f = self.make(td, "operacoes.csv",
                "Mercado;netPl;Stake\nBACK Over 1.5 HT;12,50;5\n"
                "LAY Correct Score 1-0;-3,25;5\nBACK Over 1.5 HT;1,75;5\n")
            data = pc_reader.summarize(f, "BRL")
            self.assertEqual(data["operations"], 3)
            self.assertEqual(data["net_pl"], 11.0)
            self.assertEqual(data["markets"][0]["market"], "BACK Over 1.5 HT")
            self.assertEqual(data["markets"][0]["net_pl"], 14.25)
            self.assertTrue(data["snapshot_only"])
            self.assertNotIn("profit_units", data)

    def test_json_operations_and_rejects_invalid_rows(self):
        with tempfile.TemporaryDirectory() as td:
            f = self.make(td, "entradas.json", json.dumps({"operations": [
                {"market": "MATCH_ODDS", "netPl": "-2.00"},
                {"market": "MATCH_ODDS", "netPl": "4.50"},
                {"market": "UNDER_25", "netPl": "desconhecido"},
            ]}))
            data = pc_reader.summarize(f, "BRL")
            self.assertEqual(data["net_pl"], 2.5)
            self.assertEqual(data["operations"], 2)
            self.assertEqual(data["rows_rejected"], 1)

    def test_decimal_values(self):
        self.assertEqual(pc_reader.decimal_amount("R$ 1.234,56"), pc_reader.Decimal("1234.56"))
        self.assertEqual(pc_reader.decimal_amount("(10,50)"), pc_reader.Decimal("-10.50"))
        with self.assertRaises(ValueError):
            pc_reader.decimal_amount("NaN")

    def test_missing_market_or_pl_never_creates_fake_pl(self):
        with tempfile.TemporaryDirectory() as td:
            f = self.make(td, "missing.csv", "Jogo;Resultado\nA x B;1-0\n")
            with self.assertRaises(ValueError):
                pc_reader.summarize(f, "BRL")

    def test_public_snapshot_excludes_private_financials(self):
        source = (Path(__file__).resolve().parents[1] / "web" / "data.json").read_text(encoding="utf-8")
        data = json.loads(source)
        self.assertNotIn("bolsa", data)
        self.assertNotIn("pc_import", data)
        self.assertNotIn("net_pl", source)
        self.assertNotIn("paper_signals", source)


if __name__ == "__main__":
    unittest.main()
