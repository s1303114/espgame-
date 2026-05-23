# CAMERA 渲染說明書（目前主線）

## 1. 目前主線

目前主線是：

- `PHASE_ACCEPTANCE_STAGE = "PHASE_CAMERA_TEST"`
- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `TILEMAP_ENABLED = True`
- `FLOOR_LAYER_ENABLED = False`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL = "C_API"`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `CAMERA_FULL_BULK_WIRE_RUNTIME_SWAP = False`
- `CAMERA_FULL_BULK_DOUBLE_BUFFER = False`

提交主線目前是 **wire-order full-screen sync submit**：

- 主線標記：`SUBMIT_BYTE_ORDER=WIRE_NOSWAP`
- 主線標記：`SUBMIT_WIRE_RUNTIME_SWAP=0`
- 主線標記：`SUBMIT_MODE=SYNC_SINGLE_BUFFER_FALLBACK`
- 回退原因標記：`SUBMIT_FALLBACK_REASON=CFG_OFF`

這裡的 `SYNC_SINGLE_BUFFER_FALLBACK` 是目前刻意選擇的穩定路徑，不代表錯誤。原因是 `wire + pushImageDMA` 直接 DMA 讀 `scene_buf` 時會出現水平條碼狀花屏，且玩家 sprite 也會被背景色覆蓋；改成 `wire + pushImage` non-DMA 後畫面穩定。

目前 tilemap 資源主線：

- tileset：`game/Tilemap/tilemap_all_wire.rgb565`
- 地圖：`game/Tilemap/map1_tilemap.csv`
- far 背景：`/bg_far_wire.rgb565`
- 玩家 sprite：`/player_walk_<side>_<frame>_wire.rgb565`

所有主線 `.rgb565` 影像資產都應是 **panel wire-order**，也就是每個 RGB565 pixel 以高 byte、低 byte 的順序存放。不要在每幀提交前做 runtime byte swap。

## 2. 每幀流程

1. 讀輸入、更新 `player_x / camera_x`。
2. 在 RAM `scene_buf` 合成 far 背景。來源是 wire-order `bg_far_wire.rgb565`。
3. tilemap 合成：
   - 優先 `compose_tilemap_rgb565`（C API）
   - 使用 wire-order `tilemap_all_wire.rgb565`
   - transparent key 需依 wire-order 轉成 byte-swapped raw value
4. 玩家 sprite 合成：`compose_masked_rgb565`（C API），來源是 wire-order sprite asset。
5. 提交到 TFT：
   - 穩定主線：`blit_rect565_wire_wait`（`setSwapBytes(false)` + `pushImage` + `waitDMA`）
   - 暫不使用：`blit_rect565_wire_async` / `pushImageDMA` 直接讀 scene buffer

目前穩定提交路徑的 C++ 形態：

```cpp
lcd.startWrite();
lcd.setSwapBytes(false);
lcd.pushImage(x, y, w, h, pixels);
lcd.waitDMA();
lcd.endWrite();
```

## 3. 關鍵 API

`micropython/user_cmodules/lgfx/lgfx_mp.cpp`：

- `compose_masked_rgb565(...)`
- `compose_tilemap_rgb565(...)`
- `blit_rect565_wait(...)`：舊 little-endian + swap path
- `blit_rect565_async(...)`：舊 little-endian + swap path
- `blit_rect565_wire_wait(...)`：目前穩定主線，wire-order + non-DMA submit
- `blit_rect565_wire_async(...)`：wire-order + DMA submit，目前不作主線
- `blit_wait_done()`
- `async_probe_rgb565(...)`
- `submit_probe_rgb565(...)`
- `rgb565_swap_bytes_inplace(...)`：只保留給實驗，不作主線

`project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`：

- `--byte-order le`：舊格式，低 byte / 高 byte
- `--byte-order wire`：目前主線資產格式，高 byte / 低 byte

## 4. 觀測重點與目前瓶頸

序列埠輸出重點：

- `TILEMAP_COMPOSE_IMPL=C_API`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL=C_API`
- `SUBMIT_BYTE_ORDER=WIRE_NOSWAP`
- `SUBMIT_WIRE_RUNTIME_SWAP=0`
- `SUBMIT_MODE=SYNC_SINGLE_BUFFER_FALLBACK`
- `PROFILE submit_us=...`
- `PROFILE submit_kick_us=...`
- `PROFILE submit_wait_us=...`
- `PROFILE submit_swap_us=...`
- `PROFILE fps=...`

已測過的 full-screen submit 數據（320x240）：

| 路徑 | 結果 | 備註 |
| --- | ---: | --- |
| little-endian + `swap=true` | `submit_us ~= 37.7ms` | 舊穩定路徑，但慢 |
| wire + runtime in-place swap + DMA | `kick ~= 24.3ms`, `swap ~= 13.2ms`, 總體約 `37.6ms` | 無收益，且曾造成花屏 |
| wire asset + DMA | `submit_us ~= 24.3ms` | 快，但出現水平條碼花屏，玩家也會被背景色覆蓋 |
| wire asset + non-DMA `pushImage` | `submit_us ~= 34.3ms` | 目前穩定主線 |

目前穩定版實測：

- `submit_us` 約 `34.2~34.3ms`
- `submit_kick_us` 約 `34.2~34.3ms`
- `submit_wait_us = 0`
- `submit_swap_us = 0`
- `fps` 約 `18.6~20.9`，依 world compose 成本而變

關鍵結論：

1. wire-order asset 是有效方向，能避免 LGFX 內部 byte-swap/convert staging。
2. runtime in-place swap 不可作主線，因為每幀多約 `13.2ms`，且容易污染雙緩衝 buffer 狀態。
3. `pushImageDMA` 直接讀 Python/PSRAM scene buffer 會造成水平條碼狀花屏；推測是 DMA/cache coherency 或 PSRAM DMA 路徑一致性問題。
4. 目前穩定方案是 wire-order asset + non-DMA `pushImage` full-screen submit。
5. 若未來要恢復 `24.3ms` DMA submit，下一步應研究 DMA 前 cache writeback / memory sync，而不是再改 tilemap 或透明色。

## 4.1 已排除的畫面問題方向

曾觀察到玩家 Y 以下、tilemap 區域出現背景色水平條碼狀閃爍，且玩家 sprite 也被覆蓋。已做過 A/B：

- 關閉 tilemap transparent key：背景色條碼仍存在，且透明色粉紅會被畫出。
- 將 tilemap CSV 中 `0` tile 臨時改成 tile 1：背景色條碼仍存在，且 world compose 顯著變慢。
- 改成 wire-order non-DMA submit：條碼消失。

因此該問題不是 tilemap transparent key，也不是 CSV 空洞；是 wire DMA submit 路徑造成的資料一致性問題。

## 5. Build / Flash

主推 `/tmp` 本地鏡像流程（避免工作樹環境污染）：

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

## 6. 只部署 Python 檔

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/sd/game/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/sd/game/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 reset
```

## 7. Tilemap 細節

Tilemap 目前是主線 world 合成來源（取代舊 map1 raw 路徑）：

- 啟用：`TILEMAP_ENABLED = True`
- map1 關閉：`FLOOR_LAYER_ENABLED = False`
- tileset 路徑：`TILESET_RGB565_PATH = "game/Tilemap/tilemap_all_wire.rgb565"`
- CSV 路徑：`TILEMAP_CSV_PATH = "game/Tilemap/map1_tilemap.csv"`

資料格式：

- 地圖索引：由外部 `map1_tilemap.csv` 載入
- tile 大小：`16x16`
- index `0`：透明（不畫，保留 far_bg）
- index `1..N`：對應 tileset atlas 的 tile

目前合成實作：

1. 啟動時載入 `map1_tilemap.csv` 並轉成 `tilemap_idx`（1 byte/index）
2. 讀入 `tilemap_all_wire.rgb565`（wire-order raw RGB565 atlas）
3. 若有 C API：`compose_tilemap_rgb565(...)` -> `TILEMAP_COMPOSE_IMPL=C_API`
4. 若 C API 不可用：回退 Python 路徑 -> `TILEMAP_COMPOSE_IMPL=PYTHON`

C API 參數（主線）：

- `scene_buf, scene_w, scene_h`
- `camera_x, band_top`
- `tilemap_idx, map_w, map_h`
- `tileset_raw, tile_size, tileset_w`

板上驗證標記：

- `TILEMAP_MODE_ON`
- `TILEMAP_COMPOSE_IMPL=C_API`（主線）
- 若資源缺失：`TILEMAP_TILESET_LOAD_FAIL`
