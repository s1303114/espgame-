# 目前專案架構（主線）

本文件整理目前板上實際主線。核心原則：internal flash 只做 launcher；遊戲程式與資產全部從 `/sd/game` 載入；每幀狀態由 Python 更新，重型畫面合成、enemy update 與 TFT submit 交給 C++ native API。

## 1. 啟動路徑

- internal flash：`/boot.py`、`/main.py`
- `main.py` 是 SD-only launcher
- 唯一正式 SD wiring：`slot=2, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000`
- launcher 會先驗證 `/sd/game/app.py`、`/sd/game/config.py`、`/sd/game/app_camera_test.py` 存在
- 主入口：`main.py` 先 `exec /sd/game/config.py`，再 `exec /sd/game/app_camera_test.py`
- `/sd/game/app.py` 只作為 wrapper / 存在性檢查備用，不是正式主執行檔
- 啟動 log 應看到：`Launcher source: sd`

## 2. /sd/game 實際主線內容

目前板上應至少有：

- `app.py`
- `app_camera_test.py`
- `config.py`
- `assets.py`
- `state.py`
- `engine/`
- `actors/`
- `save/`
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

## 3. 每幀責任分工

Python (`app_camera_test.py`) 負責：

- input update
- player movement / gravity
- object gravity
- B/Y swap
- camera tracking
- respawn / checkpoint
- object / overlay / enemy render descriptor 打包
- 主迴圈 profile 與 fallback 控制

C++ (`lgfx` user module) 負責：

- `update_enemies_native(...)`
- `render_scene_bands_rgb565(...)`
- tilemap / object atlas / player colorkey compose
- enemy compose
- bullet overlay compose
- wire-order DMA submit
- DMA 前 cache sync

## 4. 渲染主線

目前正式 renderer：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 40`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=40`
- `lgfx_config.hpp` 內 `cfg.freq_write = 40000000`

目前畫面以 `320x240` 拆成 `6 x 320x40` bands。C++ 在每個 band 內依序處理：

1. far background
2. tilemap
3. object atlas
4. special overlay / anchor / bullet overlay
5. enemy
6. player sprite
7. band DMA submit

## 5. Enemy update 主線

enemy update 已搬到 C++：

- `lgfx.update_enemies_native(...)`

目前負責：

- enemy AI state transition
- gravity / move / collision
- bullet spawn / move / cull / hit
- 原地更新 enemy / bullet buffer

啟動 log：

- `ENEMY_UPDATE_IMPL=C_API`
- 若 native path 失敗：`ENEMY_UPDATE_NATIVE_FALLBACK ...`

## 6. Persistent buffers

目前已有常駐 packed buffer：

- `enemy_rows_c_buf`
- `enemy_states`
- `enemy_bullets`
- `object_solids_c_buf`

其中：

- `enemy_rows_c_buf` 不再每幀重 pack，只在初始化、swap、respawn、Python fallback 後同步
- `object_solids_c_buf` 不再每幀重 pack，只在初始化、object gravity 變動、swap、respawn 後同步
- `enemy_bullets` 先 `ensure_capacity(enemy_max_bullets)`，讓 native update 直接重用 pool

## 7. 主要資產

目前主線資產都使用 wire-order RGB565：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- object atlas：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- object animations：`/sd/game/picture/object/object_animations.json`
- enemy CSV：`/sd/game/picture/enemy/enemies.csv`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- spawn sheets：`/sd/game/picture/spawn/Resurrection_Anchor_wire.rgb565`、`/sd/game/picture/spawn/Spawnpoint_rock_wire.rgb565`

## 8. 板上重點指標

建議優先看：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=40`
- `OBJECT_COUNT=10`
- `ENEMY_MODE_ON`
- `ENEMY_UPDATE_IMPL=C_API`
- `BAND_PIPELINE_SUBMIT_OK`
- `PROFILE update_us=...`
- `PROFILE submit_us=...`
- `PROFILE submit_wait_us=...`
- `PROFILE submit_kick_us=...`
- `PROFILE submit_dma_wait_us=...`
- `PROFILE fps=...`

## 9. 目前結論

目前主線已不是舊 full-screen Python compose。正式路徑是：

```text
internal flash boot.py/main.py
 -> mount /sd with slot=2 width=1 sck=39 miso=40 mosi=38 cs=47
 -> exec /sd/game/config.py
 -> exec /sd/game/app_camera_test.py
 -> Python game state update
 -> native enemy update
 -> native 6-band renderer
 -> wire-order DMA submit
```

enemy logic 這條線已壓到次要瓶頸；目前真正大頭仍是 `submit_us`，下一步最佳化應優先集中在 band render / submit 路徑。
