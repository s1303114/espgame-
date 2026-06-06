# MONK_ORB_ARCHITECTURE

本文件說明目前 `monk orb + monk body movement` 在 runtime 內的實際架構、狀態機與資料流。

## 1. 範圍

目前要分成兩條線看：

- `monk orb`：主要在 MicroPython runtime 內處理
- `monk body movement`：位置更新已搬到 C++ native enemy update

也就是說，現在 monk 已不是單一 Python-only actor，而是：

- Python 維護 monk/orb 高階語義
- C++ 維護 monk 本體每幀 movement
- C++ band renderer 只畫最後 descriptors

其中 orb 這條線目前仍然不進 native enemy AI。它的實際落點如下：

- 檔案：`sd_game_template/game/app_camera_test.py`
- 不走 bullet 系統
- 不參與物理 / 重力 / 碰撞
- C++ `lgfx` 只負責 render 最終 descriptors

monk body movement 的 native 落點：

- Python 端打包 hover state：`_pack_monk_hover_states_for_c(...)`
- Python 端呼叫 native：`_update_enemies_and_bullets_native(...)`
- C++ 端實作：`lgfx_update_enemies_native(...)`

## 2. 核心概念

目前 monk 實際上由兩個鬆耦合子系統組成：

1. `monk body`
2. `monk orb ring`

`monk body` 負責：

- 畫面上的 monk 本體位置
- 面向
- hover 動畫計數

`monk orb ring` 負責：

- 公轉中的 orb 位置
- detached 後的 world-space 固定位置
- captured return 的幾何回收
- swap target 的可選取語義

目前 orb 是「依附 monk body 中心求值」，不是完全獨立 entity。這代表 monk body 一動，orb 的 base orbit 中心也跟著動。

目前 monk orb 系統以 monk 中心為原點，將每顆 orb 視為：

- 正常時貼在自己的旋轉射線上公轉
- 交換後先離線停在固定 world position
- 當自己的那條射線旋轉掃過它時吸附回線上
- 吸附後沿線朝中心縮回正常公轉半徑

目前狀態機有三種 mode：

- `orbit`
- `detached`
- `captured_return`

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

## 4. Persistent state

每隻 monk 都有自己的 orb slot states，由：

- `_build_monk_orb_states(...)`

建立。

每顆 orb 目前保存：

- `slot`
- `mode`
- `detached_x`
- `detached_y`
- `return_radius`
- `capture_lock`

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

### 5.3 `captured_return`

- 線掃到 orb 後吸附回線上
- 一旦吸附，角度直接等於當前 `line_angle`
- orb 只沿著線 inward return
- 半徑由 `return_radius` 向 `_MONK_ORB_RADIUS` 收斂
- 到達正常公轉半徑後切回 `orbit`

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

每幀 orb 當前世界座標統一由：

- `_monk_orb_current_world_pos(...)`

決定。

行為如下：

- `orbit` -> 直接回傳 base orbit world position
- `detached` -> 直接回傳固定 detached world position
- `captured_return` -> 以當前射線角度 + `return_radius` 算世界座標

這代表 render、pick、swap debug 都應共用同一個 world position helper，避免模型不一致。

## 8. 與 swap 的接法

交換入口仍在：

- `_perform_world_swap(...)`

若挑到 monk orb，則走：

- `_pick_swappable_monk_orb(...)`
- `_swap_with_monk_orb(...)`

交換後會：

- 玩家移到 orb 當前位置
- orb 寫入：
  - `detached_x`
  - `detached_y`
- orb mode 切成 `detached`
- `return_radius` 設回 baseline，等待之後被捕捉

目前還有兩個重要語義修正已落地：

- monk orb 的 pick 與 render 現在都共用 `_monk_orb_current_world_pos(...)`
- monk 本體已從 generic enemy swap target 排除，不再和一般 enemy 共用選取語義

## 9. Render 路徑

orb 最終不是 Python 直接畫，而是 pack 成 special descriptor 給 native band pipeline。

主要入口：

- `_pack_monk_orb_descriptors(...)`

它會：

1. 依每個 monk / slot 取 orb state
2. 呼叫 `_monk_orb_current_world_pos(...)`
3. 產生 `_SPECIAL_KIND_MONK_ORB` descriptors
4. 交給 native band renderer

因此 C++ `lgfx` 不知道 orb 的 detached/captured/orbit 狀態；C++ 只負責畫 descriptor。

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
- `MONK_HOVER_BASE_Y = 71`
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
