# Tuya LED Controller for Windows — RGB+CCT system tray app

Control compatible Tuya / Smart Life Wi-Fi LED strips from a Windows system tray app using the Tuya Cloud API. Supports power, RGB colors, brightness, white color temperature, optional startup and best-effort shutdown synchronization.

[Full Portuguese setup guide](README.md) · [Tuya cloud setup](docs/configurar-tuya.md)

## Install

1. Install [Python 3.11+ for Windows](https://www.python.org/downloads/windows/) with Python Launcher and Tcl/Tk.
2. Download this repository with **Code → Download ZIP** and extract it.
3. Run `Gerar_executavel.bat`.
4. Open `dist/ControleLED.exe`.
5. In **Configuração**, enter the cloud project's Access ID, Access Secret and your Device ID. Save and test.

The UI is in Portuguese. No prebuilt binary is included in the source package. The Windows build workflow can generate a binary as an Actions artifact.

## Requirements and limits

- Windows 10/11 and a compatible Tuya RGB+CCT controller with standard commands.
- A valid Tuya Cloud project linked to your app account, with device control permission.
- Internet access on both PC and controller.
- This version uses **Western America** (`openapi.tuyaus.com`). Other regions require updating `ENDPOINT` in the code to match the [official endpoint list](https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4).
- Credentials are stored as local plaintext in `%APPDATA%/ControleLED/config.json`. Never commit them.
- Startup occurs after user login. Closing the window keeps the tray app running; **Sair** exits.
- LED power-on at startup is optional. Disabled means no change to the existing LED state.
- Shutdown/restart power-off is best effort, limited to about three seconds. It requires the app running and working internet. It cannot handle forced termination or power loss.
- No Bluetooth, offline LAN control, Google Home API or Armoury Crate/Aura Sync integration.
- API access is subject to Tuya's quotas, expiry and commercial terms.

Tests use mocks. Native Windows behavior and real application-to-device communication still require hardware validation. This is an independent project, not an official Tuya application.

By Guilherme Santana Santos · [System Bee Solutions](https://systembee.com.br/)
