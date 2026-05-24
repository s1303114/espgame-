# CAMERA 渲染說明書（目前主線）

## 1. 目前主線

目前主線是：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `TILEMAP_ENABLED = True`
- `FLOOR_LAYER_ENABLED = False`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL = "C_API"`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `CAMERA_FULL_BULK_WIRE_RUNTIME_SWAP = False`
- `CAMERA_FULL_BULK_DOUBLE_BUFFER = True`

目前板上互動主線狀態：

- X 鍵觸發 far swap，Y 鍵觸發 near swap。
- swap 使用邊緣觸發與 `SWAP_MIN_INTERVAL_MS` 間隔，避免按鍵連點或長按造成重複觸發。
- far/near swap 都走直接交換流程，不做碰撞回滾；找不到目標只輸出 `SWAP_FAIL_NO_TARGET`。
- 玩家重力由 `PLAYER_GRAVITY` 與 `PLAYER_FALL_SPEED_MAX` 控制。
- object 重力由 `OBJECT_GRAVITY_ENABLED` 與 `OBJECT_GRAVITY_STEP` 控制，每幀把可見 object 往地面推進。
- tilemap、object、player sprite 都優先走 C API compose，透明 colorkey 判斷在 C++ 端完成。
- 內部 flash 的 `main.py` 是 SD-only launcher；遊戲程式與資產都由 `/sd/game` 載入。

提交主線目前是 **wire-order full-screen async DMA submit + cache sync**：

- 主線標記：`SUBMIT_BYTE_ORDER=WIRE_NOSWAP`
- 主線標記：`SUBMIT_WIRE_RUNTIME_SWAP=0`
- 主線標記：`SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE`

`blit_rect565_wire_async` 在 `pushImageDMA` 前會先對 source buffer 做 CPU-to-memory cache sync：

```cpp
esp_cache_msync(
    (void *)pixels,
    expected_len,
    ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
);
```

這是目前拿回 DMA 效能且保持畫面穩定的關鍵。未做 cache sync 的 wire DMA 會出現水平條碼狀花屏，且玩家 sprite 可能被背景色覆蓋。

目前 tilemap 資源主線：

- tileset：`game/Tilemap/tilemap_all_wire.rgb565`
- 地圖：`game/Tilemap/map1_tilemap.csv`
- far 背景：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- 玩家 sprite：`/sd/game/picture/player/player_wire.rgb565`

所有主線 `.rgb565` 影像資產都應是 **panel wire-order**，也就是每個 RGB565 pixel 以高 byte、低 byte 的順序存放。不要在每幀提交前做 runtime byte swap。


## SD-only 啟動與部署

內部 flash 只保留最小 launcher：

- `/boot.py`
- `/main.py`

遊戲程式與資產放在 SD 卡：

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
  Tilemap/map1_tilemap.csv
  Tilemap/tilemap_all_wire.rgb565
  picture/backgound/bg_far_wire.rgb565
  picture/object/objects.csv
  picture/object/objects_atlas_wire.rgb565
  picture/player/player_wire.rgb565
```

開機後 `main.py` 會掛載 SD 卡並直接從 `/sd/game/app.py` 啟動；沒有 SD 卡或 SD 上缺少 `app.py` 時會進入 safe mode。

## 2. 每幀流程

1. 讀輸入、更新 `player_x / camera_x`。
2. 在 RAM `scene_buf` 合成 far 背景。來源是 wire-order `bg_far_wire.rgb565`。
3. tilemap 合成：
   - 優先 `compose_tilemap_rgb565`（C API）
   - 使用 wire-order `tilemap_all_wire.rgb565`
   - transparent key 需依 wire-order 轉成 byte-swapped raw value
4. 玩家 sprite 合成：`compose_masked_rgb565`（C API），來源是 wire-order sprite asset。
5. 提交到 TFT：
   - 主線：`blit_rect565_wire_async`（cache sync + `setSwapBytes(false)` + `pushImageDMA`）
   - 下一幀開始前：若上一幀仍 in-flight，呼叫 `blit_wait_done()`
   - 回退穩定路徑：`blit_rect565_wire_wait`（`setSwapBytes(false)` + `pushImage` + `waitDMA`）

目前主線提交路徑的 C++ 形態：

```cpp
esp_cache_msync(
    (void *)pixels,
    expected_len,
    ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
);
lcd.startWrite();
lcd.setSwapBytes(false);
lcd.pushImageDMA(x, y, w, h, pixels);
```

## 3. 關鍵 API

`micropython/user_cmodules/lgfx/lgfx_mp.cpp`：

- `compose_masked_rgb565(...)`
- `compose_tilemap_rgb565(...)`
- `blit_rect565_wait(...)`：舊 little-endian + swap path
- `blit_rect565_async(...)`：舊 little-endian + swap path
- `blit_rect565_wire_async(...)`：目前主線，wire-order + cache sync + DMA submit
- `blit_rect565_wire_wait(...)`：穩定回退路徑，wire-order + non-DMA submit
- `blit_wait_done()`
- `async_probe_rgb565(...)`
- `submit_probe_rgb565(...)`
- `rgb565_swap_bytes_inplace(...)`：只保留給實驗，不作主線

`project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`：

- `--byte-order le`：舊格式，低 byte / 高 byte
- `--byte-order wire`：目前主線資產格式，高 byte / 低 byte

## 3.1 RGB565 資產轉檔規格

主工具檔案：

- `/workspace/esp/esp/project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`

工具輸出格式：

- 輸出是 raw RGB565，row-major，沒有 header。檔案大小必須等於 `width * height * 2`。
- `--byte-order le`：每個 pixel 輸出 little-endian byte order，也就是 `lo, hi`。這是舊 `setSwapBytes(true)` 路徑使用的格式。
- `--byte-order wire`：每個 pixel 輸出 panel wire-order，也就是 `hi, lo`。這是目前主線 `blit_rect565_wire_async` 使用的格式。
- `--preview <png>` 只會額外輸出解碼預覽 PNG，不會改變 `.rgb565` 本體格式。

透明規則：

- 轉檔工具本身不讀 alpha，也不把透明像素改寫成特殊 metadata；輸入 PNG 會先轉成 RGB。
- 專案目前使用 magenta `#FF00FF` 作為 colorkey 顏色。RGB565 語意值是 `0xF81F`。
- 若輸出 `--byte-order le`，檔案 bytes 是 `1F F8`，C compose 傳入/比較的 16-bit key 是 `0xF81F`。
- 若輸出 `--byte-order wire`，檔案 bytes 是 `F8 1F`。因目前 C compose 以 raw little-endian 16-bit 讀 buffer，比較用 key 需 byte-swap，最終傳入值是 `0x1FF8`。
- 目前主線是 wire-order，所以 tilemap transparent key 在 `app_camera_test.py` 會從 `0xF81F` 轉成 `0x1FF8` 後傳給 `compose_tilemap_rgb565(...)`。

metadata 與 layout：

- `.rgb565` 檔案本身沒有額外 metadata，沒有寬高、frame count、atlas layout 或透明設定。這些都由檔名、`config.py` 與載入端約定。
- far 背景目前由 `CAMERA_TEST_ROOT_BG_FAR_RGB565 = "/sd/game/picture/backgound/bg_far_wire.rgb565"` 指定，尺寸約定是 `CAMERA_TEST_FAR_W x CAMERA_TEST_MAP_H = 320x240`。
- tileset atlas 目前由 `TILESET_RGB565_PATH = "game/Tilemap/tilemap_all_wire.rgb565"` 指定，尺寸由 `TILESET_ATLAS_W = 128`、`TILESET_ATLAS_H = 128` 指定。
- tile 大小是 `TILE_SIZE = 16`，所以目前 atlas layout 是 `8 x 8` tiles，row-major 排列。tilemap CSV index `0` 是透明，index `1` 對應 atlas 第一格，之後依 row-major 遞增。
- 玩家 sprite 目前由 `CAMERA_PLAYER_SPRITESHEET_PATH = "/sd/game/picture/player/player_wire.rgb565"` 指定，spritesheet 尺寸與 frame 佈局由載入端約定。

## 4. 觀測重點與目前瓶頸

序列埠輸出重點：

- `TILEMAP_COMPOSE_IMPL=C_API`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL=C_API`
- `SUBMIT_BYTE_ORDER=WIRE_NOSWAP`
- `SUBMIT_WIRE_RUNTIME_SWAP=0`
- `SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE`
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
| wire asset + DMA，無 cache sync | `submit_us ~= 24.3ms` | 快，但出現水平條碼花屏，玩家也會被背景色覆蓋 |
| wire asset + non-DMA `pushImage` | `submit_us ~= 34.3ms` | 穩定回退路徑 |
| wire asset + DMA + `esp_cache_msync` | `submit_us ~= 24.5ms` | 目前主線，畫面正常 |

目前主線實測：

- `submit_us` 約 `24.5~24.6ms`
- `submit_kick_us` 約 `24.5~24.6ms`
- `submit_wait_us` 約 `5.9~6.0ms`
- `submit_swap_us = 0`
- `fps` 約 `20.0~22.4`，依 world compose 成本而變

關鍵結論：

1. wire-order asset 是有效方向，能避免 LGFX 內部 byte-swap/convert staging。
2. runtime in-place swap 不可作主線，因為每幀多約 `13.2ms`，且容易污染雙緩衝 buffer 狀態。
3. `pushImageDMA` 直接讀 Python/PSRAM scene buffer 若不做 cache sync，會造成水平條碼狀花屏；原因是 DMA/cache coherency 或 PSRAM DMA 路徑一致性問題。
4. 目前正式方案是 wire-order asset + `esp_cache_msync` + DMA full-screen submit。
5. non-DMA `pushImage` 保留為穩定回退路徑。

## 4.1 已排除的畫面問題方向

曾觀察到玩家 Y 以下、tilemap 區域出現背景色水平條碼狀閃爍，且玩家 sprite 也被覆蓋。已做過 A/B：

- 關閉 tilemap transparent key：背景色條碼仍存在，且透明色粉紅會被畫出。
- 將 tilemap CSV 中 `0` tile 臨時改成 tile 1：背景色條碼仍存在，且 world compose 顯著變慢。
- 改成 wire-order non-DMA submit：條碼消失。
- 在 wire-order DMA submit 前加入 `esp_cache_msync(..., DIR_C2M | UNALIGNED)`：條碼消失，且保留 DMA submit 效能。

因此該問題不是 tilemap transparent key，也不是 CSV 空洞；是 wire DMA submit 路徑的資料一致性問題。正式修法是 DMA 前做 cache sync。

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
