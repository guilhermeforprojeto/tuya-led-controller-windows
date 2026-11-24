import re, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from palettes import GROUPS, FAVOURITES, name_for, remember
from colour_picker import parse_hex, hex_from_hs, hs_from_hex


class PaletteTests(unittest.TestCase):
    def test_colours_are_valid_hex(self):
        for _, _, colours in GROUPS:
            for name, hex_ in colours:
                self.assertRegex(hex_, r'^#[0-9a-f]{6}$', name)
        for hex_ in FAVOURITES:
            self.assertRegex(hex_, r'^#[0-9a-f]{6}$')

    def test_name_lookup(self):
        self.assertEqual(name_for('#FFBE98'), 'Peach Fuzz · 2024')
        self.assertEqual(name_for('#123456'), '')

    def test_recent_colours(self):
        self.assertEqual(remember(['#aa0000', '#00aa00'], '#00AA00'), ['#00aa00', '#aa0000'])
        self.assertEqual(len(remember([f'#0000{i:02x}' for i in range(10)], '#ffffff')), 8)


class PickerTests(unittest.TestCase):
    def test_parse_hex(self):
        self.assertEqual(parse_hex('FFBE98'), '#ffbe98')
        self.assertEqual(parse_hex('#f0a'), '#ff00aa')
        self.assertIsNone(parse_hex('#12345'))
        self.assertIsNone(parse_hex('zzzzzz'))

    def test_hue_saturation_round_trip(self):
        h, s = hs_from_hex(hex_from_hs(0.6, 0.5))
        self.assertAlmostEqual(h, 0.6, places=2)
        self.assertAlmostEqual(s, 0.5, places=2)


if __name__ == '__main__':
    unittest.main()
