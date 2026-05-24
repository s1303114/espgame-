# 詳細編譯說明書（ESP32S3 + MicroPython + LGFX）

本文件提供目前專案可重現的編譯、燒錄、驗證流程，並整理 qstr 卡住與常見故障排查。

目前標準做法是：**不要直接在 `/workspace` 編譯 firmware**，而是先複製 MicroPython 原始碼到 Linux 本機 `/tmp`，再在 `/tmp` 編譯。這可以避開 `/workspace` 掛在 Windows `C:\` 時的 9p I/O 卡住問題。

## 1. 目標與基線

目前固定基線：

- 專案根目錄：`/workspace/esp/esp`
- 編譯入口腳本：`/workspace/esp/esp/project_root/build_local_tmp.sh`
- 建議本機編譯根目錄：`/tmp/esp-mp-local`
- 實際 MicroPython port：`/tmp/esp-mp-local/micropython/ports/esp32`
- ESP-IDF（建議）：`/opt/esp/idf`
- ESP-IDF（備援）：`/workspace/esp/esp/esp-idf`
- BOARD：`ESP32_GENERIC_S3`
- BOARD_VARIANT：`SPIRAM_OCT_NOBT`
- USER_C_MODULES：`/tmp/esp-mp-local/micropython/user_cmodules`
- 實體串口：`/dev/ttyACM0`

重要原則：

- `/workspace` 可能是 Windows `C:\` 掛載，MicroPython qstr 階段會大量掃描小檔案，容易卡住。
- firmware 編譯一律優先用 `/tmp` 本機副本。
- 只改 Python runtime 檔案時，不需要重編 firmware，直接用 `mpremote` 部署。

## 2. 必要條件

1. 你必須在可使用 `/dev/ttyACM0` 的環境。
2. 已有 ESP-IDF toolchain，且 `source /opt/esp/idf/export.sh` 可成功。
3. 可用 `mpremote`（本環境建議用絕對路徑）：
   - `/tmp/mpvenv/bin/mpremote`
4. 若 `/dev/ttyACM0` 權限不足，需調整容器/主機 USB 權限，或確認板子已正確接入。

確認目前 `/workspace` 是否是 Windows 掛載：

```bash
df -h /workspace
```

如果看到 `C:\`，不要直接在 `/workspace/esp/esp/micropython/ports/esp32` 編譯。

## 3. 什麼時候需要重編 firmware

需要重編：

- 改了 `micropython/user_cmodules/lgfx/lgfx_mp.cpp`
- 改了 `micropython/user_cmodules` 下的 C/C++ module
- 改了 board config、CMake、MicroPython C/C++ 原始碼
- 改了需要包進 firmware 的 frozen module 或底層設定

不需要重編：

- 只改 `project_root/sd_game_template/game/*.py`
- 只改遊戲 JSON、地圖、config、存檔模板
- 只改 SD/root runtime 檔案

只改 Python runtime 時，使用第 10 節部署即可。

## 4. 目前標準編譯流程（推薦）

### 4.1 一行編譯

固定使用 `/tmp/esp-mp-local`，方便後續增量編譯：

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh
```

若不指定 `LOCAL_ROOT`，腳本會自動建立新的暫存目錄，例如 `/tmp/esp-mp.xxxxxx`：

```bash
cd /workspace/esp/esp/project_root
./build_local_tmp.sh
```

### 4.2 腳本實際做了什麼

`build_local_tmp.sh` 會：

1. 以 `/workspace/esp/esp` 作為來源專案根目錄。
2. 將 `micropython` 複製到 `${LOCAL_ROOT}/micropython`。
3. 排除來源端舊 build 產物：
   - `micropython/ports/esp32/build-*`
   - `micropython/mpy-cross/build`
   - `*/__pycache__`
4. 進入 `${LOCAL_ROOT}/micropython/ports/esp32`。
5. 優先載入 `/opt/esp/idf/export.sh`。
6. 執行：

```bash
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=${LOCAL_ROOT}/micropython/user_cmodules
```

### 4.3 成功產物

固定 `LOCAL_ROOT=/tmp/esp-mp-local` 時，成功後 firmware 在：

```text
/tmp/esp-mp-local/micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT/micropython.bin
```

成功訊號通常會包含：

- `Project build complete.`
- `Generated .../micropython.bin`
- `micropython.bin binary size ...`

## 5. 燒錄流程

編譯成功後：

```bash
cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

成功訊號：

- `Hash of data verified.`
- `Hard resetting via RTS pin... Done`

如果腳本沒有指定 `LOCAL_ROOT`，請使用腳本最後輸出的 `cd ...` 路徑與 flash command。

## 6. 板上快速驗證

燒錄完成後，確認 `lgfx` module 可 import：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK'); print('HAS_WAIT', hasattr(lgfx,'blit_rect565_wait')); print('HAS_ROWS', hasattr(lgfx,'blit_rect565_rows')); print('HAS_COPY', hasattr(lgfx,'blit_rect565_wait_copy')); print('HAS_COMP', hasattr(lgfx,'compose_masked_rgb565'))"
```

最低成功條件：

- 看見 `LGFX_IMPORT_OK`
- 需要的 API 顯示 `True`

## 7. 乾淨重編流程

### 7.1 推薦乾淨重編

若固定用 `/tmp/esp-mp-local`，完整清掉 cache 後重編：

```bash
rm -rf /tmp/esp-mp-local
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh
```

### 7.2 不清 cache 的增量重編

改完 `lgfx_mp.cpp` 後，直接重跑：

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh
```

腳本會重新複製原始碼到 `/tmp/esp-mp-local`，既有 build 目錄會保留，因此通常會走增量編譯。

### 7.3 使用新暫存目錄重編

如果不想碰舊 cache：

```bash
cd /workspace/esp/esp/project_root
./build_local_tmp.sh
```

腳本會建立新的 `/tmp/esp-mp.xxxxxx`。

## 8. 為什麼不要直接在 /workspace 編譯

直接在 `/workspace/esp/esp/micropython/ports/esp32` 編譯時，如果 `/workspace` 是 Windows `C:\` 掛載，常見卡住點：

- `Generating .../genhdr/qstr.i.last`
- `python ... makeqstrdefs.py pp ...`
- `cc1` 進入 `D` state
- `WCHAN` 顯示 `p9_cli`

診斷命令：

```bash
df -h /workspace
ps -eo pid,ppid,stat,wchan,etime,pcpu,pmem,cmd | rg "makeqstrdefs|cc1|ninja all|idf.py|make -j"
```

如果看到 `C:\` 和 `p9_cli`，這是 Windows/9p 掛載 I/O 問題，不是 `lgfx_mp.cpp` 或 qstr 定義壞掉。處理方式是停掉卡住的 build，改用第 4 節 `/tmp` 本機編譯。

## 9. 卡住時如何停止 build

查看 build 是否仍在跑：

```bash
ps -eo pid,ppid,stat,wchan,etime,pcpu,pmem,cmd | rg "idf.py|ninja all|makeqstrdefs.py pp|make -j|cc1"
```

停止卡住的 build：

```bash
pkill -f "makeqstrdefs.py pp|ninja all|make -j6 BOARD=ESP32_GENERIC_S3|idf.py -D MICROPY_BOARD=ESP32_GENERIC_S3|cc1"
```

確認沒有殘留：

```bash
pgrep -af "makeqstrdefs|ninja all|idf.py|make -j|cc1"
```

## 10. Runtime 檔案快速部署（不重編）

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

## 11. 直接在原路徑編譯（備援，不建議用於 Windows 掛載）

只有在 `df -h /workspace` 確認 `/workspace` 是 Linux 原生檔案系統時，才使用這個流程：

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
```

燒錄：

```bash
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

若 `/workspace` 顯示 `C:\`，不要使用本節流程。

## 12. IDF_PATH 警告說明

常見訊息：

- `IDF_PATH is changed from '/opt/esp/idf' to '/workspace/esp/esp/esp-idf'`

意義：

- 同一 build 目錄曾用另一個 IDF 路徑配置。
- `/tmp` 標準流程使用 `/opt/esp/idf`。
- 舊 `/workspace` build 目錄可能使用 `/workspace/esp/esp/esp-idf`。
- 若後續出現 CMake cache 不一致或怪異錯誤，清掉該 build 目錄後重編。

對目前標準流程而言，固定用 `/tmp/esp-mp-local` + `/opt/esp/idf` 即可避免反覆切換 IDF_PATH。

## 13. 與目前渲染主線對齊檢查

確認目前模式（以本專案現況）：

```bash
rg -n "CAMERA_TEST_MODE|CAMERA_SPI_TEST_PATH" /workspace/esp/esp/project_root/sd_game_template/game/config.py
```

序列埠確認關鍵字：

- `APP_RUN_START_PHASE_CAMERA_TEST`
- `CAMERA_TEST_MODE=...`
- `FULLSCREEN_BULK_SUBMIT_OK`（若使用 map1 + full bulk 主線）
- `PROFILE fps=...`

## 14. 一鍵流程（可直接貼上）

### 14.1 編譯 + 燒錄 + import 驗證

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK')"
```

### 14.2 只編譯不燒錄

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh
```

### 14.3 只燒錄既有 /tmp 產物

```bash
cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

## 15. 成功完成的判準

你可以把一次 firmware 任務視為完成的最低條件：

1. build 成功，產生 `micropython.bin`
2. flash 成功，出現 hash verified + reset done
3. 板上可 `import lgfx`
4. 目標模式在序列埠可見，例如 `CAMERA_TEST_MODE=...`
