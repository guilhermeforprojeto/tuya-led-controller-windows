import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shapes import concentric, squircle_points
from conflicts import analyse, fix_script, DISABLED


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
    def test_asus_service_running_or_enabled(self):
        self.assertEqual([k for k, _ in analyse((True, 2), None, [1], [])], ['asus'])
        self.assertEqual([k for k, _ in analyse((False, 2), None, [1], [])], ['asus'])
        self.assertEqual(analyse((False, DISABLED), None, [1], []), [])
        self.assertEqual(analyse(None, None, [1], []), [])

    def test_duplicate_openrgb(self):
        self.assertEqual([k for k, _ in analyse(None, None, [1, 2], [])], ['openrgb'])
        # Atalho na Inicialização só conflita se o OpenRGB já roda como serviço.
        self.assertEqual([k for k, _ in analyse(None, (True, 2), [1], ['x.lnk'])], ['openrgb'])
        self.assertEqual(analyse(None, None, [1], ['x.lnk']), [])

    def test_fix_script_keeps_server(self):
        text = fix_script(r'C:\b', [r'C:\s\OpenRGB.lnk'])
        self.assertIn('Set-Service -Name LightingService -StartupType Disabled', text)
        self.assertIn("Move-Item -LiteralPath 'C:\\s\\OpenRGB.lnk'", text)
        self.assertIn('$_.Id -ne $server', text)


if __name__ == '__main__':
    unittest.main()
