import sys, json, unittest, hashlib, hmac
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controle_led import Tuya, colour_value, make_headers, command
class Tests(unittest.TestCase):
 def test_rgb(self):
  self.assertEqual(json.loads(colour_value('#ff0000',50)), {'h':0,'s':1000,'v':500})
  self.assertEqual(json.loads(colour_value('#00ff00',100))['h'],120)
  self.assertEqual(json.loads(colour_value('#0000ff',1))['v'],10)
 def test_signature(self):
  body=b'{"commands":[]}'
  path='/v1.0/iot-03/devices/test/commands'
  headers=make_headers('id','secret','POST',path,body,'token',123)
  canonical='POST\n'+hashlib.sha256(body).hexdigest()+'\n\n'+path
  expected=hmac.new(b'secret',('idtoken123'+canonical).encode(),hashlib.sha256).hexdigest().upper()
  self.assertEqual(headers['sign'],expected)
  self.assertEqual(headers['access_token'],'token')
 def test_token_cached_and_power_preserves_colour(self):
  api=Tuya({'client_id':'test','secret':'test','device_id':'example'})
  with patch.object(api,'raw',side_effect=[{'access_token':'TOKEN','expire_time':7200},True,True]) as raw:
   api.send([command('switch_led',False)])
   api.send([command('switch_led',True)])
   self.assertEqual(raw.call_count,3)
   self.assertEqual(raw.call_args_list[1].args[2], {'commands':[{'code':'switch_led','value':False}]})
   self.assertEqual(raw.call_args_list[2].args[1], '/v1.0/iot-03/devices/example/commands')
 def test_rejected(self):
  api=Tuya({'client_id':'test','secret':'test','device_id':'example'})
  with patch.object(api,'request',return_value=False):
   with self.assertRaises(RuntimeError): api.send([command('switch_led',True)])
if __name__ == '__main__':
 unittest.main()
