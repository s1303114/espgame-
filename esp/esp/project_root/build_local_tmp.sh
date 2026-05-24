#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOCAL_ROOT="${LOCAL_ROOT:-$(mktemp -d /tmp/esp-mp.XXXXXX)}"
IDF_EXPORT="${IDF_EXPORT:-/opt/esp/idf/export.sh}"
BOARD="${BOARD:-ESP32_GENERIC_S3}"
BOARD_VARIANT="${BOARD_VARIANT:-SPIRAM_OCT_NOBT}"
JOBS="${JOBS:-6}"

if [[ ! -f "${IDF_EXPORT}" ]]; then
    IDF_EXPORT="${PROJECT_ROOT}/esp-idf/export.sh"
fi

mkdir -p "${LOCAL_ROOT}"

echo "Source: ${PROJECT_ROOT}/micropython"
echo "Local:  ${LOCAL_ROOT}/micropython"
echo "IDF:    ${IDF_EXPORT}"

tar -C "${PROJECT_ROOT}" \
    --exclude="micropython/ports/esp32/build-*" \
    --exclude="micropython/mpy-cross/build" \
    --exclude="*/__pycache__" \
    -cf - micropython | tar -C "${LOCAL_ROOT}" -xf -

cd "${LOCAL_ROOT}/micropython/ports/esp32"
source "${IDF_EXPORT}"

make -j"${JOBS}" \
    BOARD="${BOARD}" \
    BOARD_VARIANT="${BOARD_VARIANT}" \
    USER_C_MODULES="${LOCAL_ROOT}/micropython/user_cmodules"

echo
echo "Build OK:"
echo "${LOCAL_ROOT}/micropython/ports/esp32/build-${BOARD}-${BOARD_VARIANT}/micropython.bin"
echo
echo "Flash command:"
echo "cd ${LOCAL_ROOT}/micropython/ports/esp32"
echo "source ${IDF_EXPORT}"
echo "idf.py -B build-${BOARD}-${BOARD_VARIANT} -p /dev/ttyACM0 flash"
