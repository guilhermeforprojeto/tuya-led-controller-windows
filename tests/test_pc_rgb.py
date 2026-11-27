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


def device(id, type, name, specific=False, address=None):
    kind = 'MODE_SPECIFIC' if specific else 'PER_LED'
    modes = [mode(0, 'Direct', 'PER_LED'), mode(1, 'Breathing', kind, 2, 1 if specific else None),
             mode(2, 'Rainbow', 'NONE', 2)]
    location = f'I2C: SMBus 0, address {address}' if address else 'HID: x'
    d = SimpleNamespace(id=id, type=type, name=name, modes=modes, active_mode=0, set_color=Mock(),
                        set_colors=Mock(), metadata=SimpleNamespace(location=location))
    def set_mode(m):
        d.active_mode = m.id
    d.set_mode = Mock(side_effect=set_mode)
    return d


class PcRgbTests(unittest.TestCase):
    def setUp(self):
        self.devs = [device(0, 0, 'ASUS TUF B550M-PLUS', specific=True),
                     device(1, 1, 'ENE DRAM', address='0x71'), device(2, 2, 'GPU'),
                     device(3, 1, 'ENE DRAM', address='0x70')]
        self.client = SimpleNamespace(devices=self.devs, disconnect=Mock())
        self.factory = Mock(return_value=self.client)
        self.pc = PcLighting(client_factory=self.factory)
        self.pc.ram.autostart = False

    def last_colours(self, dev):
        return dev.set_colors.call_args.args[0]

    def test_colour_math(self):
        self.assertEqual(hex_to_rgb('#ff8000'), (255, 128, 0))
        self.assertEqual(scale((255, 128, 0), 50), (128, 64, 0))
        self.assertEqual(white_rgb(0), (255, 186, 107))
        self.assertEqual(white_rgb(1000), (205, 228, 255))

    def test_only_motherboard_and_ram(self):
        self.assertEqual(self.pc.devices(), ['ASUS TUF B550M-PLUS', 'ENE DRAM', 'ENE DRAM'])
        self.pc.apply('#ff0000', 100, types=(0,))
        self.devs[2].set_color.assert_not_called()
        self.devs[0].set_color.assert_called_once_with((255, 0, 0), fast=True)

    def test_board_direct_mode_once_and_off(self):
        self.devs[0].active_mode = 1
        self.pc.apply('#00ff00', 100, types=(0,))
        self.pc.off((0,))
        self.devs[0].set_mode.assert_called_once()  # só na primeira vez
        self.assertEqual(self.devs[0].set_color.call_args.args[0], (0, 0, 0))
        self.factory.assert_called_once()

    def test_board_effect_colour_and_speed(self):
        self.pc.apply_selection({'mode': 'effect', 'effect': 'breathing', 'colour': '#ff0000',
                                 'brightness': 100, 'speed': 'fast'}, (0,))
        board_mode = self.devs[0].set_mode.call_args.args[0]
        self.assertEqual((board_mode.name, board_mode.colors, board_mode.speed), ('Breathing', [(255, 0, 0)], 0))
        self.devs[0].set_color.assert_not_called()  # cor vai no próprio modo

    def test_ram_sticks_in_address_order_and_direct(self):
        self.assertEqual(self.pc.ram.addresses(), ['0x70', '0x71'])
        self.pc.apply_selection({'mode': 'colour', 'colour': '#ff0000', 'brightness': 100}, (1,))
        self.pc.ram._send(0)
        for d in (self.devs[1], self.devs[3]):
            self.assertEqual(d.set_mode.call_args.args[0].name, 'Direct')
            self.assertEqual(self.last_colours(d), [(255, 0, 0)] * 5)
        self.devs[0].set_mode.assert_not_called()

    def test_restore_redetects_missing_ram_and_refreshes_device_indices(self):
        self.client.devices = [self.devs[0]]
        board = device(1, 0, 'ASUS TUF B550M-PLUS')
        stick = device(0, 1, 'ENE DRAM', address='0x70')
        recovered = SimpleNamespace(devices=[stick, board], disconnect=Mock())
        self.factory.side_effect = [self.client, recovered]
        self.pc.ram.restore({'0x70': {'sel': {'mode': 'colour', 'colour': '#ff0000'}}})
        self.pc.apply('#ffffff', 100, (0,))
        with patch('pc_rgb.rescan_openrgb') as rescan:
            self.pc.ram._send(0, scan=self.pc.ram._scan_on_restore)
        rescan.assert_called_once_with('127.0.0.1', 6742)
        self.client.disconnect.assert_called_once()
        self.assertEqual(self.last_colours(stick), [(255, 0, 0)] * 5)
        self.pc.apply('#ffffff', 100, (0,))
        board.set_mode.assert_called_once()
        board.set_color.assert_called_once_with((255, 255, 255), fast=True)

    def test_restore_does_not_redetect_when_ram_is_available(self):
        self.pc.ram.restore({'0x70': {'sel': {'mode': 'colour', 'colour': '#ff0000'}}})
        with patch('pc_rgb.rescan_openrgb') as rescan:
            self.pc.ram._send(0, scan=self.pc.ram._scan_on_restore)
        rescan.assert_not_called()
        self.assertEqual(self.last_colours(self.devs[3]), [(255, 0, 0)] * 5)

    def test_only_selected_sticks_change(self):
        red = {'mode': 'colour', 'colour': '#ff0000', 'brightness': 100}
        blue = {'mode': 'colour', 'colour': '#0000ff', 'brightness': 100}
        self.pc.apply_selection(red, (1,))
        self.pc.apply_selection(blue, (1,), sticks=[2])   # posição 2 = 0x71
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[3])[0], (255, 0, 0))
        self.assertEqual(self.last_colours(self.devs[1])[0], (0, 0, 255))
        self.pc.ram_power(False, [1])
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[3]), [(0, 0, 0)] * 5)
        self.pc.ram_power(True, [1])
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[3])[0], (255, 0, 0))

    def test_calibration_lights_only_one_stick(self):
        self.pc.ram.addresses()
        self.pc.ram.set_solo('0x71')
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[1]), [(255, 255, 255)] * 5)
        self.assertEqual(self.last_colours(self.devs[3]), [(0, 0, 0)] * 5)
        # Ao terminar, pentes sem estado recebem a seleção atual em vez de ficarem apagados.
        self.pc.ram.set_solo(None, {'mode': 'colour', 'colour': '#00ff00'})
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[3])[0], (0, 255, 0))

    def test_position_states_follow_order(self):
        self.pc.ram.order = ['0x71', '0x70']
        self.pc.apply_selection({'mode': 'colour', 'colour': '#ff0000'}, (1,))
        self.pc.ram_power(False, [2])   # posição 2 = 0x70
        self.assertEqual(self.pc.ram.position_states(), [True, False])
        self.assertFalse(self.pc.ram.snapshot()['0x70']['on'])

    def test_custom_order(self):
        self.pc.ram.order = ['0x71', '0x70']
        self.assertEqual(self.pc.ram.resolve([1]), ['0x71'])

    def test_white_selection(self):
        self.pc.apply_selection({'mode': 'white', 'temperature': 0, 'brightness': 100}, (1,))
        self.pc.ram._send(0)
        self.assertEqual(self.last_colours(self.devs[3])[0], (255, 186, 107))
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
            self.assertEqual(pc.apply('#ffffff', 100, types=(0,)), 1)
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
