import sys, json, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from effects import EFFECTS, tuya_scene


class EffectTests(unittest.TestCase):
    def test_quick_shortcuts_valid(self):
        from effects import QUICK_COLOURS, QUICK_BRIGHTNESS
        import re
        for _, hex_ in QUICK_COLOURS:
            # minúsculo: o menu compara com a cor salva em minúsculas
            self.assertRegex(hex_, r'^#[0-9a-f]{6}$')
        self.assertTrue(all(1 <= b <= 100 for b in QUICK_BRIGHTNESS))

    def test_scenes_within_tuya_limits(self):
        for key, *_ in EFFECTS:
            if key == 'static':
                continue
            for speed in ('slow', 'medium', 'fast'):
                scene = tuya_scene(key, '#ff0000', 100, speed)
                self.assertTrue(1 <= scene['scene_num'] <= 8)
                self.assertTrue(1 <= len(scene['scene_units']) <= 8)
                for unit in scene['scene_units']:
                    self.assertIn(unit['unit_change_mode'], ('static', 'jump', 'gradient'))
                    for field in ('unit_switch_duration', 'unit_gradient_duration'):
                        self.assertTrue(0 <= unit[field] <= 100)
                    self.assertTrue(0 <= unit['h'] <= 360 and 0 <= unit['s'] <= 1000 and 0 <= unit['v'] <= 1000)

    def test_breathing_uses_colour_and_speed(self):
        slow = tuya_scene('breathing', '#00ff00', 50, 'slow')['scene_units']
        fast = tuya_scene('breathing', '#00ff00', 50, 'fast')['scene_units']
        self.assertEqual((slow[0]['h'], slow[0]['v'], slow[1]['v']), (120, 500, 10))
        self.assertLess(fast[0]['unit_gradient_duration'], slow[0]['unit_gradient_duration'])


if __name__ == '__main__':
    unittest.main()
