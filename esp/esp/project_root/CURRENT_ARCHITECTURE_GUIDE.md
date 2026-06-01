# 目前專案架構（主線）

本文件整理目前板上實際主線。核心原則：內部 flash 只放 launcher，遊戲程式與資產從 SD 載入；每幀狀態由 Python 更新，重型畫面合成、enemy update 與 TFT submit 交給 C++ native API。

## 1. 啟動路徑

- internal flash：`/boot.py`、`/main.py`
- `main.py` 是 SD-only launcher
- 遊戲根目錄：`/sd/game`
- 主入口：`/sd/game/app.py` -> `/sd/game/app_camera_test.py`
- 啟動 log 應看到：`Launcher source: sd`

## 2. 每幀責任分工

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

## 3. 渲染主線

目前正式 renderer：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 60`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`

目前畫面以 `320x240` 拆成 `4 x 320x60` bands。C++ 在每個 band 內依序處理：

1. far background
2. tilemap
3. object atlas
4. special overlay / anchor / bullet overlay
5. enemy
6. player sprite
7. band DMA submit

## 4. Enemy update 主線

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

## 5. Persistent buffers

目前已有常駐 packed buffer：

- `enemy_rows_c_buf`
- `enemy_states`
- `enemy_bullets`
- `object_solids_c_buf`

其中：

- `enemy_rows_c_buf` 不再每幀重 pack，只在初始化、swap、respawn、Python fallback 後同步
- `object_solids_c_buf` 不再每幀重 pack，只在初始化、object gravity 變動、swap、respawn 後同步
- `enemy_bullets` 先 `ensure_capacity(enemy_max_bullets)`，讓 native update 直接重用 pool

## 6. 主要資產

目前主線資產都使用 wire-order RGB565：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map1_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- object atlas：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`

## 7. 板上重點指標

建議優先看：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`
- `ENEMY_UPDATE_IMPL=C_API`
- `BAND_PIPELINE_SUBMIT_OK`
- `PROFILE update_us=...`
- `PROFILE submit_us=...`
- `PROFILE submit_wait_us=...`
- `PROFILE submit_kick_us=...`
- `PROFILE fps=...`

## 8. 目前結論

目前主線已不是舊 full-screen Python compose。正式路徑是：

```text
SD-only launcher
 -> Python game state update
 -> native enemy update
 -> native 4-band renderer
 -> wire-order DMA submit
```

enemy logic 這條線已壓到次要瓶頸；目前真正大頭仍是 `submit_us`，下一步最佳化應優先集中在 band render / submit 路徑。
