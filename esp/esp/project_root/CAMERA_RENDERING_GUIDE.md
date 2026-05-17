# CAMERA 渲染說明書

## 1. 範圍與目前基線

本文件描述目前渲染路徑，對應檔案：

- `sd_game_template/game/app_camera_test.py`
- `sd_game_template/game/config.py`
- `micropython/user_cmodules/lgfx/lgfx_mp.cpp`
- `micropython/user_cmodules/lgfx/lgfx_config.hpp`

`config.py` 目前基線：

- `PHASE_ACCEPTANCE_STAGE = "PHASE_CAMERA_TEST"`
- `CAMERA_TEST_MODE = "map1_full_bulk"`（別名，實際映射到 `ROWS_SAFE_PROGRESSIVE`）
- `CAMERA_SPI_TEST_PATH = "BULK_WAIT_DIRECT"`
- `FLOOR_LAYER_ENABLED = True`（啟用 map1）
- TFT 寫入時脈：`40 MHz`（`cfg.freq_write = 40000000`）

## 2. 每幀渲染流程

STEP4 每幀大致流程：

1. 在 RAM 建立/更新 `scene_buf`（RGB565）。
2. 合成 far/background。
3. 合成 world floor（map1 + mask）。
4. 合成 player sprite。
5. 將 `scene_buf` 提交到 TFT。

主要緩衝：

- `scene_buf`：場景輸出 buffer。
- `far_band_buf`：far 層快取（可用時）。
- `floor_rgb_data` / `floor_mask_data`：map1 圖與遮罩。

## 3. LGFX C 模組 API（提交與合成）

在 `lgfx_mp.cpp` 定義：

- `blit_rect565_rows(x, y, w, h, buf)`
- `blit_rect565_wait(x, y, w, h, buf)`
- `blit_rect565_wait_copy(...)`
- `blit_rect565_wait_copy_compat(...)`
- `compose_masked_rgb565(...)`

用途摘要：

- `blit_rect565_rows`：逐列/分段安全提交。
- `blit_rect565_wait`：直接提交 + `waitDMA()`。
- `blit_rect565_wait_copy`：先 copy 後 chunk 提交。
- `blit_rect565_wait_copy_compat`：相容安全路徑。
- `compose_masked_rgb565`：C 端遮罩合成（地板/精靈）。

## 4. CAMERA_TEST_MODE 模式總覽

`_normalize_mode()` 可接受多種模式（`app_camera_test.py`）：

- `COLOR`
- `PNG_SINGLE`
- `PNG_FULL`
- `FAR_ONLY`
- `SINGLE_IMAGE_STRIP`
- `SINGLE_IMAGE_DIRECT`
- `DIRECT_BG_ONLY`
- `DIRECT_RGB565_BG_ONLY`
- `ROOT_FAR_RGB565_ONLY`
- `BOARD_GENERATED_RGB565_TEST`
- `ROOT_RGB565_TEST_PATTERN`
- `BOARD_GENERATED_GRID_TEST`
- `ROOT_RGB565_GRID_PATTERN`
- `BLIT_SINGLE_BLOCK_TEST`
- `BLIT_FULL_BUFFER_TEST`
- `BLIT_ROWS_GRID_TEST`
- `ROWS_SAFE_PROGRESSIVE`
- `ROWS_SAFE_NEAR_TILE_TEST`
- `FULL_BUFFER_TEST`
- `SPI_TFT_SPEED_TEST`
- `SPI_TFT_BULK_WAIT_TEST`

別名：

- `MAP1_FULL_BULK` -> `ROWS_SAFE_PROGRESSIVE`

所以 `CAMERA_TEST_MODE = "map1_full_bulk"` 會進入 `ROWS_SAFE_PROGRESSIVE` 邏輯。

## 5. 目前主線：map1 捲動 + 全屏 bulk 提交

目前固定主線行為：

- 邏輯路徑：`ROWS_SAFE_PROGRESSIVE`（相機 + map1 捲動）
- 提交路徑：STEP4 最終提交固定為
  - `_lgfx.blit_rect565_wait(0, band_top, sw, scene_h, scene_buf)`

在目前 floor 設定下：

- `FLOOR_LAYER_ENABLED = True`
- full-scene 分配分支內 `band_top = 0`、`scene_h = sh`

等效提交：

- `x=0, y=0, w=320, h=240`（每幀全屏 bulk）

執行標記：

- `FULLSCREEN_BULK_SUBMIT_OK`

## 6. SPI 測試分支（與 map1 主線不同）

`SPI_TFT_BULK_WAIT_TEST` 會看 `CAMERA_SPI_TEST_PATH`：

- `ROWS_SAFE` -> `blit_rect565_rows(0,0,320,240,buf)`
- `BULK_WAIT_DIRECT` -> `blit_rect565_wait(0,0,320,240,buf)`
- `CHUNK_WAIT_DIRECT_16` -> 多次 `blit_rect565_wait(..., h=16)`
- `CHUNK_WAIT_COPY_16/32` -> `blit_rect565_wait_copy(...)`
- `CHUNK_WAIT_COPY_COMPAT_{1,2,4,8}` -> compat API

這是傳輸測試分支，不是 map1 主遊戲相機流程。

## 7. map1 合成細節

啟用 floor layer 後：

1. 解析資源路徑：
   - `FLOOR_LAYER_RGB565_PATH`
   - `FLOOR_LAYER_MASK_PATH`
2. 嘗試快取 RGB 到 RAM：成功印 `FLOOR_LAYER_RGB_CACHE_READY`。
3. 若 `FLOOR_USE_C_COMPOSE=True` 且有 `compose_masked_rgb565`，走 C 合成：
   - 印 `FLOOR_LAYER_COMPOSE_C_READY`
4. 每幀來源 X：
   - `floor_src_x = int(camera_x * FLOOR_SCROLL_FACTOR) + FLOOR_SCROLL_X_OFFSET`
5. 將 floor 合成到 `scene_buf`。

## 8. Dirty 設定與目前主線關係

設定仍存在：

- `CAMERA_DIRTY_RECT_EXPERIMENT`
- `CAMERA_DIRTY_FALLBACK_ON_CAMERA_MOVE`
- `CAMERA_DIRTY_BAND_FULL_WIDTH`

但目前 STEP4 最終提交已強制 full-screen bulk，
dirty/strip 的最終提交分支不再是主線。

## 9. 觀察效能指標

序列埠可觀察：

- `PROFILE bg_us`
- `PROFILE sprite_us`
- `PROFILE submit_us`
- `PROFILE total_us`
- `PROFILE fps`
- `CAMERA_STEP4_PERF frame_ms=... fps=...`

目前 map1 + full-screen bulk 路徑下，`submit_us` 通常是主要瓶頸之一。

## 10. Build / Flash / Deploy

Build：

```bash
cd /workspace/esp/esp/micropython/ports/esp32
source /workspace/esp/esp/esp-idf/export.sh
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/workspace/esp/esp/micropython/user_cmodules
```

Flash：

```bash
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

只部署 Python 檔：

```bash
cd /workspace/esp/esp/project_root
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/sd/game/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/sd/game/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/config.py :/config.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 fs cp sd_game_template/game/app_camera_test.py :/app_camera_test.py
/tmp/mpvenv/bin/mpremote connect /dev/ttyACM0 reset
```

## 11. 板上驗證清單

開機序列埠請確認：

- `CAMERA_TEST_MODE=ROWS_SAFE_PROGRESSIVE`（別名 normalize 後）
- `FLOOR_LAYER_READY`
- `FULLSCREEN_BULK_SUBMIT_OK`
- `PROFILE fps=...`

都出現即代表目前路徑是：

- map1 捲動邏輯啟用
- 全屏 bulk 提交啟用
