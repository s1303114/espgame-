# 目前專案架構（主線）

本文件整理目前板上實際主線。核心原則：internal flash 只做 launcher；遊戲程式與資產全部從 `/sd/game` 載入；一般高層遊戲狀態仍由 Python 編排，重型畫面合成、object gravity / solids sync、live enemy update 與 TFT submit 交給 C++ native API。monk 目前已不是單一 live enemy，而是 `inactive -> intro_drop -> live` 的 encounter actor。

## 0. 最新現況快照（2026-06-07）

目前板上主線仍是 SD-only runtime：internal flash 只放 `/boot.py`、`/main.py`，正式遊戲從 `/sd/game/config.py` 與 `/sd/game/app_camera_test.py` 啟動。正式 renderer 是 `ROWS_SAFE_PROGRESSIVE` + `NATIVE_BAND_PIPELINE`，band 高度 `48`，wire-order submit 開啟。

2026-06-11 補充：object gravity 與 object solids sync 已完成第一階段 native 化。Python 仍負責 object lifecycle / swap / checkpoint orchestration，但每幀 object gravity 優先走 `object_native.update_frame(...) -> lgfx.update_objects_native(...)`；`object_native.py` 保存 Python fallback 與 persistent buffer helper，避免再把 bytecode 壓回 `app_camera_test.py`。

目前 monk/orb 最新行為：

- intro drop 速度：`MONK_INTRO_DROP_SPEED = 3`
- intro body 目標 Y：`MONK_INTRO_TARGET_Y = 56`
- live hover base Y：`MONK_HOVER_BASE_Y = 55`
- monk 區域重生門檻：`MONK_RESPAWN_REINTRO_MIN_X = 1500`
- 玩家在 monk 區域重生時，會觸發 `MONK_RESPAWN_REINTRO_RESET ...`，live monk slot 會被隱藏並重用，下一輪重新跑 intro
- monk attack 目前有 type 1 split/drop/sweep + three-orb-phase dive、type 2 pulse、以及最後一顆 orb 的黑線反彈 path phase。type 1 在 5/4 顆時只用左右兩顆，剩 3 顆 orbit 且另外 2 顆是 `8 lost` 時才加第三顆：上飛到 `Y=0`、追到玩家頭上、下墜到 `Y=160`。type 2 至少三顆 orbit orb 可啟動，`8 lost` 會被忽略；5/4 顆維持同步 `28 -> 128 -> 28` pulse，timing 是 `60/40/60`；只剩 3 顆 orbit + 2 lost 時改成 `0/12/24` frame 三角錯峰雙峰 pulse，最大半徑 hold 與雙峰收尾等待都維持攻擊色。只剩精確 `1 orbit + 4 lost` 時，會記錄進 final 當下螢幕中心為固定 world waypoint，鎖住 Monk hover target 不再 retarget，Monk 以 `MONK_HOVER_SPEED_Q8` 速度沿直線平移到 waypoint 後停住，orb 以 mode `9 final_orbit` 繞 waypoint 公轉；warning 階段畫完整 `3` 秒、純黑 `1px`、可穿過 Monk 的螢幕邊界反彈 path（special kind `3`），warning 後黑線消失，orb 以 mode `4`、速度 `24` 沿線移動真實時間 `3` 秒；rush 結束或 swap eject 後，orb 直線回到下一輪 `angle_step` 對應的 `waypoint + radius 44` 位置，到位後立刻重新產生 warning path。這裡尚未實作擊敗 Monk 或 encounter clear
- action 色 damage mode `2/4/5` 會傷害玩家；mode `9 final_orbit` 使用 action 色但不造成傷害。可傷害 action orb 彼此以 `16x16` hitbox 重疊時會進入 `7 clash_bounce`，短暫彈起後掉出世界成為 `8 lost`，不再 render、damage 或被 swap picker 選中

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
- `object_native.py`
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
- `picture/object/object_altes_wire.rgb565`
- `picture/enemy/enemies.csv`
- `picture/enemy/enemy_bow_animation_wire.rgb565`
- `picture/player/player_wire.rgb565`
- `picture/spawn/Resurrection_Anchor_wire.rgb565`
- `picture/spawn/Spawnpoint_rock_wire.rgb565`

## 3. 每幀責任分工

Python (`app_camera_test.py`) 負責：

- input update
- player movement / gravity
- object lifecycle orchestration；object gravity 優先走 native，Python fallback 已拆到 `object_native.py`
- B/Y swap
- camera tracking
- respawn / checkpoint
- monk encounter lifecycle
- monk intro actor high-level trigger / handoff（intro drop update 已優先走 native API，Python 保留 fallback / orchestration）
- monk intro / live handoff
- monk-area respawn reintro reset
- object / overlay / enemy render descriptor 打包
- object render/state/solid persistent buffer 初始化與 restore helper 呼叫
- 主迴圈 profile 與 fallback 控制

目前 Python runtime 的控制流整理方向已開始落地：

- `run()` 不再直接塞滿所有 mode branch
- 啟動 banner 已抽成 `_print_camera_test_start(...)`
- `ROWS_SAFE_NEAR_TILE_TEST`、`SPI_TFT_*`、`FULL_BUFFER_TEST` 已從 SD runtime 主線移除；若要再用，應另開發期 bring-up 檔案或手動恢復
- 已移除目前未使用的 `BOARD_GENERATED_*`、`ROOT_RGB565_*`、`BLIT_*` mode families，避免歷史 bring-up/testing 分支繼續佔用 bytecode 與維護成本
- 已再移除舊的 `PNG_SINGLE` / `PNG_FULL` / `FAR_ONLY` / `SINGLE_IMAGE_*` / `DIRECT_*` fallback renderer family，`run()` 現在只保留主線 renderer
- 已再把 `ROWS_SAFE_PROGRESSIVE` step 4 內的 native band submit 路徑與 profile/report/reset 路徑抽成 helper，繼續縮小 `run()` 的 bytecode 壓力
- object native helper 已拆到 `object_native.py`；後續 runtime 新邏輯仍應優先放 helper module，主檔只留 orchestration 呼叫
- `run()` 目前先做 mode normalize、prerequisite check、`_lgfx.init()`、rotation、dispatcher 轉交
- `ROWS_SAFE_PROGRESSIVE` 仍是下一個主要拆分目標，因為它仍是目前最大的 bytecode 風險來源

C++ (`lgfx` user module) 負責：

- `update_enemies_native(...)`
- `update_objects_native(...)`
- `render_scene_bands_rgb565(...)`
- object state / render / solids buffer 原地更新
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
- `CAMERA_RENDER_WIRE_ORDER = True`
- `CAMERA_RENDER_BACK_BUFFER = True`
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
- `objects_c_buf`
- `object_state_c_buf`
- `object_solids_c_buf`
- `monk_orb_c_buf`
- `monk_attack_c_buf`

另外目前 monk 還有三組關鍵狀態：

- `monk_encounters`
- `monk_hover_c_buf`
- `monk_attack_c_buf`

其中：

- `enemy_rows_c_buf` 不再每幀重 pack，只在初始化、swap、respawn、Python fallback 後同步
- `objects_c_buf` 現在與 `objects_rows` index-aligned；不可見 / special-render object 會保留 slot，但 render source 尺寸寫 0
- `object_state_c_buf` 是 native object update 的 state buffer，保存 world rect、source rect、visible/solid/swappable/gravity/special flags
- `object_solids_c_buf` 不再靠 Python 每幀重 pack；native object update 會在 gravity 後重建 solids buffer，swap / respawn 仍由 Python orchestration 觸發同步
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
- `lgfx.update_monk_attack_native(...)` 負責 attack type 1 的 split/drop/sweep + three-orb dive、type 2 的同步 pulse / 三顆錯峰雙峰 pulse update，以及 final one-orb player-orbit/radial-rush loop
- Python `_swap_with_monk_orb(...)` 仍負責真正 swap apply，並直接寫回 `monk_orb_c_buf`
- Python `monk_orb_damage.action_hit_player(...)` 將 mode `2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 視為第二色 damage orb；碰到玩家會沿用既有死亡 / respawn 流程。mode `9 final_orbit` 是第二色但不造成傷害；mode `1 detached` 與 `6 pulse_hold` 是公轉色，不造成傷害
- 一般 live path 不再每幀把 C buffer sync 回 Python dict；dict 只保留 fallback / intro scripted / debug shadow 用途
- attack orb swap 時，`monk_orb_c_buf` 保持 `scripted_attack` mode，render descriptor 仍必須走 native C API，不能因 Python shadow 有 `scripted_attack` 而 fallback

## 6.5 下一階段可搬的熱路徑

原則仍是「Python 當 director，C++ 吃穩定且每幀重複的 hot path」。`app_camera_test.py` 已接近 MicroPython bytecode 上限，下一階段新增 runtime 行為要先放 helper module；只有已穩定、資料形狀固定、需要每幀跑的部分才搬進 `lgfx`。

優先順序建議：

1. `update_player_native(...)`
	- 範圍：player gravity、grounded check、`_move_axis_world(...)`、unembed guard、tilemap + object solids collision。
	- 收益：這是每幀固定跑的 nested collision path，且目前仍完整在 Python。
	- 做法：先讓 C++ 回傳 `(player_x, player_y, vel_y, hit_x, hit_y, grounded)`，death / respawn / camera / swap sequencing 仍留 Python。

2. `apply_swap_native(...)` 的 object/enemy/bullet 子集
	- 範圍：一般 object、enemy、bullet 的位置交換、buffer sync、bullet owner reset。
	- 收益：swap burst 目前會拉高 update peak，且會觸發多個 Python list + C buffer 同步。
	- 做法：先不碰 monk orb final/scripted special case；一般 target kind 穩定後再擴 monk orb。

3. `update_swap_preview_native(...)` 的 object buffer allocation 清理
	- 範圍：目前 Python 呼叫前仍會臨時打包 object target buffer；可改成直接餵 `object_state_c_buf` 或常駐 preview target buffer。
	- 收益：降低 hold swap 時的 per-frame allocation / packing 成本，也減少主檔 bytecode。

4. respawn/checkpoint object restore 的 native/helper 化
	- 範圍：restore object rows、state/render/solid buffer rebuild、checkpoint skip。
	- 收益：不是最大 CPU hot path，但可繼續降低 `run()` bytecode 壓力，並避免 restore 後 buffer 漏同步。

5. descriptor packing 剩餘 Python path
	- 範圍：special object / anchor / respawn overlay descriptor、monk final path descriptor 等仍由 Python 組資料的部分。
	- 收益：只有在 `CPU_WORK.desc_us` 或 `UPDATE_BREAK` 顯示 descriptor 成本上升時才值得優先搬；render compose 本身已在 C++。

暫不建議搬：完整 monk encounter lifecycle、stage switching、SD launcher、asset cache。這些是低頻 orchestration，留 Python 比較好調整，也不值得增加 native state complexity。

## 7. 主要資產

目前主線資產都使用 wire-order RGB565：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- object / monk orb atlas：`/sd/game/picture/object/object_altes_wire.rgb565`
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
2. 清掉非主線 bring-up renderer：`ROWS_SAFE_NEAR_TILE_TEST`、`SPI_TFT_SPEED_TEST` / `SPI_TFT_BULK_WAIT_TEST`、`FULL_BUFFER_TEST` 不再留在 SD runtime 主線
3. 清掉 `SPI_TFT_*` 中目前不會被走到的多條 experimental path 分支，並移除未再使用的 `CAMERA_SPI_TEST_PATH` 設定
4. 清掉未再使用的 `BOARD_GENERATED_*`、`ROOT_RGB565_*`、`BLIT_*` modes，並同步移除它們在 mode normalize、prerequisite、startup banner、`run()` 與 config 內的殘留引用
5. 已清掉舊的 `PNG_SINGLE` / `PNG_FULL` / `FAR_ONLY` / `SINGLE_IMAGE_*` / `DIRECT_*` fallback renderer family，`run()` 只保留主線 renderer
6. 再把 `ROWS_SAFE_PROGRESSIVE` step 4 內兩塊可獨立切出的路徑抽成 helper：
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
