import unittest
from urllib.error import HTTPError
from oddspapi_odds import safe_provider_error,collect_odds
from datetime import datetime,timezone
NOW=int(datetime(2026,10,19,21,0,tzinfo=timezone.utc).timestamp())
class OddsPapiPrivacyTests(unittest.TestCase):
 def test_no_secret_or_url_in_errors(self):
    secret='THIS_IS_A_FAKE_SECRET_TEST'
    e=RuntimeError('https://api.oddspapi.io/v4/odds?apiKey='+secret)
    self.assertEqual(safe_provider_error(e),'provider_unavailable')
    http=HTTPError('https://api.oddspapi.io/v4/odds?apiKey='+secret,
                   429,'Too Many Requests',{},None)
    self.assertEqual(safe_provider_error(http),'provider_http_429')
    docs={'2026-10-19':{'matches':{'f1':{'fixture':{
          'phase':'scheduled','start_timestamp':NOW+1800,
          'home':'A','away':'B'}}}}}
    status=collect_odds(docs,[('2026-10-19','f1',1800)],NOW,key=secret,
      fetcher=lambda _:(_ for _ in ()).throw(e))
    self.assertEqual(status['status'],'unavailable')
    self.assertNotIn(secret,str(status))
    self.assertNotIn('apiKey',str(status))
 def test_timeout_redacted(self):
    self.assertEqual(safe_provider_error(TimeoutError('secret')),'provider_timeout')
if __name__=='__main__':unittest.main()
