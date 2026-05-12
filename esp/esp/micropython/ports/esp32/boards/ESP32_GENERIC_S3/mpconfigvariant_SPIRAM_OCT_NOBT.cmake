set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.spiram_sx
    boards/ESP32_GENERIC_S3/sdkconfig.board
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram_oct
    boards/ESP32_GENERIC_S3/sdkconfig.nobt
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="Generic ESP32S3 module with Octal-SPIRAM (NoBT)"
    MICROPY_PY_BLUETOOTH=0
)
