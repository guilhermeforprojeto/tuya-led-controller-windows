import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fx import frame, single, is_animated, PERIOD
from pc_rgb import stick_colours


def brightest(rows):
    return max(range(len(rows)), key=lambda i: sum(rows[i][0]))


class FxTests(unittest.TestCase):
    def test_static_colour_and_brightness(self):
        rows = frame({'mode': 'colour', 'colour': '#ff0000', 'brightness': 50}, 0, sticks=2)
        self.assertEqual(rows[0][0], (127.5, 0, 0))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 5)

    def test_chase_walks_sticks_in_order(self):
        sel = {'mode': 'effect', 'effect': 'chase', 'colour': '#00ff00', 'speed': 'medium'}
        period = PERIOD['medium']
        heads = [brightest(frame(sel, period * f, sticks=4)) for f in (0.15, 0.35, 0.55, 0.75)]
        self.assertEqual(heads, sorted(heads))
        self.assertEqual(heads[0], 0)
        self.assertEqual(heads[-1], 3)

    def test_all_sticks_share_one_clock(self):
        sel = {'mode': 'effect', 'effect': 'breathing', 'colour': '#ffffff'}
        rows = frame(sel, 1.0, sticks=4)
        self.assertTrue(all(row == rows[0] for row in rows))
        self.assertEqual(single(sel, 1.0), rows[0][0])

    def test_animated_flags(self):
        self.assertFalse(is_animated({'mode': 'colour'}))
        self.assertFalse(is_animated({'mode': 'effect', 'effect': 'static'}))
        self.assertTrue(is_animated({'mode': 'effect', 'effect': 'rainbow'}))

    def test_groups_and_off(self):
        red = {'mode': 'colour', 'colour': '#ff0000'}
        sticks = {'a': {'sel': red, 'on': True, 'group': 1}, 'b': {'sel': red, 'on': False, 'group': 1},
                  'c': {'sel': {'mode': 'colour', 'colour': '#0000ff'}, 'on': True, 'group': 2}}
        out = stick_colours(sticks, ['a', 'b', 'c', 'd'], 0)
        self.assertEqual(out['a'][0], (255, 0, 0))
        self.assertEqual(out['b'], [(0, 0, 0)] * 5)
        self.assertEqual(out['c'][0], (0, 0, 255))
        self.assertNotIn('d', out)  # pente sem estado: o app não mexe


if __name__ == '__main__':
    unittest.main()
