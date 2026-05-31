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
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 60`

目前板上互動主線狀態：

- B 鍵觸發 far swap，Y 鍵觸發 near swap，X 目前不觸發 swap。
- swap 使用邊緣觸發與 `SWAP_MIN_INTERVAL_MS` 間隔，避免按鍵連點或長按造成重複觸發。
- far/near swap 都走直接交換流程，不做碰撞回滾；找不到目標只輸出 `SWAP_FAIL_NO_TARGET_V2`。
- 玩家重力由 `PLAYER_GRAVITY` 與 `PLAYER_FALL_SPEED_MAX` 控制。
- object 重力由 `OBJECT_GRAVITY_ENABLED` 與 `OBJECT_GRAVITY_STEP` 控制，每幀把可見 object 往地面推進。
- tilemap、object、player sprite 都優先走 C API compose，透明 colorkey 判斷在 C++ 端完成。
- 內部 flash 的 `main.py` 是 SD-only launcher；遊戲程式與資產都由 `/sd/game` 載入。

提交主線目前是 **native 4-band pipeline + wire-order DMA + cache sync**：

- 主線標記：`SUBMIT_BYTE_ORDER=WIRE_NOSWAP`
- 主線標記：`SUBMIT_WIRE_RUNTIME_SWAP=0`
- 初始化時仍會偵測 full-screen async 能力：`SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE`
- 正式主線會切到：`SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- band 啟動標記：`BAND_PIPELINE_NATIVE_ON h=60`

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

目前主線每幀流程是 native band pipeline，不再是 Python 先合成完整 `scene_buf` 再 full-screen submit。

1. Python 讀輸入，更新 player / object / enemy / bullet / respawn 狀態。
2. Python 更新 `camera_x`，選出本幀 player sprite frame。
3. Python 將 object、special overlay、enemy descriptor 打包成緊湊 buffer。
4. Python 呼叫 `lgfx.render_scene_bands_rgb565(...)`。
5. C++ 依 `CAMERA_BAND_PIPELINE_H` 把 320x240 拆成多個水平 band，目前是 `320x60 * 4`。
6. 每個 band 內由 C++ 依序 compose：
   - far background band
   - tilemap
   - object atlas
   - special object / respawn anchor / bullet overlay
   - enemy
   - player sprite
7. 每個 band compose 後立即以 wire-order DMA submit。
8. C++ 在下一個 band submit 前處理 DMA wait，使 CPU compose 與 DMA/SPI 傳輸交錯。

目前主線提交路徑的 C++ 形態仍以 wire-order DMA 為核心：

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

`esp_cache_msync` 是保留 DMA 效能且避免水平條碼花屏的必要步驟。

## 3. 關鍵 API

`micropython/user_cmodules/lgfx/`：

- `render_scene_bands_rgb565(...)`：目前主線，native 4-band compose + wire DMA submit。
- `compose_tilemap_rgb565(...)`：fallback/測試用 tilemap compose。
- `compose_objects_atlas_rgb565(...)`：fallback/測試用 object atlas compose。
- `compose_colorkey_rgb565(...)`：fallback/測試用 player/sprite colorkey compose。
- `blit_rect565_wire_async(...)`：full-screen wire-order async fallback/測試路徑，cache sync + DMA submit。
- `blit_rect565_wire_wait(...)`：穩定回退路徑，wire-order + non-DMA submit。
- `blit_wait_done()`
- `async_probe_rgb565(...)`
- `submit_probe_rgb565(...)`
- `band_submit_probe_rgb565(...)`
- `rgb565_swap_bytes_inplace(...)`：只保留給實驗，不作主線。

`project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`：

- `--byte-order le`：舊格式，低 byte / 高 byte。
- `--byte-order wire`：目前主線資產格式，高 byte / 低 byte。

## 3.1 RGB565 資產轉檔規格

主工具檔案：

- `/workspace/esp/esp/project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`

工具輸出格式：

- 輸出是 raw RGB565，row-major，沒有 header。檔案大小必須等於 `width * height * 2`。
- `--byte-order le`：每個 pixel 輸出 little-endian byte order，也就是 `lo, hi`。這是舊 `setSwapBytes(true)` 路徑使用的格式。
- `--byte-order wire`：每個 pixel 輸出 panel wire-order，也就是 `hi, lo`。這是目前 native band pipeline 與 full-screen wire DMA 路徑使用的格式。
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
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`
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
| wire asset + DMA + `esp_cache_msync` | `submit_us ~= 24.5ms` | 前一版 full-screen 主線，畫面正常 |

目前 native band pipeline 主線實測（40MHz TFT 設定、4 bands x 60px）：

- `submit_us` 約 `33.9ms`
  - 注意：native band 模式下這包含 C++ compose + band DMA pipeline，不是舊版純 submit。
- `submit_kick_us` 約 `5.8ms`
- `submit_wait_us` 約 `13.4ms`
- `submit_swap_us = 0`
- `total_us` 約 `35.7ms`
- `fps` 約 `28.0`

對照前一版 full-screen wire-order DMA 主線：

- `submit_us` 約 `24.5ms`，但 Python compose 另需約 `15~25ms`
- `total_us` 約 `51.6ms`
- `fps` 約 `19.4`

因此 band pipeline 的收益不是減少總傳輸量，而是把 C++ compose 與 DMA wait 重疊，降低整幀 total time。

關鍵結論：

1. wire-order asset 是有效方向，能避免 LGFX 內部 byte-swap/convert staging。
2. runtime in-place swap 不可作主線，因為每幀多約 `13.2ms`，且容易污染雙緩衝 buffer 狀態。
3. `pushImageDMA` 直接讀 Python/PSRAM scene buffer 若不做 cache sync，會造成水平條碼狀花屏；原因是 DMA/cache coherency 或 PSRAM DMA 路徑一致性問題。
4. 目前正式方案是 wire-order asset + `esp_cache_msync` + native band DMA pipeline。
5. full-screen wire DMA 與 non-DMA `pushImage` 保留為回退與測試路徑。

## 4.1 已排除的畫面問題方向

曾觀察到玩家 Y 以下、tilemap 區域出現背景色水平條碼狀閃爍，且玩家 sprite 也被覆蓋。已做過 A/B：

- 關閉 tilemap transparent key：背景色條碼仍存在，且透明色粉紅會被畫出。
- 將 tilemap CSV 中 `0` tile 臨時改成 tile 1：背景色條碼仍存在，且 world compose 顯著變慢。
- 改成 wire-order non-DMA submit：條碼消失。
- 在 wire-order DMA submit 前加入 `esp_cache_msync(..., DIR_C2M | UNALIGNED)`：條碼消失，且保留 DMA submit 效能。

因此該問題不是 tilemap transparent key，也不是 CSV 空洞；是 wire DMA submit 路徑的資料一致性問題。正式修法是 DMA 前做 cache sync。

## 4.2 Native Band Pipeline 細節

目前 band pipeline 入口在：

- Python：`app_camera_test.py` 內偵測 `CAMERA_BAND_PIPELINE_NATIVE`
- C++：`micropython/user_cmodules/lgfx/lgfx_band.cpp`
- exported API：`lgfx.render_scene_bands_rgb565(...)`

啟用條件：

- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 60`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `CAMERA_FULL_BULK_WIRE_RUNTIME_SWAP = False`
- firmware 內有 `render_scene_bands_rgb565`
- far background 已 RAM cache
- tilemap / tileset / object atlas / player sprite 都已載入

目前特殊動畫物件與復活錨點也已走 native overlay 描述子路徑：

- Python 會把每個 animated overlay 打包成 `x, y, w, h, frame_index` 描述子
- frame buffer tuple 會一併傳給 `lgfx.render_scene_bands_rgb565(...)`
- C++ band compose 會在 object atlas 後、player sprite 前套用這些 overlay
- 因此 `special_object_render_enabled` 不再是 native band fallback 的理由

若條件不滿足，會輸出：

- `BAND_PIPELINE_NATIVE_FALLBACK`

並回到原本 full-screen compose/submit 路徑。

目前 C++ 回傳 profile tuple：

```text
(band_count, compose_us, kick_us, wait_us, total_us)
```

Python 主線會把整個 native call 記入 `PROFILE submit_us`，並把 `kick_us / wait_us` 拆到 `PROFILE submit_kick_us / PROFILE submit_wait_us`。

實機驗證時，建議先做兩個檢查：

- `import lgfx; hasattr(lgfx, 'render_scene_bands_rgb565')` 必須是 `True`
- 開機 log 必須看到 `SUBMIT_MODE=NATIVE_BAND_PIPELINE` 與 `BAND_PIPELINE_NATIVE_ON h=...`

如果 `lgfx` 缺少 `render_scene_bands_rgb565`，不要先懷疑 Python runtime。先檢查 `/tmp` 本地鏡像是否真的同步到所有改動過的 user_cmodule 檔案，尤其是：

- `micropython/user_cmodules/lgfx/lgfx_mp.cpp`
- `micropython/user_cmodules/lgfx/lgfx_band.cpp`
- `micropython/user_cmodules/lgfx/lgfx_shared.hpp`

這次已驗證過一個容易踩到的坑：只同步 `lgfx_band.cpp` 和 header 到 `/tmp/esp-mp-local` 並重編，firmware 可能會刷進新的 band renderer，但因為舊版 `lgfx_mp.cpp` module table 還留在 `/tmp`，板上 `lgfx` 仍然不會匯出 `render_scene_bands_rgb565`，結果開機會持續 fallback。

最佳化方向：

1. 測試 `CAMERA_BAND_PIPELINE_H = 40 / 48 / 80`，找 compose 與 DMA wait 最佳 overlap。
2. 減少每幀 far background 153KB copy。
3. 對 camera static frame 做 static world band cache，只重畫 player。
4. camera 移動時做水平 strip cache，而不是每 band 重組 tilemap。

## 5. Build / Flash

主推 `/tmp` 本地鏡像流程（避免工作樹環境污染）：

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

若 `build_local_tmp.sh` 在 `/workspace -> /tmp` 複製階段卡在 9p I/O，且你改的是少數幾個 user_cmodule 檔案，可以直接把所有改過的檔案同步到既有 `/tmp/esp-mp-local` 後再重編；不要只同步其中一部分，否則很容易出現 qstr / module export 與實際實作版本不一致。

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
