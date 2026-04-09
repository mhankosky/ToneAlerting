# Pi Radio Alerts

Headless Raspberry Pi 5 service that:

- listens on `153.890 MHz` with an `RTL-SDR`
- detects Motorola Quick Call II tone sequences
- scrolls active alerts as a comma-separated ticker in arrival order
- keeps each alert active for `2 minutes`
- refreshes an alert's `2 minute` timer if the same alert is received again
- alternates alert colors while scrolling
- shows a blinking light-green health indicator at the bottom when the system is healthy
- switches the display to a red `ERROR` screen with black text if the service encounters a runtime problem

## Hardware

- Raspberry Pi 5
- RTL-SDR USB receiver
- 16x32 RGB LED Matrix Panel 6mm Pitch, Adafruit product `420`
- A compatible HUB75 driver board for the Pi, typically the Adafruit RGB Matrix Bonnet or HAT

## Software Notes

This app expects:

- `rtl_fm` from the `rtl-sdr` package for radio audio
- Python `3.11+`
- `hzeller/rpi-rgb-led-matrix` Python bindings installed on the Pi for the real LED panel

`rgbmatrix` is not listed in `pyproject.toml` because it usually needs to be built on the Pi against the panel driver library.

## Install

### Fresh Raspberry Pi OS Lite 64-bit

1. Flash `Raspberry Pi OS Lite (64-bit)` to the microSD card with Raspberry Pi Imager.
2. In the imager advanced options, enable SSH, set hostname, configure Wi-Fi if needed, and create your user.
3. Boot the Pi 5, then connect over SSH.
4. Update the OS:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

5. Install base packages:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev build-essential cmake pkg-config rtl-sdr libatlas-base-dev libgraphicsmagick++-dev libwebp-dev
```

6. If the DVB kernel driver grabs the RTL-SDR, blacklist it:

```bash
sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf >/dev/null <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
sudo reboot
```

7. After reboot, confirm the radio is visible:

```bash
rtl_test
```

### Application Install

```bash
git clone /path/to/this/project /opt/pi-radio-alerts
cd /opt/pi-radio-alerts
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### RGB Matrix Library

Install the RGB matrix library on the Pi by following the Adafruit/HZeller setup for Raspberry Pi 5 and HUB75 panels.

Typical flow:

```bash
cd /opt
sudo git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make build-python PYTHON=$(command -v python3)
```

Then install the Python binding into the project virtualenv:

```bash
cd /opt/pi-radio-alerts
source .venv/bin/activate
pip install /opt/rpi-rgb-led-matrix/bindings/python
```

If you are using the Adafruit RGB Matrix Bonnet/HAT, the default `hardware_mapping` in this project is already set to `adafruit-hat-pwm`.

## Run

For real radio input:

```bash
pi-radio-alerts --frequency-mhz 153.89 --hold-seconds 120
```

For development without the LED panel attached:

```bash
PI_RADIO_ALERTS_CONSOLE=1 pi-radio-alerts
```

For offline WAV-file testing:

```bash
PI_RADIO_ALERTS_CONSOLE=1 pi-radio-alerts --wav-file /path/to/test.wav
```

## Display Behavior

- Alerts scroll left-to-right as one comma-separated list in the order they were first received.
- Each alert remains active for `120 seconds`.
- If the same alert is received again before expiry, its `120 second` timer is reset and its position stays the same.
- The ticker alternates colors per alert for easier separation on the matrix.
- A blinking light-green indicator on the bottom edge means the process is healthy.
- If the app hits a startup or runtime failure, it switches the matrix to a red `ERROR` screen.

## Service

Example `systemd` unit:

```ini
[Unit]
Description=Pi Radio Alerts
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/pi-radio-alerts
ExecStart=/opt/pi-radio-alerts/.venv/bin/pi-radio-alerts --frequency-mhz 153.89 --hold-seconds 120
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

Save that as `/etc/systemd/system/pi-radio-alerts.service`, then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-radio-alerts.service
sudo systemctl status pi-radio-alerts.service
```

## Tone List

`tones.json` contains the sequences extracted from your Phoenix G2 tone list PDF.

## Tuning Notes

- The detector currently uses FFT windowing and frequency/duration matching with tolerances suited to Quick Call II.
- You may want to tune `gain`, `squelch`, and detector thresholds once you test with live traffic on-site.
- `EAST HAZEL CREST DUTY` and `EAST HAZEL CREST STILL` are identical in the source PDF, so both currently resolve to the same tone pair.
