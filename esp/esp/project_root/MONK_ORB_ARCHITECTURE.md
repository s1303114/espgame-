# MONK_ORB_ARCHITECTURE

本文件說明目前 `monk orb` 在 runtime 內的實際架構、狀態機與資料流。

## 1. 範圍

這條線目前完全在 MicroPython runtime 內處理：

- 檔案：`sd_game_template/game/app_camera_test.py`
- 不走 bullet 系統
- 不參與物理 / 重力 / 碰撞
- C++ `lgfx` 只負責 render 最終 descriptors

## 2. 核心概念

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

## 10. 目前仍可能需要調整的手感參數

與手感相關的主要參數：

- `_MONK_ORB_CAPTURE_LINE_EPS`
- `_MONK_ORB_CAPTURE_LOCK_FRAMES`
- `_MONK_ORB_RETURN_RADIUS_DIV`
- `_MONK_ORB_RETURN_RADIUS_MIN_STEP`

如果 capture 太晚、太早、或沿線回歸太快，優先調這幾個值，而不是重做整個模型。

## 11. 目前已知原則

- 不把 orb 當 bullet
- 不把 orb 變成完整 enemy
- detached 用 world-space 固定位置
- captured_return 角度永遠跟當前線同步
- int rounding 盡量延後到最後 render pack
