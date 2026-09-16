import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from provider_health import import_session, record, rows, summary

class ProviderHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name)/"requests.csv"

    def test_unknown_billing_and_rate_limit_are_not_zero_or_success(self):
        record("a","morph/fp8","flash","failed",2,error="HTTPError: HTTP 429",path=self.log)
        record("b","morph/fp8","flash","received",4,usage={"cost":0.01},path=self.log)
        result=summary(self.log)[0]
        self.assertEqual((result["requests"],result["received"],result["failed"],result["rate_limits"]),(2,1,1,1))
        self.assertEqual(result["unknown_cost_requests"],1)
        self.assertEqual(result["known_cost_usd"],0.01)
        self.assertEqual(result["median_received_seconds"],4)

    def test_reimport_preserves_unknown_original_error_without_inflation(self):
        journal=Path(self.tmp.name)/"session";journal.mkdir()
        events=[{"type":"request","attempt":"a","worker":"flash","provider":"morph/fp8"},
                {"type":"failure","attempt":"a","detail":"HTTPError"},
                {"type":"response","attempt":"a","at":1,"status":"failed","usage":None,"elapsed_seconds":2}]
        (journal/"events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        import_session(journal,self.log);import_session(journal,self.log)
        self.assertEqual(len(rows(self.log)),1)
        self.assertEqual(rows(self.log)[0]["http_status"],"")
        self.assertNotIn("prompt",rows(self.log)[0])

    def test_parallel_writers_keep_one_header_and_all_records(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: record(str(i),"fireworks","flash","received",1,{"cost":0},path=self.log),range(30)))
        self.assertEqual(len(rows(self.log)),30)
        self.assertEqual(self.log.read_text().count("attempt,at,provider"),1)
