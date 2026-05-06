# ChoreWars

A home chore tracker built for two people, running as a touchscreen kiosk on a Raspberry Pi. Tap a chore, tap your name — see who's winning the week.

## How it works

- **Home screen** shows all chores (Litter Box, Dishes, Laundry, Bathroom, Vacuum, Trash) plus a weekly score for each person.
- **Tap a chore** → pick who did it (JC or MG).
- **Celebration screen** shows a 10-second confirmation, then returns home automatically.
- **Done chores** show `✓ Person` in place of the icon so you can see at a glance what's left.
- **Weekly strip** at the top tracks total chores done by each person since Monday.
- **★ History** shows a monthly summary with progress bars and a full log with chore labels.
- **⚙️ Settings** lets you delete a mistaken entry or reset all scores.
- **Screensaver** kicks in after 2 minutes idle — bouncing emojis during the day, near-black clock at night (11 pm – 7 am).

---

## Hardware

| Part | Details |
|---|---|
| Board | Raspberry Pi 3 Model B (or newer) |
| Display | Adafruit PiTFT 3.5" Resistive Touchscreen |
| Driver | `fb_hx8357d` via `dtoverlay=pitft35-resistive` |
| Power | 5.1V 2.5A supply with a short 24 AWG cable |

---

## Software stack

- Python 3 + Flask
- SQLite (auto-created on first run)
- Single-page HTML/CSS/JS frontend
- Chromium in kiosk mode

---

## Setup

### 1. Flash Raspberry Pi OS

Use **Raspberry Pi OS Lite** or the full desktop version. The desktop version (with LightDM) is required for the kiosk display.

Enable SSH during the flash via Raspberry Pi Imager.

### 2. Connect the PiTFT display

Follow [Adafruit's PiTFT installation guide](https://learn.adafruit.com/adafruit-pitft-3-dot-5-touch-screen-for-raspberry-pi). Add the following to `/boot/config.txt`:

```
dtoverlay=pitft35-resistive,rotate=90,speed=32000000,fps=20
avoid_warnings=2
```

### 3. Configure X to render on the PiTFT

Create `/etc/X11/xorg.conf`:

```
Section "Device"
  Identifier "PiTFT"
  Driver "fbdev"
  Option "fbdev" "/dev/fb1"
EndSection

Section "Screen"
  Identifier "PiTFT Screen"
  Device "PiTFT"
EndSection

Section "ServerLayout"
  Identifier "Default"
  Screen "PiTFT Screen"
EndSection
```

Reboot. Your desktop should now appear on the PiTFT.

### 4. Install dependencies

```bash
sudo apt update
sudo apt install -y python3-pip chromium-browser unclutter
pip3 install flask
```

### 5. Clone the repo

```bash
git clone https://github.com/your-username/ChoreWars.git
cd ChoreWars
```

### 6. Configure player names

Open `app.py` and edit the two constants at the top:

```python
PLAYER_1 = "AA"   # replace with first person's initials
PLAYER_2 = "BB"   # replace with second person's initials
```

### 7. Run manually

```bash
python3 app.py &
DISPLAY=:0 bash kiosk.sh &
```

Open `http://localhost:5050` on any browser on the same network to verify.

---

## Autostart on boot (systemd)

Create `/etc/systemd/system/chorewars.service`:

```ini
[Unit]
Description=ChoreWars App
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/ChoreWars
ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/ChoreWars/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/chorewars-kiosk.service`:

```ini
[Unit]
Description=ChoreWars Kiosk
After=graphical.target chorewars.service
Requires=chorewars.service

[Service]
User=YOUR_USERNAME
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/YOUR_USERNAME/.Xauthority
ExecStartPre=/bin/sleep 5
ExecStart=/bin/bash /home/YOUR_USERNAME/ChoreWars/kiosk.sh
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable chorewars.service chorewars-kiosk.service
sudo systemctl start chorewars.service chorewars-kiosk.service
```

---

## Display scaling

The kiosk is tuned for the Adafruit PiTFT 3.5" (480×320 framebuffer, rotated to 320×480 portrait). `kiosk.sh` uses:

```
--window-size=480,320
--force-device-scale-factor=0.65
```

This gives a CSS viewport of approximately **492×738**, which all sizing in the UI is based on. Adjust the scale factor if your display or resolution differs.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/today` | All chores completed today with streak and monthly stats |
| `POST` | `/api/clean` | Record a chore (`person` + `chore` in JSON body) |
| `GET` | `/api/weekly` | Weekly totals per person and per chore (Mon–Sun) |
| `GET` | `/api/history` | All records, newest first, with chore label |
| `DELETE` | `/api/clean/<id>` | Delete a specific entry by ID |
| `POST` | `/api/reset` | Delete all records |

---

## Project structure

```
ChoreWars/
├── app.py              # Flask app and SQLite logic
├── kiosk.sh            # Launches Chromium in kiosk mode
├── start.sh            # Installs deps and starts Flask
├── requirements.txt    # Python dependencies
└── templates/
    └── index.html      # Entire frontend (HTML + CSS + JS)
```
