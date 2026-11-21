import sys, unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pc_rgb import PcLighting, scale, white_rgb, hex_to_rgb


def mode(id, name, colour_mode, speed=None, colors_max=None):
    return SimpleNamespace(id=id, name=name, color_mode=SimpleNamespace(name=colour_mode),
                           speed=speed, speed_min=4 if speed is not None else None,
                           speed_max=0 if speed is not None else None,
                           colors_max=colors_max, colors=None)


def device(id, type, name, specific=False):
    kind = 'MODE_SPECIFIC' if specific else 'PER_LED'
    modes = [mode(0, 'Direct', 'PER_LED'), mode(1, 'Breathing', kind, 2, 1 if specific else None),
             mode(2, 'Rainbow', 'NONE', 2)]
    d = SimpleNamespace(id=id, type=type, name=name, modes=modes, active_mode=0, set_color=Mock())
    def set_mode(m):
        d.active_mode = m.id
    d.set_mode = Mock(side_effect=set_mode)
    return d


class PcRgbTests(unittest.TestCase):
    def setUp(self):
        self.devs = [device(0, 0, 'ASUS TUF B550M-PLUS', specific=True), device(1, 1, 'XPG Spectrix'),
                     device(2, 2, 'GPU')]
        self.client = SimpleNamespace(devices=self.devs, disconnect=Mock())
        self.factory = Mock(return_value=self.client)
        self.pc = PcLighting(client_factory=self.factory)

    def test_colour_math(self):
        self.assertEqual(hex_to_rgb('#ff8000'), (255, 128, 0))
        self.assertEqual(scale((255, 128, 0), 50), (128, 64, 0))
        self.assertEqual(white_rgb(0), (255, 186, 107))
        self.assertEqual(white_rgb(1000), (205, 228, 255))

    def test_only_motherboard_and_ram(self):
        self.assertEqual(self.pc.devices(), ['ASUS TUF B550M-PLUS', 'XPG Spectrix'])
        self.assertEqual(self.pc.apply('#ff0000', 100), 2)
        self.devs[2].set_color.assert_not_called()
        self.devs[0].set_color.assert_called_once_with((255, 0, 0), fast=True)

    def test_direct_mode_once_and_off(self):
        self.devs[1].active_mode = 1
        self.pc.apply('#00ff00', 100)
        self.pc.off()
        self.devs[1].set_mode.assert_called_once()  # só na primeira vez
        self.assertEqual(self.devs[1].set_color.call_args.args[0], (0, 0, 0))
        self.factory.assert_called_once()

    def test_individual_device(self):
        self.pc.apply('#ff0000', 100, types=(1,))
        self.devs[0].set_color.assert_not_called()
        self.devs[0].set_mode.assert_not_called()
        self.devs[1].set_color.assert_called_once()

    def test_effect_colour_and_speed(self):
        self.pc.apply_selection({'mode': 'effect', 'effect': 'breathing', 'colour': '#ff0000',
                                 'brightness': 100, 'speed': 'fast'})
        board_mode = self.devs[0].set_mode.call_args.args[0]
        self.assertEqual((board_mode.name, board_mode.colors, board_mode.speed), ('Breathing', [(255, 0, 0)], 0))
        self.devs[0].set_color.assert_not_called()  # cor vai no próprio modo
        self.assertEqual(self.devs[1].set_mode.call_args.args[0].speed, 0)
        self.devs[1].set_color.assert_called_once_with((255, 0, 0), fast=True)

    def test_effect_without_colour_and_fallback(self):
        self.pc.apply_selection({'mode': 'effect', 'effect': 'rainbow', 'colour': '#ff0000',
                                 'speed': 'slow'})
        self.assertEqual(self.devs[1].set_mode.call_args.args[0].speed, 4)
        self.devs[1].set_color.assert_not_called()
        self.pc.apply_selection({'mode': 'effect', 'effect': 'chase', 'colour': '#00ff00'})
        self.assertEqual(self.devs[1].set_mode.call_args.args[0].name, 'Direct')

    def test_white_selection(self):
        self.pc.apply_selection({'mode': 'white', 'temperature': 0, 'brightness': 100})
        self.devs[1].set_color.assert_called_once_with((255, 186, 107), fast=True)

    def test_reconnects_once_after_failure(self):
        self.devs[0].set_color.side_effect = [ConnectionResetError(), None]
        self.pc.apply('#0000ff', 100)
        self.assertEqual(self.factory.call_count, 2)

    def test_server_missing(self):
        pc = PcLighting(client_factory=Mock(side_effect=ConnectionRefusedError()))
        with self.assertRaisesRegex(RuntimeError, 'OpenRGB'):
            pc.off()

    def test_no_devices(self):
        self.client.devices = [self.devs[2]]
        with self.assertRaisesRegex(RuntimeError, 'administrador'):
            self.pc.off()

    def test_launches_openrgb_when_closed(self):
        factory = Mock(side_effect=[ConnectionRefusedError(), ConnectionRefusedError(), self.client])
        self.client.update = Mock()
        launcher = Mock()
        with patch('pc_rgb.time.sleep'):
            pc = PcLighting(client_factory=factory, launcher=launcher, wait=5)
            self.assertEqual(pc.apply('#ffffff', 100), 2)
        launcher.assert_called_once()

    def test_launch_not_repeated(self):
        launcher = Mock()
        pc = PcLighting(client_factory=Mock(side_effect=ConnectionRefusedError()), launcher=launcher, wait=0)
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, 'OpenRGB'):
                pc.off()
        launcher.assert_called_once()


if __name__ == '__main__':
    unittest.main()
