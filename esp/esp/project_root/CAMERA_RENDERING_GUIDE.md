# CAMERA 渲染說明書（目前主線）

## 1. 目前主線

目前主線是：

- `PHASE_ACCEPTANCE_STAGE = "PHASE_CAMERA_TEST"`
- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `TILEMAP_ENABLED = True`
- `FLOOR_LAYER_ENABLED = False`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL = "C_API"`
- `CAMERA_FULL_BULK_DOUBLE_BUFFER = True`

提交主線是 **DMA 雙緩衝 full bulk**（可回退）：

- 主線標記：`SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE`
- 回退標記：`SUBMIT_MODE=SYNC_SINGLE_BUFFER_FALLBACK`

## 2. 每幀流程

1. 讀輸入、更新 `player_x / camera_x`。
2. 在 RAM `scene_buf` 合成 far 背景。
3. tilemap 合成：
   - 優先 `compose_tilemap_rgb565`（C API）
   - 否則回退 Python tilemap。
4. 玩家 sprite 合成：`compose_masked_rgb565`（C API）。
5. 提交到 TFT：
   - 主線：`blit_rect565_async` + `blit_wait_done`（雙緩衝 ping-pong）
   - 回退：`blit_rect565_wait`（單緩衝同步）

## 3. 關鍵 API

`micropython/user_cmodules/lgfx/lgfx_mp.cpp`：

- `compose_masked_rgb565(...)`
- `compose_tilemap_rgb565(...)`
- `blit_rect565_wait(...)`
- `blit_rect565_async(...)`
- `blit_wait_done()`

## 4. 觀測重點

序列埠輸出重點：

- `TILEMAP_COMPOSE_IMPL=C_API`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL=C_API`
- `SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE`
- `PROFILE submit_us=...`
- `PROFILE fps=...`

目前瓶頸通常仍在 `submit_us`（TFT 全幀提交）。

## 5. Build / Flash

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
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

Tilemap 目前是主線 world 合成來源（取代 map1）：

- 啟用：`TILEMAP_ENABLED = True`
- map1 關閉：`FLOOR_LAYER_ENABLED = False`
- tileset 路徑：`TILESET_RGB565_PATH = "game/Tilemap/Tileset.rgb565"`

資料格式：

- 地圖索引：`_TILEMAP_CSV`（在 `app_camera_test.py`）
- tile 大小：`16x16`
- index `0`：透明（不畫）
- index `1..N`：對應 tileset atlas 的 tile

目前合成實作：

1. 啟動時把 `_TILEMAP_CSV` 轉成 `tilemap_idx`（1 byte/index）
2. 讀入 `Tileset.rgb565`（raw RGB565 atlas）
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
