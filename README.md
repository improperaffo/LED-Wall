# LED-Wall

A 128×64 RGB LED matrix on the wall, showing a clock, the MeteoSwiss forecast for Ecublens and a FlightWall-style display of the plane overhead.

A small Python server renders every frame and streams it over TCP to an ESP32. The ESP32 only puts pixels on the panel, so adding or changing screens never needs a reflash.

```
MeteoSwiss / adsb.lol ──HTTPS──> server (Python + Pillow, renders the frames)
                                    │ TCP :7777, RGB565 frames
                                    ▼
                         ESP32 (WiFi) ──HUB75──> 128×64 panel (FM6353)
```

## Screens

| Screen | Shows | Source |
|---|---|---|
| `clock` | HH:MM with a blinking colon, date, current temperature | local time, MeteoSwiss |
| `weather` | Icon, current temperature, today's min/max. Next 40 h as a temperature line with rain bars, night shading and midnight markers | MeteoSwiss app API (`plzDetail`) |
| `forecast` | Three days: weekday, icon, min/max, rain | MeteoSwiss |
| `flights` | Nearest airborne aircraft: airline (in its colour), route `GVA→SUF`, callsign, type, altitude, distance, track arrow. With an empty sky it shows "No aircraft" and the last plane seen | [adsb.lol](https://adsb.lol) + VRS route data |
| `timeline` | MeteoSwiss-style strip from the current 3-hour slot, 24 h by default and settable from 9 to 48 h (beyond about 30 h one icon covers a group of slots, flagged if any is wet): eight full-width slots (hour, icon, red **!** when rain is likely; the first labelled "now") above a temperature curve with hourly rain bars. Status line at the bottom with clock, date and the minimum temperature | MeteoSwiss (3 h icons, rain probability, hourly rain) |
| `nownext` | Big current icon and temperature, today's min/max; next five 3-hour slots with icon, temperature, rain-probability bar and % (red with **!** when likely) | MeteoSwiss |
| `rain` | Rain first: "Rain 18:00 · 4.2 mm" headline (or "Dry next 48 h"), 24 hourly rain bars with probability behind them, 3-hour icon strip | MeteoSwiss |

`timeline`, `nownext` and `rain` draw at the native 128×64. The red **!** threshold (probability % and mm per 3 h) is set on the control page.

A screen without data is skipped. A new aircraft that comes close and low can interrupt the rotation.

## Control page

The server serves a control page on port 8080, e.g. `http://pigate.local:8080`. It has no login, so keep it on the LAN or a tailnet. On the page you can:
- switch between **Rotate** (cycle through the ticked widgets in order, each for its own number of seconds) and **Single widget** (one widget stays up);
- reorder the widgets, use **Show now**, and watch a live preview of the panel;
- set how often each data source is re-fetched (weather at least every 60 s, flights at least every 5 s). A source no visible widget uses drops to polling every 5 min;
- set widget options: the Timeline's time horizon (9–48 h) and the flight search radius (10–150 km, default 40 km);
- turn flight alerts on or off;
- set **operating hours**: the days and the window during which the panel lights up (default Mon–Sat 08:00–19:00). Outside them the panel is dark and data is fetched only every 30 min. A window may run past midnight.

Changes apply immediately and auto-save to `~/.local/state/ledwall/settings.json`. That file is outside the code tree, so deploys don't touch it.

In single mode the widget's data is re-fetched at its refresh interval, and the panel redraws when the data changes. If the chosen widget has no data yet (for example, no aircraft overhead), the clock is shown instead.

The page is backed by a small JSON API:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/settings` | Settings and widget/source metadata |
| `PUT` | `/api/settings` | Update settings (partial updates allowed); returns 400 with an error message if invalid |
| `POST` | `/api/show` | `{"name": "weather"}`: jump to that widget now |
| `GET` | `/api/status` | On/off (operating hours), widget on the panel, connected panels, data age |
| `GET` | `/api/frame.png` | The current frame, rendered with an LED look |

## Hardware

- **ESP32**: a generic ESP32-WROOM devkit (ESP32-D0WD-V3, 4 MB flash, CH340 USB-serial).
- **Panel**: sold as Waveshare *RGB-Matrix-P2.5-64x32*, but the unit is **128×64 with 1/32 scan**, and its driver chips are **FM6353** (S-PWM, with their own frame memory). Standard HUB75 libraries leave this panel dark. See [Panel quirks](#panel-quirks).
- **Power**: the panel needs its own 5 V supply, at least 4 A, ideally 6–8 A. The ESP32 can run from any USB charger, or from the same 5 V supply through its 5V/VIN pin. Panel GND and ESP32 GND must be connected.

### Wiring

This follows the ESP32 diagram on Waveshare's wiki (the 64×64 one, which includes E). B is GPIO22, not the library default of 19.

| HUB75 | R1 | G1 | B1 | R2 | G2 | B2 | A | B | C | D | E | LAT | OE | CLK | GND |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPIO | 25 | 26 | 27 | 14 | 12 | 13 | 23 | 22 | 5 | 17 | 32 | 4 | 15 | 16 | GND |

The ribbon goes into the panel's **input** connector (JIN; the arrows on the PCB point away from it).

## Firmware (`firmware/`)

PlatformIO project for the Arduino core on `esp32dev`.

```sh
cp firmware/include/secrets.h.example firmware/include/secrets.h   # WiFi, server address, OTA password
cd firmware
pio run -e paneltest -t upload    # colour bars / grid / text / white, no networking: checks wiring
pio run -e ledwall   -t upload    # the real firmware, over USB
```

**Over-the-air updates.** `firmware/ota.sh` builds on the build host and pushes the image from a machine on the ESP32's LAN with `espota.py`. The hostnames and IPs in the script are the author's; adjust them. From a machine on the same LAN as the ESP32, `pio run -e ota -t upload --upload-flags="--auth=<OTA_PASS>"` also works.

**Behaviour.**
- The ESP32 connects to `SERVER_HOST:SERVER_PORT` and retries every 2 s.
- It reconnects if the server is silent for more than 10 s.
- With no server, it shows `NO SERVER` and its IP; with no WiFi, `NO WIFI`.
- It logs WiFi disconnect reasons, plus a heap/RSSI line every minute, on serial.

## Server (`server/`)

The server needs Python 3.11 or newer and Pillow; there are no other dependencies.

```sh
cd server
python3 -m ledwall            # listens on :7777
python3 preview.py            # renders every screen to preview/*.png with an LED look
python3 preview.py flights --fake-flight
```

`server/ledwall.service` is the systemd unit used in production. It sets `TZ=Europe/Zurich`, because the server host runs on UTC.

`server/config.toml` sets:
- the panel size and the ports (panel 7777, control page 8080);
- the location (postcode for MeteoSwiss, lat/lon for flights);
- the brightness schedule (day/night, 0–255);
- the flight alert rules (how close and low an aircraft must be to interrupt the rotation);
- the first-run defaults for the rotation. After the first run, the control page's settings apply.

### Adding a screen

Subclass `Screen` in `server/ledwall/screens/`. Implement `render(now)`, which returns `(image, seconds_until_next_frame)`, and optionally `ready()`. Register the screen in `ledwall/app.py`, and add it to `WIDGETS` in `ledwall/settings.py` with its label and data source. It then appears on the control page. Options the widget reads from `settings.data["options"]` are declared in `OPTIONS` in the same file, and the page lists them automatically.

Screens draw either on a 64×32 canvas, which the server scales 2× (nearest neighbour) before sending, or at the native 128×64 (`canvas((128, 64))`). Fonts are public-domain X11 BDF fonts in `server/fonts/`, converted to PIL format on first use.

### Wire protocol

| Direction | Message |
|---|---|
| server → ESP32 | `F` + W×H×2 bytes, RGB565 little-endian, row-major (sent only when the frame changes) |
| server → ESP32 | `B` + 1 byte brightness (0–255) |
| server → ESP32 | `P` ping (every 2 s when idle) |
| ESP32 → server | `H` + JSON + `\n` (hello: firmware version, IP, RSSI, MAC) |

## Panel quirks

These all cost debugging time, so they're recorded here:

- **FM6353 driver chips.** The mainline [ESP32-HUB75-MatrixPanel-DMA](https://github.com/mrcodetastic/ESP32-HUB75-MatrixPanel-DMA) can't drive them; the panel stays fully dark, even with FM6126A init. The firmware uses [LAutour's ICN2053/FM6353 fork](https://github.com/LAutour/ESP32-HUB75-MatrixPanel-DMA-ICN2053), vendored in `firmware/lib/` with patches. Every frame must be sent with `flipDMABuffer()`.
- **ISR in IRAM.** The fork's DMA interrupt ran code from flash. Registered as an IRAM interrupt, it panicked ("Cache disabled but cached memory region accessed") whenever WiFi wrote to flash. Without the IRAM flag, flash-cache misses under WiFi load scrambled rows. The vendored copy now has the whole ISR path (`getRGBColor16`, `color565to888`, the register helpers and `ICN2053_REG_CMD`) in IRAM/DRAM.
- **2.5 MHz panel clock.** Building one 128-pixel row in the ISR takes about 690 µs. At 5 MHz the DMA cycle is about 1.5 ms; that is too little slack, and garbage appears at the far (left) end of the shift chain. 2.5 MHz doubles the cycle and still refreshes at about 500 Hz. Double DMA row buffering made it worse.
- **WiFi before panel.** WiFi must be started before the panel allocates its buffers (about 73 KB of internal RAM). Otherwise WiFi never associates.
- **Gamma.** The fork maps colour channels linearly. The vendored copy applies CIE lightness per channel, so dark tones don't glow.
- **OTA.** The frame connection is closed when an update starts, because unread frames starve the OTA socket. The OTA timeout is raised from 1 s to 10 s.

## Data sources

- **Weather**: `https://app-prod-ws.meteoswiss-app.ch/v1/plzDetail?plz=<postcode>00`. This is the unofficial API behind the MeteoSwiss app, so it may change without notice. Polled every 10 min.
- **Aircraft**: `https://api.adsb.lol/v2/point/<lat>/<lon>/<nm>`, polled every 15 s. Routes come from `https://vrs-standing-data.adsb.lol/routes/<XX>/<CALLSIGN>.json`, cached for 6 h. Non-scheduled callsigns have no route, and the screen shows the callsign instead.

## Licences

- `firmware/lib/ESP32-HUB75-MatrixPanel-DMA-ICN2053/` is derived from the MIT-licensed ESP32-HUB75-MatrixPanel-DMA. The fork itself ships no licence file.
- The fonts in `server/fonts/` are the X11/public-domain BDF fonts collected in [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/fonts).
