# MONK_ORB_ARCHITECTURE

本文件說明目前 `monk encounter + monk orb + monk body movement` 在 runtime 內的實際架構、狀態機與資料流。

## 0. 最新現況快照（2026-06-07）

目前 monk 是 `encounter actor + live enemy slot` 的混合架構，不是開場就存在的普通 live enemy。intro 前只有 Python encounter template；intro 完成後才接到 live enemy row 與 native buffers。玩家在 monk 區域 respawn 時，現有 live monk slot 會被隱藏並重用，清掉 orb/attack state 後重新跑 intro，不會重複 append 新 monk。

目前板上 tuning：

- `MONK_INTRO_DROP_SPEED = 3`
- `MONK_INTRO_TARGET_Y = 56`
- `MONK_INTRO_START_OFFSET_Y = 96`
- `MONK_HOVER_BASE_Y = 55`
- `MONK_HOVER_MIN_X = 1616`
- `MONK_HOVER_MAX_X = 1887`
- `MONK_RESPAWN_REINTRO_MIN_X = 1500`

目前 native 狀態：

- intro drop update 優先使用 `lgfx.update_monk_intro_native(...)`，Python 保留 fallback / orchestration
- live body hover 使用 native enemy update 的 static monk branch
- live orb update / descriptor / picker 使用 C++ native API
- monk attack controller 使用 native `lgfx.update_monk_attack_native(...)`
- type 1 attack：兩顆 orb split/drop/sweep
- type 2 attack：五顆 orb pulse，半徑 `28 -> 128 -> 28`，timing `60/40/60`
- action modes `2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 造成玩家死亡
- mode `1 detached`、`6 pulse_hold` 使用公轉色，不傷害玩家
- action orb 彼此 `16x16` hitbox 重疊時會停在當前 `current_x/current_y`，轉成 detached 公轉色，之後等待射線捕捉回 orbit

本次抓到一組板上 FPS sample：`PROFILE total_us=39474`、`PROFILE fps=25.33`，同段 log 後續 sample 約 `24.4-25.4 fps`。

## 1. 範圍

目前要分成三條線看：

- `monk encounter lifecycle`：主要在 MicroPython runtime 內處理
- `live monk orb`：熱路徑已搬到 C++ native buffer / native API
- `monk body movement`：位置更新已搬到 C++ native enemy update
- `monk intro drop`：update 優先走 C++ native API，Python 保留 fallback / lifecycle orchestration
- `live monk attack`：type 1 / type 2 attack state update 已搬到 C++ native API

也就是說，現在 monk 已不是單一 Python-only actor，而是：

- Python 維護 encounter / intro / swap apply / respawn reintro / scripted fallback 高階語義
- C++ 維護 intro body/orb drop update
- C++ 維護 monk 本體每幀 movement
- C++ 維護 live orb state update、descriptor packing、swap target picking
- C++ 維護 live attack phase state 與 attack orb scripted movement
- C++ band renderer 只畫最後 descriptors

其中 `encounter lifecycle` 仍然不進 native enemy AI；live orb 則已是 native packed buffer 主導。它們的實際落點如下：

- 檔案：`sd_game_template/game/app_camera_test.py`
- 不走 bullet 系統
- 不參與物理 / 重力 / 碰撞
- C++ `lgfx` 負責 live orb 幾何 update、render descriptor packing、monk orb swap target picking

monk body movement 的 native 落點：

- Python 端打包 hover state：`_pack_monk_hover_states_for_c(...)`
- Python 端呼叫 native：`_update_enemies_and_bullets_native(...)`
- C++ 端實作：`lgfx_update_enemies_native(...)`

目前 encounter lifecycle 的 Python 落點：

- `_build_monk_intro_states(...)`
- `_start_monk_intro(...)`
- `_update_monk_intro_states(...)`
- `_instantiate_live_monk_from_encounter(...)`
- `_update_monk_encounters(...)`

目前 intro render split 的 Python 落點：

- `_pack_monk_encounter_intro_body_descriptors(...)`
- `_pack_monk_encounter_intro_orb_descriptors(...)`

目前 live orb native 落點：

- Python packed buffer：`monk_orb_c_buf`
- C++ update：`lgfx.update_monk_orbs_native(...)`
- C++ descriptor packing：`lgfx.pack_monk_orb_descriptors_native(...)`
- C++ swap target picking：`lgfx.pick_swappable_monk_orb_native(...)`
- C++ attack update：`lgfx.update_monk_attack_native(...)`
- Python fallback：`_pack_monk_orb_descriptors(...)`、`_pick_swappable_monk_orb(...)`

## 2. 核心概念

目前 monk 實際上由三個鬆耦合子系統組成：

1. `monk encounter lifecycle`
2. `monk body`
3. `monk orb ring`

`monk encounter lifecycle` 負責：

- 何時從不存在變成可見 actor
- intro actor 的建立與更新
- intro 完成後何時 instantiate 成 live monk
- encounter 是否已進入 `live`

`monk body` 負責：

- 畫面上的 monk 本體位置
- 面向
- hover 動畫計數

`monk orb ring` 負責：

- 公轉中的 orb 位置
- detached 後的 world-space 固定位置
- captured return 的幾何回收
- swap target 的可選取語義
- attack 期間兩顆 scripted orb 的 native current position

目前 encounter state 有三種：

- `inactive`
- `intro_drop`
- `live`

這代表 monk 在 `camera_x < 1600` 時不應存在於 live enemy set；只有 trigger 後才會先以 intro actor 出現，intro 完成後才 append 到 live enemy rows。

目前這個 split 已經落地：

- `enemies.csv` 的 monk row 使用 `spawn_mode=encounter`
- `_split_live_enemies_and_monk_encounters(...)` 會把 monk 從 live enemy set 拆出去
- 板上已驗證 boot 時 `ENEMY_COUNT=2`，代表 monk 在 intro 前不算 live enemy

目前 orb 是「依附 monk body 中心求值」，不是完全獨立 entity。這代表 monk body 一動，orb 的 base orbit 中心也跟著動。

目前 monk orb 系統以 monk 中心為原點，將每顆 orb 視為：

- 正常時貼在自己的旋轉射線上公轉
- 交換後先離線停在固定 world position
- 當自己的那條射線旋轉掃過它時吸附回線上
- 吸附後沿線朝中心縮回正常公轉半徑

目前 live orb native mode：

- `0 orbit`
- `1 detached`
- `2 captured_return`
- `3 scripted_intro`
- `4 scripted_attack`
- `5 pulse_damage`
- `6 pulse_hold`
- `255 unused`

## 3. 正常公轉

正常公轉不是獨立 enemy，也不是 bullet，而是每幀從 monk 中心和 slot 算出來的 render 成員。

關鍵常數：

- `_MONK_ORB_COUNT = 5`
- `_MONK_ORB_RADIUS = 28`
- `_MONK_ORB_W = 16`
- `_MONK_ORB_H = 16`
- `_MONK_ORB_TABLE_SIZE = 60`
- `_MONK_ORB_RAD_PER_IDX = 2π / _MONK_ORB_TABLE_SIZE`

每顆 orb 的基礎旋轉角度由：

- `_monk_orb_slot_angle_rad(anim_counter, slot_i)`

計算方式：

- `line_angle = anim_counter * RAD_PER_IDX + slot_phase`
- `slot_phase = slot_i * 72°`

正常位置由：

- `_monk_orb_slot_world_pos(...)`

計算，即：

- `orbit position = line_angle + fixed radius`

目前 intro 期間也已改成沿用同一套 orbit 幾何：

- intro orb 不再各自直落
- intro 期間每顆 orb 會跟著下落中的 monk body 持續公轉
- intro 結束時會把當前 `anim_counter + orb_states` 直接交接給 live monk，避免切換時跳角度

## 4. Persistent state

目前 live orb 的 authoritative state 是 native packed buffer：

- `monk_orb_c_buf`
- `_MONK_ORB_NATIVE_STRIDE = 16`

每筆 native orb row：

- `mode` `u8`
- `slot` `u8`
- `capture_lock` `u8`
- `flags/current_valid` `u8`
- `detached_x` `i16`
- `detached_y` `i16`
- `return_radius` `i16`
- `current_x` `i16`
- `current_y` `i16`

live modes 對應：

- `0`：orbit
- `1`：detached
- `2`：captured_return
- `3`：scripted_intro
- `4`：scripted_attack
- `5`：pulse_damage
- `6`：pulse_hold
- `255`：unused

目前同一個 mode byte 也決定 sprite row 與 damage：`0 orbit` / `1 detached` / `3 scripted_intro` / `6 pulse_hold` 維持目前公轉顏色；`2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 使用第二色，碰到玩家會死亡。

一般 live path 現在不再每幀把 C buffer sync 回 Python dict；Python dict 只保留 fallback、debug、scripted mode shadow 用途。

每隻 monk 都有自己的 orb slot states，由：

- `_build_monk_orb_states(...)`

建立。

Python shadow 每顆 orb 目前保存：

- `slot`
- `mode`
- `detached_x`
- `detached_y`
- `return_radius`
- `capture_lock`

在目前版本中，orb state 還多了 script 期欄位，用來支援 intro 與 attack：

- `script_x`
- `script_y`
- `script_target_x`
- `script_target_y`

目前已使用的 scripted mode：

- `_MONK_ORB_MODE_SCRIPTED_INTRO`
- `_MONK_ORB_MODE_SCRIPTED_ATTACK`

其中 intro 與 attack type 1 都已在主線啟用。`scripted_attack` 的 authoritative position 在 `monk_orb_c_buf.current_x/current_y`，Python dict 只保留 shadow/fallback/debug 欄位。

attack controller 另有一組 native buffer：

- `monk_attack_c_buf`
- `_MONK_ATTACK_NATIVE_STRIDE = 16`

每筆 attack row：

- `0`: `phase`，`0 idle`、`1 split`、`2 drop`、`3 sweep`、`4 pulse_expand`、`5 pulse_hold`、`6 pulse_shrink`
- `1`: `prev_hover_cd`
- `2`: left attack slot，idle 時 `0xFF`；pulse phase 時是 phase step counter
- `3`: right attack slot，idle 時 `0xFF`
- `4..5`: left target X
- `6..7`: right target X
- `8..9`: left target Y
- `10..11`: right target Y
- `12`: left horizontal direction，signed byte
- `13`: right horizontal direction，signed byte
- `14`: attack cadence toggle；waypoint interval 交替觸發，`0` 表示這次可攻擊，`1` 表示這次 skip
- `15`: attack type turn；`0` 表示下一次可攻擊機會用 type 1，`1` 表示下一次可攻擊機會嘗試 type 2 pulse

monk 區域 respawn reintro 不會重建整組 enemy runtime。`_reset_monk_for_respawn_reintro(enemy_rt)` 會就地處理現有 live monk slot：

- 將 live monk row visible 設為 `0`
- reset 該 enemy state
- 將該 monk 的 `monk_orb_states` 清為 `None`
- 將對應 `monk_orb_c_buf` entries 設為 mode `255 unused`
- 將對應 `monk_attack_c_buf` phase 清回 idle
- encounter 回到 `inactive`，intro state 設為 `idle + armed`

下一次 `camera_x >= 1600` 時會重新進入 `intro_drop`；intro 完成後 `_instantiate_live_monk_from_encounter(...)` 會復用該 live slot，不再 append 新 row。

另外 encounter 本身目前還會保存：

- `state`
- `template_row`
- `template_meta`
- `intro_state`
- `live_enemy_i`
- `body_x`
- `body_y`
- `body_target_x`
- `body_target_y`
- `body_target_bottom_y`
- `anim_counter`
- `orbs`
- `orb_states`

注意：

- 不再保存 `offset_x/offset_y`
- 不再依賴 `return_angle_idx` 作為主幾何狀態
- detached 時用 world position
- captured_return 時只保存 radius，角度直接跟當前射線同步

## 5. 三態模型

### 5.1 `orbit`

- orb 在自己的旋轉線上
- 半徑固定為 `_MONK_ORB_RADIUS`
- 角速度等於一般公轉速度

### 5.2 `detached`

- 玩家與 orb 交換後，orb 留在交換後 world position
- 位置由：
  - `detached_x`
  - `detached_y`
- orb 不主動追線
- 等自己的那條線轉到它附近
- 使用公轉色 sprite，不造成傷害

### 5.3 `captured_return`

- 線掃到 orb 後吸附回線上
- 一旦吸附，角度直接等於當前 `line_angle`
- orb 只沿著線 inward return
- 半徑由 `return_radius` 向 `_MONK_ORB_RADIUS` 收斂
- 到達正常公轉半徑後切回 `orbit`
- 使用第二色 sprite，16x16 hitbox 碰到玩家會死亡

### 5.4 `scripted_attack`

- attack type 1 期間使用
- 只由 `lgfx.update_monk_attack_native(...)` 推進
- `lgfx.update_monk_orbs_native(...)` 對 mode `4` 只保留目前 `current_x/current_y`，不重新計算公轉位置
- descriptor packing、swap target picking、swap candidate distance 都必須讀 `monk_orb_c_buf.current_x/current_y`
- Python shadow 不可把 `scripted_attack` 視為需要 render fallback 的 scripted mode，否則畫面會切回 stale Python orbit/script position
- 使用第二色 sprite，16x16 hitbox 碰到玩家會死亡

### 5.5 `pulse_damage` / `pulse_hold`

- attack type 2 期間使用
- 5 顆 orb 必須全在 `orbit` 才會啟動；若有任一顆 detached / captured_return / scripted_attack，這次 type 2 不發動，下一個可攻擊機會仍會再嘗試 type 2
- 5 顆 orb 保持在各自旋轉射線上，角度照一般公轉走，只改半徑
- 半徑流程：`28 -> 128` 花 60 frame，`128` 停 40 frame，`128 -> 28` 花 60 frame
- expand / shrink 使用 mode `5 pulse_damage`，第二色 sprite，碰到玩家會死亡
- hold 使用 mode `6 pulse_hold`，公轉色 sprite，不造成傷害
- pulse 期間若其中一顆被 swap，該顆進入一般 `detached -> captured_return -> orbit` 流程；其他仍在 pulse 的 orb 不取消，繼續目前 expand / hold / shrink phase
- 完成後全部回到 mode `0 orbit`、半徑 `28`

### 5.6 第二色 damage

第二色 orb damage 目前由小型 Python helper module 處理：

- `sd_game_template/game/monk_orb_damage.py`
- runtime import 名稱：`monk_orb_damage`
- main loop 在玩家 movement / collision settle 後呼叫 `monk_orb_damage.action_hit_player(...)`

此 helper 直接掃描 `monk_orb_c_buf`：

- stride 仍為 `_MONK_ORB_NATIVE_STRIDE = 16`
- mode `2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 視為可傷害玩家
- hitbox 使用 orb 的 `current_x/current_y` 與固定 `16x16`
- 命中時回傳 `(orb_index, mode, x, y)`，主迴圈會印 `PLAYER_KILLED_BY_MONK_ORB ...`，再把玩家導入既有 `PLAYER_DEAD_WAIT_RESPAWN` 流程

攻擊色 orb 之間也會用同一個 `16x16` hitbox 做重疊判定。若任兩顆 mode `2 captured_return`、`4 scripted_attack`、`5 pulse_damage` 的 hitbox 重疊，重疊到的 orb 會停在各自當前 `current_x/current_y`，轉成 mode `1 detached`，因此變回公轉色且不再傷害玩家。之後照既有 detached 規則等待射線捕捉，進 `captured_return` 回 orbit。若是在 type 2 pulse 中發生，只有重疊到的 orb 離開 pulse，其他 pulse orb 繼續目前 phase。

設計原因：`app_camera_test.py` 已接近 MicroPython bytecode 上限。曾將完整 damage scan helper 直接放入主檔，板上啟動會出現 `RuntimeError: bytecode overflow`；因此新增 runtime 行為應優先拆小 module，主迴圈只留短呼叫。

## 6. 吸附條件

目前 detached -> captured_return 的判定不是純 `angle_idx` 比較，而是幾何判定。

關鍵 helper：

- `_monk_orb_rel_to_center(...)`
- `_quantize_monk_orb_polar(...)`
- `_step_monk_orb_state(...)`

目前 capture 使用：

- `along > 0`
- `perp <= _MONK_ORB_CAPTURE_LINE_EPS`

其中：

- `along`：orb 是否在該旋轉線前方
- `perp`：orb 到該旋轉線的垂直距離

為了避免在邊界附近抖動，還有：

- `_MONK_ORB_CAPTURE_LOCK_FRAMES`

作為短暫鎖定。

## 7. 位置求值

live orb 每幀當前世界座標由 C++ 更新：

- `lgfx.update_monk_orbs_native(...)`

它會原地更新 `monk_orb_c_buf` 的：

- `mode`
- `capture_lock`
- `return_radius`
- `current_x/current_y`

Python fallback 座標 helper 仍保留：

- `_monk_orb_current_world_pos(...)`

決定。

行為如下：

- `orbit` -> 直接回傳 base orbit world position
- `detached` -> 直接回傳固定 detached world position
- `captured_return` -> 以當前射線角度 + `return_radius` 算世界座標

正常 native path 下：

- render descriptor packing 直接讀 `monk_orb_c_buf.current_x/current_y`
- swap target picking 直接讀 `monk_orb_c_buf.current_x/current_y`
- swap apply 優先讀 / 寫 `monk_orb_c_buf`

只有 fallback、`scripted_intro` 或 debug shadow 需要 Python dict 座標同步。`scripted_attack` 已 native 化，render descriptor 必須繼續走 C API。

## 8. 與 swap 的接法

交換入口仍在：

- `_perform_world_swap(...)`

若挑到 monk orb，則走：

- `_pick_swappable_monk_orb(...)`
- `_swap_with_monk_orb(...)`

目前 `_pick_swappable_monk_orb(...)` 會優先呼叫：

- `lgfx.pick_swappable_monk_orb_native(...)`

native picker 直接吃：

- `enemy_rows_c_buf`
- `monk_orb_c_buf`
- player / camera / band bounds

並回傳：

- `enemy_i`
- `slot_i`
- `d2`

Python 仍負責真正 swap apply，不把 full world swap 搬進 C++。

交換後會：

- 玩家移到 orb 當前位置
- 若 orb 不是 attack orb：orb native buffer 寫入 `detached_x/detached_y/current_x/current_y`，`mode = detached`，`return_radius` 設回 baseline，等待之後被捕捉
- 若 orb 是 attack orb：orb native buffer 寫入新的 `current_x/current_y`，但 `mode` 保持 `scripted_attack`，attack state 的 slot 不變

attack swap continuation 的實際語義：

- phase 1 split：被玩家交換後，該 orb 從交換後位置繼續沿原本水平方向移動
- phase 2 drop：被玩家交換後，繼續朝指定 Y 收斂；若交換後已越過指定 Y，則往回移到指定 Y
- phase 3 sweep：被玩家交換後，繼續沿原本 sweep 水平方向移動
- phase done：兩顆 attack orb 進 `detached` 回收模式，與一般被玩家交換後一樣等待 orb ring 捕捉

目前還有兩個重要語義修正已落地：

- monk orb 的 pick 與 render 現在都共用 native current position
- monk 本體已從 generic enemy swap target 排除，不再和一般 enemy 共用選取語義

## 9. Render 路徑

orb 最終不是 Python 直接畫，而是 pack 成 special descriptor 給 native band pipeline。

live orb 主要入口：

- `_pack_monk_orb_descriptors_native(...)`
- `lgfx.pack_monk_orb_descriptors_native(...)`

它會：

1. 讀 `enemy_rows_c_buf` 與 `monk_orb_c_buf`
2. 直接使用 native `current_x/current_y`
3. 產生 `_SPECIAL_KIND_MONK_ORB` descriptors（8 bytes：`x i16, y i16, kind, slot, mode, 0`）
4. 交給 native band renderer

Python `_pack_monk_orb_descriptors(...)` 仍保留為 fallback。現在只有 `scripted_intro` 會優先走 fallback；`scripted_attack` 已完全走 native descriptor。

目前重要約定：

- `scripted_intro` 仍可觸發 Python descriptor fallback
- `scripted_attack` 不可觸發 Python descriptor fallback，必須繼續用 `lgfx.pack_monk_orb_descriptors_native(...)`
- descriptor byte 6 必須保存 native mode，native renderer 依此選擇公轉色或第二色
- 否則被 swap 的 attack orb 會看起來停住，另一顆 attack orb 會看起來回到 stale Python 公轉位置

目前 monk orb atlas source：

- `OBJECTS_ATLAS_RGB565_PATH = "game/picture/object/object_altes_wire.rgb565"`
- `ENEMY_MONK_ORB_ATLAS_RGB565_PATH = "game/picture/object/object_altes_wire.rgb565"`
- 公轉 / detached / intro sprite：`(96,16,16,16)`
- captured_return / scripted_attack / pulse_damage sprite：`(96,32,16,16)`
- pulse_hold sprite：`(96,16,16,16)`

因 object atlas 與 monk orb atlas path / size 相同，runtime 會重用同一份已載入 bytes，避免 RAM 中存在兩份 256x256 RGB565 atlas。

因此 live orb path 現在是：C++ 更新 state/current，C++ 產生 descriptor，C++ renderer 畫 descriptor；Python 只處理高階 lifecycle / swap apply。

目前 intro render 已與 live render split：

- `intro_drop` 期間：
  - body 走 `_pack_monk_encounter_intro_body_descriptors(...)`
  - orb 走 `_pack_monk_encounter_intro_orb_descriptors(...)`
- `live` 期間：
  - body 回到一般 live enemy render
  - orb 回到 `_pack_monk_orb_descriptors(...)`

另外已修正的一個重要對齊點：

- intro body render 現在與 live monk 共用同一套 draw-origin 計算
- 不再把 intro body box 左上直接當成最終 sprite draw origin

## 10. Monk body movement 架構

目前 monk 本體移動已不走 Python fallback 的一般 enemy AI，而是走 native `static enemy` 分支。

目前已確定的目標模型是：

- 在指定矩形內挑一個 waypoint
- 直接往該 waypoint 移動
- 目前先不疊任何正弦運動

### 10.1 Python 端資料準備

初始化時：

- `_load_enemy_runtime_assets(...)` 會建立 `monk_hover_c_buf`
- 每筆 hover state stride 為 `_MONK_HOVER_STATE_STRIDE = 11`

目前 packed 欄位如下：

- `target_x` `i16`
- `target_y` `i16`
- `base_y` `i16`
- `phase` `u16`
- `retarget_cd` `u8`
- `speed_q8` `i16`

目前 Python 端初始化策略：

- `target_x` 先設在 `[MONK_HOVER_MIN_X, MONK_HOVER_MAX_X]` 中點
- `target_y` 先設成 `MONK_HOVER_BASE_Y`
- `phase` 依 enemy index 給 seed
- `retarget_cd` 先設為 `MONK_HOVER_RETARGET_FRAMES`

目前板上 config 基線：

- `MONK_HOVER_MIN_X = 1616`
- `MONK_HOVER_MAX_X = 1887`
- `MONK_HOVER_BASE_Y = 55`
- `MONK_HOVER_AMP = 39`
- `MONK_HOVER_PHASE_STEP = 1`
- `MONK_HOVER_WAVE_AMP_X = 0`
- `MONK_HOVER_WAVE_AMP_Y = 0`
- `MONK_HOVER_RETARGET_FRAMES = 30`
- `MONK_HOVER_TARGET_EPS = 12`
- `MONK_HOVER_SPEED_Q8 = 512`

其中：

- `BASE_Y / AMP` 目前主要仍供 Python 初始化 `target_y` 範圍使用
- `WAVE_AMP_X / WAVE_AMP_Y` 雖然 native 路徑仍保留欄位與計算位置，但目前設為 `0`，等價於關閉正弦擾動

### 10.2 Native 更新路徑

`lgfx_update_enemies_native(...)` 對 `static_enemy` 會走 monk hover 分支：

1. 從 `monk_hover_c_buf` 讀 hover state
2. 若已接近目前 target，且 `retarget_cd <= 0`，則在矩形範圍內重抽新 waypoint
3. `wx` 平滑追向 `target_x`
4. `wy` 平滑追向 `target_y`
5. 把更新後的 `wx/wy` 回寫到 enemy row
6. 把新的 target/phase/cd/speed 回寫到 hover buffer

當前 native 固定常數仍寫在 C++ 內：

- `monk_hover_min_x = 1616`
- `monk_hover_max_x = 1887`
- `monk_hover_min_y = 32`
- `monk_hover_max_y = 111`
- `monk_hover_target_eps = 12`
- `monk_hover_retarget_frames = 30`

另外目前 native 仍保留：

- `monk_hover_phase_step`
- `monk_hover_wave_amp_x`
- `monk_hover_wave_amp_y`

但因為板上 config 已將 `WAVE_AMP_X/Y` 設為 `0`，目前等價於不使用正弦擾動。

這代表目前 `config.py` 雖然已提供 `MONK_HOVER_*` 參數，但 native 真正使用的矩形邊界仍有一部分寫死在 C++ 內；Python config 與 C++ 常數目前是人工保持一致。

### 10.3 目前實際行為

目前板上 monk body 的實際行為是：

- x/y 都會追 waypoint
- 追向速度由 16-bit `speed_q8` 控制
- 目前不疊任何正弦擾動
- orb 的 base orbit 中心會跟著 monk body 移動

這一版已經不是「固定 base_y 原地上下浮」，也不是「追 target 再加波動」的版本。當前主線就是純 waypoint movement。

另外已確認修掉的兩個歷史 bug：

- 舊版曾把 `wy` 蓋回固定基線，導致垂直追點失效
- 舊版 `speed_q8` 只有 1 byte，導致速度表達錯誤；目前已改成 16-bit packed value

目前仍非最終設計的地方：

- waypoint 範圍部分常數仍硬編碼在 C++
- body 與 orb ring 的耦合仍然直接
- 到點後是否停留、如何挑下一點，目前仍是簡單版本

另外目前 live handoff 的一個重要細節已落地：

## 11. Native API 與驗證標記

目前 live monk/orb 相關 native API：

- `lgfx.update_monk_intro_native(...)`
- `lgfx.update_monk_orbs_native(...)`
- `lgfx.pack_monk_orb_descriptors_native(...)`
- `lgfx.pick_swappable_monk_orb_native(...)`
- `lgfx.update_monk_attack_native(...)`

板上啟動驗證應看到：

- `MONK_ORB_UPDATE_IMPL=C_API`
- `MONK_ORB_DESC_IMPL=C_API`

快速 API 驗證：

```python
import lgfx
print(hasattr(lgfx, "update_monk_orbs_native"))
print(hasattr(lgfx, "update_monk_intro_native"))
print(hasattr(lgfx, "pack_monk_orb_descriptors_native"))
print(hasattr(lgfx, "pick_swappable_monk_orb_native"))
print(hasattr(lgfx, "update_monk_attack_native"))
```

attack swap 驗證 marker：

- `MONK_ATTACK_NATIVE_START ...`
- `MONK_ATTACK_NATIVE_PHASE ... phase=drop`
- `MONK_ATTACK_NATIVE_PHASE ... phase=sweep`
- `MONK_ATTACK_NATIVE_SKIP ...`
- `SWAP_MONK_ORB_ATTACK_CONTINUE ...`
- `MONK_ATTACK_NATIVE_DONE ...`
- `PLAYER_KILLED_BY_MONK_ORB ...`
- `PLAYER_DEAD_WAIT_RESPAWN ...`
- `MONK_RESPAWN_REINTRO_RESET ...`

最近已驗證：`MONK_ORB_DESC_IMPL=C_API`、`SWAP_MONK_ORB_ATTACK_CONTINUE` 出現後，attack 仍會繼續進入 drop/sweep/DONE，且沒有 `MONK_ATTACK_NATIVE_FAIL` / `MONK_ORB_DESC_NATIVE_FAIL`。攻擊 cadence 已改為 waypoint interval 一次攻擊、一次 skip，板上 log 出現 `MONK_ATTACK_NATIVE_START ...` -> `MONK_ATTACK_NATIVE_DONE ...` -> `MONK_ATTACK_NATIVE_SKIP ...` -> 下一次 `MONK_ATTACK_NATIVE_START ...`。第二色 orb damage 也已在板上 log 出現 `PLAYER_KILLED_BY_MONK_ORB index=11 mode=2 ...`，並接續 `PLAYER_DEAD_WAIT_RESPAWN checkpoint=1 camera_target=0`。

最近 profile 紀錄：

- 穩態 log：`/tmp/esp_profile_render_native_orb_pick.log`
- swap burst rerun log：`/tmp/esp_profile_render_native_orb_pick_rerun.log`

穩態 sample：

- `update_avg=6509.7us`
- `fps_avg=25.76`
- 無 `Traceback`
- 無 `SAFE MODE`
- 無 `MONK_ORB_PICK_NATIVE_FAIL`

swap burst sample：

- `swap_events=31`
- `update_avg=8939.7us`
- `update_max=12926us`
- 無 `Traceback`
- 無 `SAFE MODE`
- 無 `MONK_ORB_PICK_NATIVE_FAIL`

2026-06-07 重新抓的一組 profile/FPS sample：

- log：`/tmp/monk_fps_sample.log`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `MONK_ORB_UPDATE_IMPL=C_API`
- `MONK_ORB_DESC_IMPL=C_API`
- `PROFILE update_us=7062`
- `PROFILE submit_us=31582`
- `PROFILE submit_wait_us=17010`
- `PROFILE submit_dma_wait_us=16906`
- `PROFILE total_us=39474`
- `PROFILE fps=25.33`
- 後續 sample 約在 `24.4-25.4 fps`

這代表目前高點主要是 swap/debug burst，不是 live orb steady-state update 退步。

## 12. 後續建議

目前 monk/orb 優化可先告一段落。後續若要再整理，優先順序建議：

1. 加 `SWAP_DEBUG_VERBOSE`，把 `SWAP_*` debug print 分級，讓 profile 更乾淨。
2. 加 `PROFILE swap_us`，把 swap/debug burst 從 `update_us` 中拆出來看。
3. 等 attack 規則穩定後，再考慮 scripted attack orb native 化。
4. 若還要新增 C++ gameplay API，避免繼續塞進 `lgfx_mp.cpp`，優先放在 `lgfx_band.cpp` 或新拆 `lgfx_gameplay.cpp`，避免 ESP32S3 literal range link 問題。

- intro 完成時會 append 新的 live monk row 到 `enemy_rows`
- 同步擴充 `enemy_rows_c_buf`
- 同步擴充 `monk_hover_c_buf`
- 並將新的 `enemy_rows_c_count / monk_hover_c_count` 回傳給主迴圈

這是為了避免發生「intro 結束後 monk 看起來已出現，但 native update 根本沒開始更新新 row」的停住問題。

目前板上已驗證：

- `MONK_INTRO_DONE`
- `MONK_LIVE_INSTANTIATED`
- `MONK_ENCOUNTER_STATE=live`
- 後續可看到 `MONK_HOVER_DBG` 持續更新

## 11. 目前仍可能需要調整的手感參數

與手感相關的主要參數：

- `_MONK_ORB_CAPTURE_LINE_EPS`
- `_MONK_ORB_CAPTURE_LOCK_FRAMES`
- `_MONK_ORB_RETURN_RADIUS_DIV`
- `_MONK_ORB_RETURN_RADIUS_MIN_STEP`

與 monk body movement 相關的主要參數：

- `MONK_HOVER_MIN_X`
- `MONK_HOVER_MAX_X`
- `MONK_HOVER_BASE_Y`
- `MONK_HOVER_AMP`
- `MONK_HOVER_PHASE_STEP`
- `MONK_HOVER_WAVE_AMP_X`
- `MONK_HOVER_WAVE_AMP_Y`
- `MONK_HOVER_RETARGET_FRAMES`
- `MONK_HOVER_TARGET_EPS`
- `MONK_HOVER_SPEED_Q8`

如果 capture 太晚、太早、或沿線回歸太快，優先調這幾個值，而不是重做整個模型。

如果 monk body 的移動感不對，則優先檢查：

- target 抽樣範圍是否合理
- `speed_q8` 是否過慢或過快
- `retarget_cd` 是否導致太頻繁或太晚換點
- 當前是否真的需要再打開 `X/Y` 正弦擾動
- monk body 與 orb ring 是否需要解耦更多層

## 12. 目前已知原則

- 不把 orb 當 bullet
- 不把 orb 變成完整 enemy
- detached 用 world-space 固定位置
- captured_return 角度永遠跟當前線同步
- int rounding 盡量延後到最後 render pack
- monk body movement 與 orb state machine 目前是分層處理，不再混成單一 enemy 行為
- monk 本體不應再回到 generic enemy swap / generic enemy bullet hit 語義
- monk 目前主線是純 waypoint movement；正弦擾動目前已關閉

## 13. 目前 lifecycle 現況

目前已經落地並板上驗證的 lifecycle 是：

1. `inactive`
2. `camera_x >= 1600` 觸發 encounter
3. `intro_drop`
4. monk body 自上方落下
5. orb 在下落期間持續公轉
6. `MONK_INTRO_DONE`
7. instantiate 成 live monk
8. live monk 接回 native hover / waypoint movement

目前已板上驗證的關鍵訊號：

- `MONK_ENCOUNTER_STATE=intro_drop`
- `MONK_INTRO_START encounter=0 x=1744 y=56`
- `MONK_INTRO_DONE encounter=0 x=1744 y=56`
- `MONK_LIVE_INSTANTIATED idx=... x=1744 y=56`
- `MONK_ENCOUNTER_STATE=live`
- `MONK_RESPAWN_REINTRO_RESET player_x=...`（monk 區域 respawn 時）

也就是說，monk 現在不再是「開場就藏在 live enemy set 裡」，而是完整的延遲 encounter actor。

## 14. C++ 遷移方向

目前最值得搬進 C++ 的，不是整個 `run()` 主迴圈，而是 monk encounter 這條每幀熱路徑。

原因：

- profile 顯示 FPS 下降的主要來源是 `update_us` 上升，不是 `submit_compose_us` 明顯爆掉
- 目前最熱、也最分裂的邏輯是：
  - encounter lifecycle
  - intro body update
  - intro orb 公轉
  - intro -> live handoff

### 14.1 建議保留在 Python 的部分

- CSV / config 載入
- 關卡資源路徑
- 玩家控制與一般高層遊戲流程
- save / respawn / checkpoint 類流程
- debug gate 與實驗性調參

### 14.2 建議先搬到 C++ 的部分

- `inactive -> intro_drop -> live` state machine
- intro body drop 更新
- intro orb 公轉與 scripted state
- intro 完成後直接接 live hover / waypoint
- monk body / orb descriptor 打包

### 14.3 建議的遷移邊界

不要把整個主遊戲邏輯一次重寫成 C++。

比較合理的做法是建立 `monk encounter native island`：

- Python 只提供 template / config / 初始資料
- C++ 維護 monk encounter 的 packed state
- C++ 每幀更新 monk encounter
- C++ 直接產生 monk body/orb render descriptors

### 14.4 第一階段實作目標

第一階段最合理的目標是：

1. 定義 `monk encounter native buffer` 與固定 stride
2. 把 `_update_monk_encounters(...) + _update_monk_intro_states(...)` 搬成單一 native update
3. 先保留 Python 端資源載入與高層流程
4. 穩定後再把 descriptor packing 也搬下去

這樣可以先把現在最熱的每幀 Python 狀態機拿掉，而不需要同時重寫整個 game runtime。
