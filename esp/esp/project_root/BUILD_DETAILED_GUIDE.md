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
- 只改 SD 上的遊戲 Python、地圖、圖片或 config

只改 Python runtime 或圖片資產時，使用第 10 節 SD-only 部署即可。

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
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK'); print('HAS_WAIT', hasattr(lgfx,'blit_rect565_wait')); print('HAS_COMP', hasattr(lgfx,'compose_colorkey_rgb565')); print('HAS_BAND', hasattr(lgfx,'render_scene_bands_rgb565'))"
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

若 `build_local_tmp.sh` 本身卡在 `/workspace -> /tmp` 複製階段，但你只改了少數幾個 user_cmodule 檔案，可以直接同步到現有 `/tmp/esp-mp-local` 後增量重編，例如：

```bash
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_mp.cpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_mp.cpp
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_band.cpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_band.cpp
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_shared.hpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_shared.hpp

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/tmp/esp-mp-local/micropython/user_cmodules
```

重點是「所有改過的檔案都要同步」。這次已實際踩到一個陷阱：只同步 `lgfx_band.cpp` / `lgfx_shared.hpp`，漏掉 `lgfx_mp.cpp`，會導致 firmware 雖然刷進新的 native band renderer，但板上 `lgfx` 模組仍然沒有匯出 `render_scene_bands_rgb565`，開機就會一直走 `BAND_PIPELINE_NATIVE_FALLBACK`。

這種情況先不要猜 qstr 壞掉，先直接在板上檢查：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx
print('HAS_RENDER_SCENE_BANDS', hasattr(lgfx, 'render_scene_bands_rgb565'))
print('HAS_NAME', 'render_scene_bands_rgb565' in dir(lgfx))"
```

若兩個都不是 `True`，代表你目前刷進去的 firmware export table 還是舊的，先回頭檢查 `/tmp` 本地鏡像是否漏同步。

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

如果 `build_local_tmp.sh` 是卡在這個階段，而不是卡在編譯本身，那就不要在同一個卡住的 `/workspace` build 上繼續猜測 C++ 錯誤；直接停掉它，改用上面那種「同步到既有 `/tmp/esp-mp-local` 再重編」的流程會更快。

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

## 10. SD-only Runtime 部署（不重編）

目前主線是 **SD-only launcher**：

- 內部 flash 只需要 `boot.py` 與 `main.py`。
- 遊戲程式與圖片資產都放在 SD 卡 `/sd/game`。
- 開機時 `main.py` 掛載 SD，驗證 `/sd/game/app.py`、`/sd/game/config.py`、`/sd/game/app_camera_test.py` 都存在。
- 驗證通過後，launcher 直接 `exec` `/sd/game/config.py` 與 `/sd/game/app_camera_test.py`。
- `/sd/game/app.py` 目前只作為 wrapper / 存在性檢查備用，不是正式主執行檔。
- 沒有 SD 卡、或上述必要檔案缺失時，會進入 safe mode，不會跑內部 flash 舊遊戲。

### 10.1 更新內部 flash launcher

`mpremote fs cp` 不支援一行把兩個來源分別寫到兩個目標，請逐檔複製：

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp boot.py :boot.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp main.py :main.py
```

### 10.2 掛載 SD 並同步 game

這一段有一個這次實機已確認的陷阱：

- `os.listdir('/sd')` 不能拿來判斷「外接 SD 已掛載」，因為板上內部檔案系統本身就可能存在 `/sd` 目錄。
- `mpremote fs cp ... :/sd/...` 顯示成功，甚至顯示 `Up to date`，也不代表真的寫到了外接 SD 卡。
- 判斷是否真的寫到外接 SD，唯一可信的方法是：**寫入後 `umount` 再 `mount`，重新讀檔確認內容仍然是新版。**

因此，標準做法不要先用 `os.listdir('/sd')` 判斷，而是先強制重掛載，再用同一個已掛載 session 複製檔案。

### 10.2.1 強制掛載外接 SD

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import machine, os
try:
    os.umount('/sd')
    print('PRE_UMOUNT_OK')
except Exception as e:
    print('PRE_UMOUNT_SKIP', e)
try:
    os.mount(machine.SDCard(slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000), '/sd')
    print('SD_MOUNTED_SLOT2_ACTUAL')
except Exception as e1:
    print('SD_MOUNT_SLOT2_ERR', e1)
    raise
"
```

看到 `SD_MOUNTED_SLOT2_ACTUAL` 才算真的把外接 SD 掛上去。這是目前板子實際使用的 pin mapping：`slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000`。

目前正式唯一 SD 路徑就是 internal flash launcher [main.py](/workspace/esp/esp/project_root/main.py) 這組 wiring：`slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000`。文件、手動部署、boot 掛載都必須使用同一組設定；不要再保留或混用舊 pin 範例。

### 10.2.2 用同一個 session 逐檔同步

這次實測中，逐檔複製最穩定，也比較容易判斷是哪個檔案沒有更新：

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/app.py :/sd/game/app.py
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/app_camera_test.py :/sd/game/app_camera_test.py
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/config.py :/sd/game/config.py
```

如果要同步更多資產或整包目錄，可以另外做，但核心啟動鏈至少先確認上述檔案已經真的寫入外接 SD。

如果這次改的是 native overlay / native band 相關 Python 路徑，建議至少同步：

- `sd_game_template/game/app.py`
- `sd_game_template/game/app_camera_test.py`
- `sd_game_template/game/config.py`
- `sd_game_template/game/sd_config.py`（若使用 SD 專用入口且語法檢查通過）

若只改 object 資產，最小同步集合是：

- `sd_game_template/game/picture/object/objects.csv`
- `sd_game_template/game/picture/object/objects_atlas_wire.rgb565`

建議仍然使用同一個已掛載 session：

```bash
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/picture/object/objects.csv :/sd/game/picture/object/objects.csv
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/picture/object/objects_atlas_wire.rgb565 :/sd/game/picture/object/objects_atlas_wire.rgb565
```

### 10.2.3 重掛載驗證是否真的寫入外接 SD

不要只看 `cp` 的輸出。請立刻做一次 `umount -> mount -> read back`：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import os, machine
try:
    os.umount('/sd')
except Exception:
    pass
os.mount(machine.SDCard(slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000), '/sd')
with open('/sd/game/app_camera_test.py', 'r') as f:
    s = f.read()
with open('/sd/game/config.py', 'r') as f:
    c = f.read()
print('REMOUNT_V2_START', 'APP_RUN_START_PHASE_CAMERA_TEST_V2' in s)
print('REMOUNT_V2_FAR', 'SWAP_FAR_OK_V2' in s)
print('REMOUNT_BTN_A_39', 'BTN_A_PIN = 39' in c)
print('REMOUNT_BTN_B_40', 'BTN_B_PIN = 40' in c)
print('REMOUNT_BTN_X_38', 'BTN_X_PIN = 38' in c)
"
```

若要驗證 object 資產是否真的上到外接 SD，可以改成：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import os, machine
try:
    os.umount('/sd')
except Exception:
    pass
os.mount(machine.SDCard(slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000), '/sd')
s = open('/sd/game/picture/object/objects.csv', 'r').read()
print('HAS_MUSHROOM', 'mushroom,decor,1168,160,16,16' in s)
print('HAS_BOX', 'box,decor,1392,96,32,32' in s)
print('HAS_MINECART', 'minecart,decor,1360,160,32,32' in s)
print('ATLAS_SIZE', os.stat('/sd/game/picture/object/objects_atlas_wire.rgb565')[6])"
```

若要驗證 native overlay 版本是否真的上到外接 SD，可以把 readback 改成檢查：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import os, machine
try:
    os.umount('/sd')
except Exception:
    pass
os.mount(machine.SDCard(slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000), '/sd')
app = open('/sd/game/app_camera_test.py', 'r').read()
print('APP_HAS_NATIVE_OVERLAY_PACK', '_pack_special_render_overlays' in app)
print('APP_CALLS_NATIVE_OVERLAY', 'overlay_desc_buf,' in app)"
```

只要重掛載後檔案內容又變回舊版，就表示你剛才沒有真的寫到外接 SD，而是寫到了別的地方或用了錯的 session 狀態。

### 10.3 reset 與來源驗證

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 reset
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 repl
```

正常啟動後 log 會看到遊戲主線輸出，例如：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `PROFILE fps=...`
- `APP_RUN_START_PHASE_CAMERA_TEST`

如果你剛剛有在修改按鍵邏輯、啟動 wrapper 或 launcher，建議在程式裡保留一個容易辨識的 startup marker，然後 reset 後直接看 UART。例如這次使用過：

- `RUNTIME_APP_CAMERA_TEST_DEBUG_V2`
- `APP_RUN_START_PHASE_CAMERA_TEST_V2`

如果 reset 後看不到這些 marker，就不要先懷疑邏輯沒改到，先回頭檢查第 10.2.3 節，確認外接 SD 上的檔案是否真的更新成功。

若要確認目前載入來源，優先看開機 log：

```text
LOADER_SRC_PATH=/sd/game/app_camera_test.py
LAUNCHER_APP_FILE=/sd/game/app_camera_test.py
```

這兩行是目前主線最直接的來源證據，因為 launcher 直接 `exec` 的 module 是 `app_camera_test`。

若要在 REPL 裡再次確認，按 `Ctrl-C` 中斷後輸入：

```python
import sys, config
print('APP_CAMERA_TEST_FILE', sys.modules['app_camera_test'].__file__)
print('BG_PATH', config.CAMERA_TEST_ROOT_BG_FAR_RGB565)
```

成功條件：

```text
APP_CAMERA_TEST_FILE /sd/game/app_camera_test.py
BG_PATH /sd/game/picture/backgound/bg_far_wire.rgb565
```

注意：若你是用 `reset` 之後再晚一點才 attach REPL，最前面的 startup marker 可能已經滾過 UART。這種情況不要只因為「沒看到某一行」就判定沒載入新版；先回到第 10.2.3 節做 `umount -> mount -> read back`，再配合上面的 loader log/source 檢查。

### 10.4 SD 卡目錄結構

SD 卡根目錄應有：

```text
/sd/game/
  app.py
  app_camera_test.py
  config.py
  assets.py
  state.py
  actors/
  engine/
  save/
  Tilemap/map_tilemap.csv
  Tilemap/tilemap_all_wire.rgb565
  picture/backgound/bg_far_wire.rgb565
  picture/object/objects.csv
  picture/object/object_animations.json
  picture/object/objects_atlas_wire.rgb565
  picture/enemy/enemies.csv
  picture/enemy/enemy_bow_animation_wire.rgb565
  picture/player/player_wire.rgb565
  picture/spawn/Resurrection_Anchor_wire.rgb565
  picture/spawn/Spawnpoint_rock_wire.rgb565
```

目前乾淨主線的 internal flash 應只保留 `boot.py` 與 `main.py`。`main.py` 不會載入 internal flash 舊遊戲檔；所有實際程式與資產都應以 `/sd/game` 為準。

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
rg -n "CAMERA_TEST_MODE|CAMERA_TEST_STEP|CAMERA_SPI_TEST_DBG_EVERY" /workspace/esp/esp/project_root/sd_game_template/game/config.py
```

序列埠確認關鍵字：

- `LOADER_SRC_PATH=/sd/game/app_camera_test.py`
- `LAUNCHER_APP_FILE=/sd/game/app_camera_test.py`
- `APP_RUN_START_PHASE_CAMERA_TEST`
- `CAMERA_TEST_MODE=...`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `PROFILE fps=...`

## 14. 一鍵流程（可直接貼上）

### 14.1 編譯 + 燒錄 + launcher/SD 部署 + import 驗證

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('LGFX_IMPORT_OK')"

cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp boot.py :boot.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp main.py :main.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import machine, os
try:
    os.umount('/sd')
    print('PRE_UMOUNT_OK')
except Exception as e:
    print('PRE_UMOUNT_SKIP', e)
try:
    os.mount(machine.SDCard(slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000), '/sd')
    print('SD_MOUNTED_SLOT2_ACTUAL')
except Exception as e1:
    print('SD_MOUNT_SLOT2_ERR', e1)
    raise
"
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/app.py :/sd/game/app.py
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/app_camera_test.py :/sd/game/app_camera_test.py
/tmp/mpvenv/bin/mpremote resume fs cp sd_game_template/game/config.py :/sd/game/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 reset
```

如果 `/sd/game` 沒出現，或 reset 後仍然跑舊版，回到第 10.2 節，使用「強制掛載外接 SD -> 同一 session 逐檔同步 -> 重掛載驗證」的流程重新部署。

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
4. SD 來源確認為 `/sd/game/app_camera_test.py`
5. 目標模式在序列埠可見，例如 `CAMERA_TEST_MODE=...`


## 15. Native band pipeline 檢查

部署後若 FPS 或畫面不符合預期，先確認板上 firmware 與 SD 檔案版本一致：

```bash
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 exec "import lgfx; print('HAS_RENDER_SCENE_BANDS', hasattr(lgfx, 'render_scene_bands_rgb565'))"
```

開機 log 應看到：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`

目前實機量測中，`CAMERA_BAND_PIPELINE_H = 48` 比 `40 / 32 / 24 / 56` 更佳，且在起始區域與 monk 區域都勝出，是目前建議固定的主線值。

若缺少 `render_scene_bands_rgb565`，代表 firmware 仍是舊版或 `/tmp/esp-mp-local` 漏同步 `lgfx_mp.cpp` / `lgfx_band.cpp` / `lgfx_shared.hpp`。

目前主線仍以 `main.py` 直接 `exec` `/sd/game/config.py` 與 `/sd/game/app_camera_test.py` 為準；`/sd/game/app.py` 只作為存在性檢查與 wrapper 備用。

若這次修改的是 panel bus / DMA 相關 firmware 參數，例如 `micropython/user_cmodules/lgfx/lgfx_config.hpp` 內的 `cfg.freq_write`，也要記得同步該檔到 `/tmp/esp-mp-local` 再重編；只同步 `lgfx_mp.cpp` / `lgfx_band.cpp` 不足以反映 bus clock 變更。

目前實機驗證過：

- `CAMERA_BAND_PIPELINE_H = 48` 是正式主線 band 高度
- `lgfx_config.hpp` 的 `cfg.freq_write = 40000000` 是目前正式主線 SPI write clock
- `80MHz` 雖可把 `submit_us` 明顯壓低、FPS 拉到約 `31.6`，但畫面會撕裂
- 因此目前主線固定維持 `40MHz`，不要把 `80MHz` 當成預設 baseline
