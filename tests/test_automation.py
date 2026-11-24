import sys, unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import (valid_time, due_routines, pick_profile, ProfileSwitcher,
                        describe_days, describe_selection)
from effects import EFFECTS


class RoutineTests(unittest.TestCase):
    def test_valid_time(self):
        self.assertEqual(valid_time('7:05'), '07:05')
        self.assertEqual(valid_time(' 23:59 '), '23:59')
        self.assertIsNone(valid_time('24:00'))
        self.assertIsNone(valid_time('7h'))

    def test_due_once_per_minute_and_day_filter(self):
        r = {'id': 'a', 'time': '22:00', 'days': [0], 'action': 'off'}  # segunda
        monday = datetime(2026, 11, 23, 22, 0, 30)
        last = {}
        self.assertEqual(due_routines([r], monday, last), [r])
        self.assertEqual(due_routines([r], monday, last), [])  # mesmo minuto
        self.assertEqual(due_routines([r], datetime(2026, 11, 24, 22, 0), {}), [])  # terça
        self.assertEqual(due_routines([dict(r, enabled=False)], monday, {}), [])

    def test_descriptions(self):
        self.assertEqual(describe_days([0, 1, 2, 3, 4]), 'Seg a Sex')
        self.assertEqual(describe_days([5, 6]), 'Fim de semana')
        self.assertIn('Respirar', describe_selection(
            {'mode': 'effect', 'effect': 'breathing', 'colour': '#ff0000', 'brightness': 50}, EFFECTS))


class ProfileTests(unittest.TestCase):
    def test_pick_profile_priority_and_focus(self):
        game = {'id': 'g', 'process': 'Game.exe', 'when': 'open'}
        editor = {'id': 'e', 'process': 'code.exe', 'when': 'focus'}
        self.assertIs(pick_profile([game, editor], {'game.exe', 'code.exe'}, 'code.exe'), game)
        self.assertIs(pick_profile([game, editor], {'code.exe'}, 'code.exe'), editor)
        self.assertIsNone(pick_profile([game, editor], {'code.exe'}, 'chrome.exe'))
        self.assertIsNone(pick_profile([dict(game, enabled=False)], {'game.exe'}, ''))

    def test_switcher_apply_then_restore(self):
        s = ProfileSwitcher()
        p = {'id': 'g'}
        self.assertEqual(s.decide(p), ('apply', p))
        self.assertIsNone(s.decide(p))
        self.assertEqual(s.decide(None), ('restore', None))
        self.assertIsNone(s.decide(None))


if __name__ == '__main__':
    unittest.main()
