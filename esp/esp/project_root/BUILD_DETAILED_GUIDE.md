# 詳細編譯說明書（ESP32S3 + MicroPython + LGFX）

本文件提供目前專案可重現的編譯/燒錄流程，並整理 qstr 卡住與常見故障排查。

## 1. 目標與基線

目前固定基線：

- 專案根目錄：`/workspace/esp/esp`
- MicroPython port：`/workspace/esp/esp/micropython/ports/esp32`
- ESP-IDF：`/workspace/esp/esp/esp-idf`
- BOARD：`ESP32_GENERIC_S3`
- BOARD_VARIANT：`SPIRAM_OCT_NOBT`
- USER_C_MODULES：`/workspace/esp/esp/micropython/user_cmodules`
- 實體串口：`/dev/ttyACM0`

## 2. 必要條件

1. 你必須在可使用 `/dev/ttyACM0` 的環境。
2. 已有 ESP-IDF toolchain（`source export.sh` 可成功）。
3. 可用 `mpremote`（本環境建議用絕對路徑）：
   - `/tmp/mpvenv/bin/mpremote`

## 3. 一次完整流程（標準）

### 3.1 進入目錄 + 載入 IDF

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
```

### 3.2 編譯

```bash
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
```

### 3.3 燒錄

```bash
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

### 3.4 板上 Python API 快速驗證（可選）

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK'); print('HAS_WAIT', hasattr(lgfx,'blit_rect565_wait')); print('HAS_ROWS', hasattr(lgfx,'blit_rect565_rows')); print('HAS_COPY', hasattr(lgfx,'blit_rect565_wait_copy')); print('HAS_COMP', hasattr(lgfx,'compose_masked_rgb565'))"
```

## 4. 建議的「乾淨重編」流程

當你懷疑 cache 混亂（尤其 IDF_PATH 衝突）時，先 fullclean。

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT fullclean
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
```

## 5. IDF_PATH 警告說明

常見訊息：

- `IDF_PATH is changed from '/opt/esp/idf' to '/workspace/esp/esp/esp-idf'`

意義：

- 同一 build 目錄曾用另一個 IDF 路徑配置。
- 若後續出現 CMake cache 不一致或怪異錯誤，執行 `fullclean` 後重編。

## 6. qstr 階段說明與故障排查

### 6.1 qstr 是什麼

MicroPython 在 build 過程會跑 `makeqstrdefs.py`，用預處理器掃描 C/C++ 原始碼中的字串定義，產生 qstr 表。

### 6.2 如何判斷卡在 qstr

`ps` 看到長時間停在：

- `python ... makeqstrdefs.py pp ...`

且 CPU 幾乎不動、ninja 無進度。

### 6.3 先跑單步檢查

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
tools/check_qstr_single.sh
```

若輸出 `OK`，代表最基本單檔 qstr 預處理可過。

### 6.4 本專案曾遇過的 qstr 問題模式

問題特徵（歷史案例）：

- `MICROPY_HW_BOARD_NAME` 被錯誤展開成多個 token，導致 preprocess 參數破碎。

避免方式：

- 確認 board variant 的定義在 CMake 是完整字串，不要被拆成不合法參數。
- 變更 board/variant 定義後，建議 `fullclean` 再編。

## 7. 常用診斷命令

### 7.1 看目前分支與版本

```bash
cd /workspace/esp/esp
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD
git log --oneline -n 5
```

### 7.2 看 build 是否仍在跑

```bash
ps -eo pid,ppid,stat,etime,pcpu,pmem,cmd | rg "idf.py|ninja all|makeqstrdefs.py pp|make -j"
```

### 7.3 停掉卡住的 build

```bash
pkill -f "makeqstrdefs.py pp|ninja all|make -j6 BOARD=ESP32_GENERIC_S3|idf.py -D MICROPY_BOARD=ESP32_GENERIC_S3"
```

## 8. 燒錄失敗排查

### 8.1 連接失敗 / 端口被占用

錯誤示例：

- `failed to access /dev/ttyACM0 (it may be in use by another program)`

處理：

1. 關掉佔用 serial 的程式（mpremote repl、monitor、IDE serial monitor）。
2. 重新跑 flash。

### 8.2 寫入後驗證

成功訊號：

- `Hash of data verified.`（三段映像）
- `Hard resetting via RTS pin... Done`

## 9. Runtime 檔案快速部署（不重編）

只改 Python 腳本時，建議直接上板：

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/sd/game/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/sd/game/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 reset
```

為什麼同時寫 `/sd/game` 與 `/`：

- 板子啟動來源可能是 SD 或 root，雙寫可避免來源不一致。

## 10. 與目前渲染主線對齊檢查

確認目前模式（以本專案現況）：

```bash
rg -n "PHASE_ACCEPTANCE_STAGE|CAMERA_TEST_MODE|CAMERA_SPI_TEST_PATH" /workspace/esp/esp/project_root/sd_game_template/game/config.py
```

序列埠確認關鍵字：

- `APP_RUN_START_PHASE_CAMERA_TEST`
- `CAMERA_TEST_MODE=...`
- `FULLSCREEN_BULK_SUBMIT_OK`（若使用 map1 + full bulk 主線）
- `PROFILE fps=...`

## 11. 一鍵流程（可直接貼上）

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT fullclean
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK')"
```

## 12. 成功完成的判準

你可以把一次任務視為「完成」的最低條件：

1. build 成功（產生 `micropython.bin`）
2. flash 成功（hash verified + reset done）
3. 板上可 `import lgfx`
4. 目標模式在序列埠可見（例如 `CAMERA_TEST_MODE=...`）
