#!/bin/sh
# Build foxsinad_fw with arduino-cli.
#   ./build.sh setup   once: install the Arduino-Pico core and the Etherkit
#                      Si5351 library (about 500 MB). Adds the core's board
#                      URL to your arduino-cli config; never overwrites it.
#   ./build.sh         compile to build/foxsinad_fw.ino.uf2
set -e
cd "$(dirname "$0")"

FQBN="rp2040:rp2040:rpipico"
PICO_URL="https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json"

if [ "$1" = "setup" ]; then
    arduino-cli config init >/dev/null 2>&1 || true   # fails harmlessly if a config exists
    arduino-cli config get board_manager.additional_urls 2>/dev/null | grep -qF "$PICO_URL" \
        || arduino-cli config add board_manager.additional_urls "$PICO_URL"
    arduino-cli core update-index
    arduino-cli core install rp2040:rp2040
    arduino-cli lib install "Etherkit Si5351"
    exit 0
fi

arduino-cli compile --fqbn "$FQBN" --output-dir build foxsinad_fw
echo
echo "UF2: $(pwd)/build/foxsinad_fw.ino.uf2"
