# 目前專案架構（主線）

本文件整理目前板上實際主線。核心原則：internal flash 只做 launcher；遊戲程式與資產全部從 `/sd/game` 載入；一般高層遊戲狀態仍由 Python 編排，重型畫面合成、live enemy update 與 TFT submit 交給 C++ native API。monk 目前已不是單一 live enemy，而是 `inactive -> intro_drop -> live` 的 encounter actor。

## 0. 最新現況快照（2026-06-07）

目前板上主線仍是 SD-only runtime：internal flash 只放 `/boot.py`、`/main.py`，正式遊戲從 `/sd/game/config.py` 與 `/sd/game/app_camera_test.py` 啟動。正式 renderer 是 `ROWS_SAFE_PROGRESSIVE` + `NATIVE_BAND_PIPELINE`，band 高度 `48`，wire-order submit 開啟。

目前 monk/orb 最新行為：

- intro drop 速度：`MONK_INTRO_DROP_SPEED = 3`
- intro body 目標 Y：`MONK_INTRO_TARGET_Y = 56`
- live hover base Y：`MONK_HOVER_BASE_Y = 55`
- monk 區域重生門檻：`MONK_RESPAWN_REINTRO_MIN_X = 1500`
- 玩家在 monk 區域重生時，會觸發 `MONK_RESPAWN_REINTRO_RESET ...`，live monk slot 會被隱藏並重用，下一輪重新跑 intro
- monk attack 目前有 type 1 split/drop/sweep 與 type 2 five-orb pulse；type 2 半徑 `28 -> 128 -> 28`，timing 是 `60/40/60`
- action 色 orb mode `2/4/5` 會傷害玩家；action orb 彼此以 `16x16` hitbox 重疊時會停在當前位置、轉回 detached 公轉色、停止傷害

本次抓到的一組板上 profile/FPS（`/tmp/monk_fps_sample.log`，`CAMERA_RUNTIME_VERBOSE=True`）：

- `PROFILE update_us=7062`
- `PROFILE submit_us=31582`
- `PROFILE submit_wait_us=17010`
- `PROFILE submit_dma_wait_us=16906`
- `PROFILE total_us=39474`
- `PROFILE fps=25.33`
- 同一段 log 後續 sample 約在 `24.4-25.4 fps`

## 1. 啟動路徑

- internal flash：`/boot.py`、`/main.py`
- `main.py` 是 SD-only launcher
- 唯一正式 SD wiring：`slot=2, width=1, sck=5, mosi=6, miso=7, cs=4, freq=1000000`
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
- monk encounter lifecycle
- monk intro actor high-level trigger / handoff（intro drop update 已優先走 native API，Python 保留 fallback / orchestration）
- monk intro / live handoff
- monk-area respawn reintro reset
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

目前 monk 的責任分層是：

- Python：encounter lifecycle orchestration、intro/live handoff、monk-area respawn reintro、swap apply、scripted/fallback shadow state
- C++：live monk hover / waypoint movement、live enemy native update
- C++：monk intro drop state update（Python 仍保留 fallback）
- C++：live orb state update、live orb descriptor packing、monk orb swap target picking
- C++：live monk attack phase update、attack orb scripted movement
- C++ renderer：intro/live descriptor 最終合成與 submit

## 4. 渲染主線

目前正式 renderer：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 48`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `lgfx_config.hpp` 內 `cfg.freq_write = 40000000`

目前畫面以 `320x240` 拆成 `5 x 320x48` bands。C++ 在每個 band 內依序處理：

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

但要注意：這裡的 `enemy update` 目前主要是指 live enemy set。monk 已拆成兩段：

- `intro_drop` 前：不在 live enemy set
- `intro_drop` 中：由 Python encounter actor 更新 body/orb 狀態
- `live` 後：append 到 live enemy rows，再交給 native `static enemy` hover / waypoint 分支

目前已板上驗證：

- 開機時 `ENEMY_COUNT=2`
- `camera_x >= 1600` 後出現 `MONK_ENCOUNTER_STATE=intro_drop`
- intro 完成後才出現 `MONK_LIVE_INSTANTIATED`
- 之後可看到 `MONK_HOVER_DBG ...`，代表 live 後已交由 native hover update 接手

啟動 log：

- `ENEMY_UPDATE_IMPL=C_API`
- 若 native path 失敗：`ENEMY_UPDATE_NATIVE_FALLBACK ...`

## 6. Persistent buffers

目前已有常駐 packed buffer：

- `enemy_rows_c_buf`
- `enemy_states`
- `enemy_bullets`
- `object_solids_c_buf`
- `monk_orb_c_buf`
- `monk_attack_c_buf`

另外目前 monk 還有三組關鍵狀態：

- `monk_encounters`
- `monk_hover_c_buf`
- `monk_attack_c_buf`

其中：

- `enemy_rows_c_buf` 不再每幀重 pack，只在初始化、swap、respawn、Python fallback 後同步
- `object_solids_c_buf` 不再每幀重 pack，只在初始化、object gravity 變動、swap、respawn 後同步
- `enemy_bullets` 先 `ensure_capacity(enemy_max_bullets)`，讓 native update 直接重用 pool
- `monk_hover_c_buf` 在 monk 進入 live 時會擴充一筆新 row，並同步更新 `monk_hover_c_count`
- `monk_orb_c_buf` 在 monk 進入 live 時會擴充，live orb 的 authoritative state 目前在這個 buffer
- `monk_attack_c_buf` 在 monk 進入 live 後按 enemy count 擴充，保存 attack phase、左右 attack slot、phase target、水平移動方向與 waypoint interval attack cadence toggle
- `enemy_rows_c_buf` 在 monk `intro -> live` handoff 時也會擴充並同步 `enemy_rows_c_count`
- monk 區域 respawn reintro 不再 append 新 live monk；它會隱藏並重用現有 live monk slot，清掉該 slot 的 orb/attack state，再讓 encounter 回到 `inactive` + intro armed
- `monk_orb_damage.py` 是小型 Python helper module，掃描 `monk_orb_c_buf` 的第二色 modes；主檔 `app_camera_test.py` 已接近 MicroPython bytecode 上限，新增 runtime 行為優先拆 helper module

這兩個 count 同步目前已是必要條件，否則會出現 monk 看起來 instantiate 成功，但 native update 根本沒開始處理新 row 的停住問題。

目前 monk encounter 本身則仍主要保存在 Python objects 內，而不是 native packed buffer：

- `state`
- `intro_state`
- `body_x/body_y`
- `body_target_x/body_target_y`
- `anim_counter`
- `orbs`
- `orb_states`

live orb state 則已 native 化：

- `lgfx.update_monk_orbs_native(...)` 更新 `mode/current_x/current_y/return_radius`
- `lgfx.pack_monk_orb_descriptors_native(...)` 產生 `_SPECIAL_KIND_MONK_ORB` render descriptor
- `lgfx.pick_swappable_monk_orb_native(...)` 負責 near/far monk orb target picking
- `lgfx.update_monk_attack_native(...)` 負責 attack type 1 的 split/drop/sweep phase update
- Python `_swap_with_monk_orb(...)` 仍負責真正 swap apply，並直接寫回 `monk_orb_c_buf`
- Python `monk_orb_damage.action_hit_player(...)` 將 mode `2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 視為第二色 damage orb；碰到玩家會沿用既有死亡 / respawn 流程。mode `1 detached` 與 `6 pulse_hold` 是公轉色，不造成傷害
- 一般 live path 不再每幀把 C buffer sync 回 Python dict；dict 只保留 fallback / intro scripted / debug shadow 用途
- attack orb swap 時，`monk_orb_c_buf` 保持 `scripted_attack` mode，render descriptor 仍必須走 native C API，不能因 Python shadow 有 `scripted_attack` 而 fallback

## 7. 主要資產

目前主線資產都使用 wire-order RGB565：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- object / monk orb atlas：`/sd/game/picture/object/object_altes_wire.rgb565`
- legacy object atlas path currently may still exist on SD：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- object animations：`/sd/game/picture/object/object_animations.json`
- enemy CSV：`/sd/game/picture/enemy/enemies.csv`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- spawn sheets：`/sd/game/picture/spawn/Resurrection_Anchor_wire.rgb565`、`/sd/game/picture/spawn/Spawnpoint_rock_wire.rgb565`

## 8. 板上重點指標

建議優先看：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `OBJECT_COUNT=10`
- `ENEMY_MODE_ON`
- `ENEMY_UPDATE_IMPL=C_API`
- `MONK_ORB_UPDATE_IMPL=C_API`
- `MONK_ORB_DESC_IMPL=C_API`
- `MONK_ATTACK_NATIVE_START ...`
- `MONK_ATTACK_NATIVE_PHASE ...`
- `MONK_ATTACK_NATIVE_SKIP ...`
- `SWAP_MONK_ORB_ATTACK_CONTINUE ...`
- `MONK_ATTACK_NATIVE_DONE ...`
- `PLAYER_KILLED_BY_MONK_ORB ...`
- `BAND_PIPELINE_SUBMIT_OK`
- `MONK_RESPAWN_REINTRO_RESET ...`
- `MONK_ENCOUNTER_STATE=intro_drop`
- `MONK_INTRO_START ...`
- `MONK_INTRO_DONE ...`
- `MONK_LIVE_INSTANTIATED ...`
- `MONK_ENCOUNTER_STATE=live`
- `MONK_HOVER_DBG ...`
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
 -> mount /sd with slot=2 width=1 sck=5 mosi=6 miso=7 cs=4
 -> exec /sd/game/config.py
 -> exec /sd/game/app_camera_test.py
 -> Python game state update
 -> Python monk encounter / intro update
 -> native live enemy update
 -> native 6-band renderer
 -> wire-order DMA submit
```

目前 bottleneck 不能再簡化成「只有 submit_us」。monk/orb live 熱路徑已搬到 C++ 後，最近板上 profile 顯示：

- native orb steady-state sample：`update_avg=6509.7us`、`fps_avg=25.76`
- swap/debug burst sample：`swap_events=31`、`update_avg=8939.7us`、`update_max=12926us`、`fps_avg=23.68`
- 2026-06-07 sample：`update_us=7062`、`submit_us=31582`、`total_us=39474`、`fps=25.33`

也就是說，目前 steady-state 已經改善；剩下最顯眼的 update 高點主要來自 swap/debug burst，尤其 `SWAP_*` print 與 Python debug metrics，而不是 live orb update 本身退步。

另外目前 `CAMERA_RUNTIME_VERBOSE = True`，而板上高頻 `MONK_INTRO_DBG`、`MONK_HOVER_DBG`、`SWAP_TARGET_DBG` 也會額外拉低低谷 FPS，所以 profile 仍混有 debug 成本。

## 10. 本次重新部署與驗證

本文件以下部署紀錄主要反映先前主線整理與 band pipeline 驗證；目前 monk encounter 狀態已比這段紀錄更新。若要理解 monk 現況，應優先以 [MONK_ORB_ARCHITECTURE.md](/workspace/esp/esp/project_root/MONK_ORB_ARCHITECTURE.md) 的 lifecycle 與 handoff 描述為準。

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
- `BAND_PIPELINE_NATIVE_ON h=48`
- 持續看到 `BAND_PIPELINE_SUBMIT_OK`
- 未出現 `SAFE MODE` / `Traceback` / `NameError` / `UNSUPPORTED_MODE`

本次板上開機驗證結果：

- `Launcher source: sd`
- `APP_RUN_START_PHASE_CAMERA_TEST_V2`
- `CAMERA_TEST_MODE=ROWS_SAFE_PROGRESSIVE`
- `CAMERA_TEST_STEP=4_START`
- `ENEMY_UPDATE_IMPL=C_API`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `BAND_PIPELINE_SUBMIT_OK`
- `CAMERA_TEST_STEP=4_DRAW_OK`
- 清理 dead code 後重新部署仍可正常啟動主線
- 刪除 `BOARD_GENERATED_*` / `ROOT_RGB565_*` / `BLIT_*` 後重新部署仍可正常啟動主線

本次驗證未再出現：

- `_MODE_PNG_FULL` `NameError`
- launcher `SAFE MODE`
- 啟動階段 `Traceback`

2026-06-07 最新 profile window 觀察值：

- `PROFILE update_us=7062`
- `PROFILE submit_us=31582`
- `PROFILE submit_wait_us=17010`
- `PROFILE submit_dma_wait_us=16906`
- `PROFILE total_us=39474`
- `PROFILE fps=25.33`

這代表目前 SD 上最新 runtime 已可正常進入正式 `ROWS_SAFE_PROGRESSIVE` 主線；這組 sample 仍主要受 native band submit / DMA wait 與 verbose debug 成本影響。
