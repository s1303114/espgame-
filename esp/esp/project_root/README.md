# ESP32S3 Camera Test Mainline

目前主線是：

- internal flash 只保留 `boot.py` / `main.py`
- `main.py` 以唯一 SD wiring 掛載 `/sd`
- launcher 先驗證 `/sd/game/app.py`、`/sd/game/config.py`、`/sd/game/app_camera_test.py` 存在
- launcher 直接 `exec /sd/game/config.py`，再 `exec /sd/game/app_camera_test.py`
- Python 更新玩家、camera、swap、respawn、object gravity 與主迴圈狀態
- C++ `lgfx.update_enemies_native(...)` 更新 enemy / bullet
- C++ `lgfx.render_scene_bands_rgb565(...)` 做 `320x240 -> 6 x 320x40` native band compose + wire-order DMA submit

## 目前重點

- 啟動路徑：`SD-only launcher`
- 唯一 SD wiring：`slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000`
- 渲染主線：`NATIVE_BAND_PIPELINE`
- band 高度：`40`
- enemy update：`C_API`
- 資產格式：wire-order RGB565
- DMA 前會做 cache sync

## 板上 /sd/game 主線內容

- `app.py`
- `app_camera_test.py`
- `config.py`
- `assets.py`
- `state.py`
- `engine/`
- `actors/`
- `Tilemap/map_tilemap.csv`
- `Tilemap/tilemap_all_wire.rgb565`
- `picture/backgound/bg_far_wire.rgb565`
- `picture/object/objects.csv`
- `picture/object/object_animations.json`
- `picture/object/objects_atlas_wire.rgb565`
- `picture/enemy/enemies.csv`
- `picture/enemy/enemy_bow_animation_wire.rgb565`
- `picture/player/player_wire.rgb565`
- `picture/spawn/Resurrection_Anchor_wire.rgb565`
- `picture/spawn/Spawnpoint_rock_wire.rgb565`

## 主線驗證標記

板上應看到：

- `Launcher source: sd`
- `LOADER_SRC_PATH=/sd/game/app_camera_test.py`
- `LAUNCHER_APP_FILE=/sd/game/app_camera_test.py`
- `OBJECT_COUNT=10`
- `ENEMY_UPDATE_IMPL=C_API`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=40`
- `CAMERA_TEST_STEP=4_DRAW_OK`

## 建置原則

- firmware 一律優先在 `/tmp/esp-mp-local` 編譯
- `user_cmodules` 改動需要重編 firmware
- 只改 Python / 資產時，用 SD-only 部署
- 外接 SD 同步後一定要 `umount -> mount -> readback` 驗證

## 主要文件

- `BUILD_DETAILED_GUIDE.md`
- `CAMERA_RENDERING_GUIDE.md`
- `CURRENT_ARCHITECTURE_GUIDE.md`
- `OBJECTS_CSV_GUIDE.md`
