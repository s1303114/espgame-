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

目前 Python runtime 的控制流整理方向已開始落地：

- `run()` 不再直接塞滿所有 mode branch
- 啟動 banner 已抽成 `_print_camera_test_start(...)`
- `ROWS_SAFE_NEAR_TILE_TEST`、`SPI_TFT_*`、`FULL_BUFFER_TEST` 已先抽到 `_run_pre_rows_safe_mode(...)`
- `SPI_TFT_*` 內已清掉目前不會被走到的 `CHUNK_WAIT_*` / `COMPAT_*` dead branches，保留現行固定的 `BULK_WAIT_DIRECT`
- 已移除目前未使用的 `BOARD_GENERATED_*`、`ROOT_RGB565_*`、`BLIT_*` mode families，避免歷史 bring-up/testing 分支繼續佔用 bytecode 與維護成本
- 已再移除舊的 `PNG_SINGLE` / `PNG_FULL` / `FAR_ONLY` / `SINGLE_IMAGE_*` / `DIRECT_*` fallback renderer family，`run()` 現在只保留主線與少數仍可用的 bring-up mode
- 已再把 `ROWS_SAFE_PROGRESSIVE` step 4 內的 native band submit 路徑與 profile/report/reset 路徑抽成 helper，繼續縮小 `run()` 的 bytecode 壓力
- `run()` 目前先做 mode normalize、prerequisite check、`_lgfx.init()`、rotation、dispatcher 轉交
- `ROWS_SAFE_PROGRESSIVE` 仍是下一個主要拆分目標，因為它仍是目前最大的 bytecode 風險來源

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

## 10. 本次重新部署與驗證

本次已重新部署：

- 來源：`/workspace/esp/esp/project_root/sd_game_template/game/app_camera_test.py`
- 目標：`/sd/game/app_camera_test.py`
- 部署方式：重新 mount `/sd` 後以 `mpremote ... fs cp` 覆寫 SD 上 runtime 檔案

本次實際整理內容：

1. 將 `run()` 前段的啟動 log / mode banner 抽成 `_print_camera_test_start(...)`
2. 將三條較早返回的測試路徑抽出：
	- `ROWS_SAFE_NEAR_TILE_TEST`
	- `SPI_TFT_SPEED_TEST` / `SPI_TFT_BULK_WAIT_TEST`
	- `FULL_BUFFER_TEST`
3. 新增 `_run_pre_rows_safe_mode(...)` 作為前段 dispatcher，讓 `run()` 先把非主線測試模式導走
4. 保持現有行為不變，這一刀只做搬移與 dispatcher 整理，沒有改渲染策略、native band pipeline 或 profile tuple 格式
5. 清掉 `SPI_TFT_*` 中目前不會被走到的多條 experimental path 分支，並移除未再使用的 `CAMERA_SPI_TEST_PATH` 設定
6. 清掉未再使用的 `BOARD_GENERATED_*`、`ROOT_RGB565_*`、`BLIT_*` modes，並同步移除它們在 mode normalize、prerequisite、startup banner、`run()` 與 config 內的殘留引用
7. 再清掉舊的 `PNG_SINGLE` / `PNG_FULL` / `FAR_ONLY` / `SINGLE_IMAGE_*` / `DIRECT_*` fallback renderer family，包含：
	- mode 常數
	- 舊版 `_ensure_prerequisites(...)`
	- 舊版 `_print_camera_test_start(..., png_single_stage)`
	- `run()` 裡 direct / single-image / manual-frame fallback 尾段
	- `config.py` / `sd_config.py` 內對應的 `CAMERA_TEST_PNG_SINGLE_STAGE`、`CAMERA_TEST_STRIP_H`、`CAMERA_TEST_MANUAL_FRAMES`、`CAMERA_TEST_BG_*`、`CAMERA_TEST_BG_*_RGB565`
8. 再把 `ROWS_SAFE_PROGRESSIVE` step 4 內兩塊可獨立切出的路徑抽成 helper：
	- native band submit 分支
	- profile / stall / dirty-profile 統計輸出與 reset 分支
	- 這一刀先只做 move-only refactor，不改主線 renderer 行為

本次補充驗證結果：

- 重新部署後，板上仍正常從 SD 啟動
- `CAMERA_TEST_MODE=ROWS_SAFE_PROGRESSIVE`
- `CAMERA_TEST_STEP=4_START`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=40`
- 持續看到 `BAND_PIPELINE_SUBMIT_OK`
- 未出現 `SAFE MODE` / `Traceback` / `NameError` / `UNSUPPORTED_MODE`

本次板上開機驗證結果：

- `Launcher source: sd`
- `APP_RUN_START_PHASE_CAMERA_TEST_V2`
- `CAMERA_TEST_MODE=ROWS_SAFE_PROGRESSIVE`
- `CAMERA_TEST_STEP=4_START`
- `ENEMY_UPDATE_IMPL=C_API`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=40`
- `BAND_PIPELINE_SUBMIT_OK`
- `CAMERA_TEST_STEP=4_DRAW_OK`
- 清理 dead code 後重新部署仍可正常啟動主線
- 刪除 `BOARD_GENERATED_*` / `ROOT_RGB565_*` / `BLIT_*` 後重新部署仍可正常啟動主線

本次驗證未再出現：

- `_MODE_PNG_FULL` `NameError`
- launcher `SAFE MODE`
- 啟動階段 `Traceback`

本次啟動後首個 profile window 觀察值：

- `PROFILE update_us=7022`
- `PROFILE submit_us=40429`
- `PROFILE submit_compose_us=12172`
- `PROFILE submit_wait_us=19822`
- `PROFILE submit_dma_wait_us=19748`
- `PROFILE total_us=48467`
- `PROFILE fps=20.63`

這代表目前 SD 上最新 runtime 已可正常進入正式 `ROWS_SAFE_PROGRESSIVE` 主線；目前 bottleneck 結論不變，仍優先指向 native band submit / DMA wait，而不是這次 Python 控制流整理本身。
