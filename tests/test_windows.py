import sys, unittest, types
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_integration import SessionListener, set_startup, startup_command
class WindowsTests(unittest.TestCase):
 def test_shutdown_and_restart(self):
  send=Mock(); listener=SessionListener(lambda:True,send,Mock())
  self.assertEqual(listener.handle(0x11,0,0),1)
  send.assert_not_called()
  listener.handle(0x16,1,0)
  send.assert_called_once()
 def test_cancel_logoff_and_disabled(self):
  send=Mock(); listener=SessionListener(lambda:True,send,Mock())
  listener.handle(0x16,0,0)
  listener.handle(0x16,1,0x80000000)
  send.assert_not_called()
  listener.should_switch_off=lambda:False
  listener.handle(0x16,1,0)
  send.assert_not_called()
 def test_registry_enable_disable(self):
  registry=types.SimpleNamespace(CreateKey=MagicMock(),HKEY_CURRENT_USER=1,REG_SZ=1,SetValueEx=Mock(),DeleteValue=Mock())
  with patch.dict(sys.modules,winreg=registry),patch('windows_integration.os.name','nt'),patch('windows_integration.startup_command',return_value='"C:\\My App\\ControleLED.exe" --startup'):
   set_startup(True)
   self.assertEqual(registry.SetValueEx.call_args.args[1],'ControleLED')
   self.assertIn('--startup',registry.SetValueEx.call_args.args[4])
   set_startup(False)
   self.assertEqual(registry.DeleteValue.call_args.args[1],'ControleLED')
 def test_frozen_path_quoted(self):
  with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',r'C:\My App\ControleLED.exe'):
   self.assertEqual(startup_command(),'"C:\\My App\\ControleLED.exe" --startup')
if __name__ == '__main__':
 unittest.main()
