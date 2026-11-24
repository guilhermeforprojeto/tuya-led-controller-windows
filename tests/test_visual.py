import sys, unittest
from pathlib import Path
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
        text = stop_script(found, r"C:\b")
        self.assertIn("Set-Service -Name 'LightingService' -StartupType Disabled", text)
        self.assertIn("Stop-Process -Name 'aac3572mbhal_x86' -Force", text)
        self.assertNotIn("Stop-Process -Name 'openrgb'", text)
        self.assertIn('$_.Id -ne $server', text)


class RemovalTests(unittest.TestCase):
    def test_msi_repair_becomes_uninstall(self):
        from winproc import removal_command
        self.assertEqual(removal_command('MsiExec.exe /I{1E00994F-C378-4D13-9703-CA8D67B270B7}'),
                         'MsiExec.exe /X{1E00994F-C378-4D13-9703-CA8D67B270B7} /qb /norestart')
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