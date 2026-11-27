import base64
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shapes import concentric, squircle_points
from conflicts import analyse, stop_script, summary, DISABLED


class ShapeTests(unittest.TestCase):
    def test_concentric_radius(self):
        self.assertEqual(concentric(20, 14), 6)
        self.assertEqual(concentric(14, 4), 10)
        self.assertEqual(concentric(10, 12), 4)  # mínimo

    def test_squircle_stays_inside_box(self):
        pts = squircle_points(10, 20, 110, 60, 12)
        xs, ys = pts[0::2], pts[1::2]
        self.assertGreaterEqual(min(xs), 10 - 1e-9)
        self.assertLessEqual(max(xs), 110 + 1e-9)
        self.assertGreaterEqual(min(ys), 20 - 1e-9)
        self.assertLessEqual(max(ys), 60 + 1e-9)

    def test_radius_clamped_to_half_side(self):
        pts = squircle_points(0, 0, 100, 10, 50)
        self.assertTrue(all(0 <= y <= 10 + 1e-9 for y in pts[1::2]))


class IconTests(unittest.TestCase):
    def test_icon_sizes(self):
        from icon_art import draw_icon, icon_for
        for sel in ({'mode': 'colour', 'colour': '#ff0000'}, {'mode': 'white', 'temperature': 0},
                    {'mode': 'effect', 'effect': 'rainbow'}):
            img = draw_icon(size=32, **icon_for(sel))
            self.assertEqual(img.size, (32, 32))
        self.assertTrue(icon_for({'mode': 'effect', 'effect': 'rainbow'})['rainbow'])


class ConflictTests(unittest.TestCase):
    def run_analyse(self, procs=(), services=None, installed=(), store=(), pids=(1,),
                    openrgb_service=None, shortcuts=()):
        services = services or {}
        return analyse(set(procs), lambda n: services.get(n), list(installed), list(store),
                       list(pids), openrgb_service, list(shortcuts))

    def test_asus_hal_processes_installed_and_store(self):
        found = self.run_analyse(procs={'aac3572dramhal_x86.exe', 'chrome.exe'},
                                 installed=[('Kingston AURA DRAM Component', 'msiexec /x{1}'),
                                            ('Aurora HDR', '')],
                                 store=['B9ECED6F.ArmouryCrate_6.7.6.0_x64__q'])
        self.assertEqual([f['key'] for f in found], ['asus'])
        asus = found[0]
        self.assertTrue(asus['active'])
        self.assertEqual(asus['running'], ['aac3572dramhal_x86.exe'])
        self.assertEqual([n for n, _ in asus['installed']], ['Kingston AURA DRAM Component'])
        self.assertEqual(len(asus['store']), 1)

    def test_service_disabled_is_ignored_but_installed_alerts(self):
        found = self.run_analyse(services={'LightingService': (False, DISABLED)})
        self.assertEqual(found, [])
        found = self.run_analyse(services={'LightingService': (False, 2)})
        self.assertFalse(found[0]['active'])
        self.assertIn('(instalado)', summary(found))
        self.assertIn('remova todo e qualquer', summary(found))

    def test_hidden_aura_components_alone_are_inactive_leftovers(self):
        from conflicts import alerts
        found = self.run_analyse(installed=[('AURA DRAM Component', 'x'),
                                            ('ASUS AURA Motherboard HAL', 'y'),
                                            ('Kingston AURA DRAM Component', 'z')])
        self.assertEqual(found[0]['severity'], 'leftover')
        self.assertEqual(alerts(found), [])
        self.assertEqual(summary(found), '')
        # Com o app da Store ou um processo rodando, volta a ser alerta.
        found = self.run_analyse(installed=[('AURA DRAM Component', 'x')],
                                 store=['B9ECED6F.ArmouryCrate_6'])
        self.assertEqual(found[0]['severity'], 'installed')
        found = self.run_analyse(procs={'aac3572dramhal_x86.exe'},
                                 installed=[('AURA DRAM Component', 'x')])
        self.assertEqual(found[0]['severity'], 'active')

    def test_asus_helpers_are_visible_without_a_conflict_warning(self):
        from conflicts import alerts, stoppable
        processes = {'armourysocketserver.exe', 'armouryhtmldebugserver.exe'}
        found = self.run_analyse(procs=processes, installed=[('AURA DRAM Component', 'x')])
        self.assertEqual(found[0]['severity'], 'auxiliary')
        self.assertEqual(set(found[0]['running']), processes)
        self.assertEqual(alerts(found), [])
        self.assertEqual(stoppable(found), found)
        active = self.run_analyse(procs=processes | {'lightingservice.exe'})
        self.assertEqual(alerts(active)[0]['severity'], 'active')

    def test_removal_runs_msi_before_bundle(self):
        from conflicts import removal_order
        self.assertEqual(removal_order(['"b.exe" /uninstall /quiet', 'MsiExec.exe /X{A} /qb']),
                         ['MsiExec.exe /X{A} /qb', '"b.exe" /uninstall /quiet'])

    def test_other_rgb_software(self):
        found = self.run_analyse(procs={'icue.exe', 'signalrgb.exe'})
        self.assertEqual({f['key'] for f in found}, {'icue', 'signalrgb'})

    def test_duplicate_openrgb(self):
        self.assertEqual([f['key'] for f in self.run_analyse(pids=(1, 2))], ['openrgb'])
        self.assertEqual([f['key'] for f in self.run_analyse(openrgb_service=(True, 2),
                                                             shortcuts=['x.lnk'])], ['openrgb'])
        self.assertEqual(self.run_analyse(shortcuts=['x.lnk']), [])

    def test_stop_script(self):
        found = self.run_analyse(procs={'aac3572mbhal_x86.exe'},
                                 services={'LightingService': (True, 2)}, pids=(1, 2))
        found[0]['process_ids'] = [(31, 'Aac3572MbHal_x86.exe')]
        text = stop_script(found, r"C:\b")
        self.assertIn("Stop-Service -Name 'LightingService' -Force", text)
        self.assertNotIn('Set-Service', text)
        self.assertIn('Get-Process -Id 31', text)
        self.assertIn("$_.ProcessName -eq 'Aac3572MbHal_x86'", text)
        self.assertIn('$_.Id -ne $server', text)

    def test_elevated_stop_checks_the_windows_process_list_before_reporting_success(self):
        from conflicts import stop_now
        found = self.run_analyse(procs={'armourysocketserver.exe'})
        found[0]['process_ids'] = [(123, 'ArmourySocketServer.exe')]
        win32api = SimpleNamespace(GetSystemDirectory=lambda: r'C:\Windows\System32')
        with patch.dict(sys.modules, win32api=win32api), \
             patch('conflicts._run_elevated', return_value=True) as elevate, \
             patch('conflicts.find_conflicts', side_effect=[found, []]):
            with self.assertRaisesRegex(RuntimeError, 'ainda detecta'):
                stop_now(found, r'C:\ControleLED')
            self.assertTrue(stop_now(found, r'C:\ControleLED'))
        executable, args = elevate.call_args.args
        self.assertIn('System32', executable)
        script = base64.b64decode(args.split()[-1]).decode('utf-16-le')
        self.assertIn('Get-Process -Id 123', script)
        self.assertNotIn('Get-NetTCPConnection', script)

    def test_elevated_stop_cancellation_preserves_current_state(self):
        from conflicts import stop_now
        found = self.run_analyse(procs={'armourysocketserver.exe'})
        win32api = SimpleNamespace(GetSystemDirectory=lambda: r'C:\Windows\System32')
        with patch.dict(sys.modules, win32api=win32api), \
             patch('conflicts._run_elevated', return_value=False), \
             patch('conflicts.find_conflicts') as detect:
            self.assertFalse(stop_now(found, r'C:\ControleLED'))
        detect.assert_not_called()


class RemovalTests(unittest.TestCase):
    def test_msi_repair_becomes_uninstall(self):
        from winproc import removal_command
        self.assertEqual(removal_command('MsiExec.exe /I{1E00994F-C378-4D13-9703-CA8D67B270B7}'),
                         'MsiExec.exe /X{1E00994F-C378-4D13-9703-CA8D67B270B7} IGNOREDEPENDENCIES=ALL /qb /norestart')
        self.assertEqual(removal_command('"C:\\x\\setup.exe" /uninstall', '"C:\\x\\setup.exe" /uninstall /quiet'),
                         '"C:\\x\\setup.exe" /uninstall /quiet')
        self.assertEqual(removal_command('"C:\\y\\unins000.exe"'), '"C:\\y\\unins000.exe"')

    def test_remove_script_runs_each_and_waits(self):
        from conflicts import remove_script
        text = remove_script(['"C:\\a b\\s.exe" /uninstall /quiet', 'MsiExec.exe /X{X} /qb'])
        self.assertEqual(text.count('-Wait'), 2)
        self.assertIn("'/c \"\"C:\\a b\\s.exe\" /uninstall /quiet\"'", text)


if __name__ == '__main__':
    unittest.main()
