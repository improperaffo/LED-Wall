#!/bin/sh
# Build on sensnuc3 and flash the ESP32 over WiFi from pigate (the only host on its LAN).
# Usage: firmware/ota.sh   (run from the laptop)
set -e
cd "$(dirname "$0")"
rsync -a --exclude .pio ./ sensnuc3:ledwall/firmware/
ssh sensnuc3 'cd ledwall/firmware && ~/pio/bin/pio run -e ledwall | tail -1'
scp -q -3 sensnuc3:ledwall/firmware/.pio/build/ledwall/firmware.bin pigate:ledwall/firmware.bin
scp -q -3 sensnuc3:.platformio/packages/framework-arduinoespressif32/tools/espota.py pigate:ledwall/espota.py
ssh pigate 'cd ledwall && python3 espota.py -i 192.168.0.80 -I 192.168.0.200 -a ledwall -f firmware.bin -r' \
  | tr '\r' '\n' | grep -vE '^Uploading: .* [0-9]?[0-9]% $'
