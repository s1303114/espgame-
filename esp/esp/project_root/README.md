# 目前架構說明書（Camera Test 主線）

本文件描述目前 Camera Test 主線的實際架構（以目前程式碼與板上行為為準）。

---

## 1. 啟動與入口

- 韌體啟動後由 `main.py` 進入 `test_entry.py`。
- 目前 `test_entry.py` 是 `MODE="TEST"`。
- `sd_game_template/game/app.py` 目前固定進入 `sd_game_template/game/app_camera_test.py`
- 目前已改為：
  - `TEST_MAX_FRAMES <= 0` 時，不傳 `max_frames`，測試不會在 300 幀自動結束。

---

## 2. 畫面渲染主線（Step 4）

### 2.1 每幀流程

1. 讀輸入（搖桿 + 按鍵）
2. 玩家移動與重力更新
3. 物件交換（X: far / Y: near）
4. object 重力更新（每幀）
5. 相機 `camera_x` 更新
6. 以 `scene_buf` 做整屏合成（320x240）
7. 全屏提交到 TFT（full-screen bulk）

### 2.2 full-screen submit

- 目前是整屏提交，不走 dirty rect 主線。
- log 會看到 `FULLSCREEN_BULK_SUBMIT_OK`。
- `submit_us` 是主要成本之一。

---

## 3. 資產與路徑

### 3.1 背景 / Tilemap

- far 背景：先載入 RAM 快取（減少每幀讀檔）。
- Tilemap CSV：
  - `game/Tilemap/map1_tilemap.csv`
- Tileset RGB565：
  - `game/Tilemap/tilemap_all_wire.rgb565`

### 3.2 Objects

- 物件表：
  - `game/picture/object/objects.csv`
- 物件圖集：
  - `game/picture/object/objects_atlas_wire.rgb565`

> 注意：`objects.csv` 路徑之前有切到 `game/picture/player/object/...`，會導致 `OBJECT_MODE_OFF`。目前主線已回到 `game/picture/object/objects.csv`。

---

## 4. C++ / MicroPython 分工

### 4.1 C++（LGFX 擴充）

目前主線使用 C API 進行重負載合成：

- `compose_tilemap_rgb565(...)`
- `compose_objects_atlas_rgb565(...)`
- `compose_colorkey_rgb565(...)`（玩家 sprite colorkey）

透明處理使用 colorkey（粉紅 `#FF00FF`），wire-order 主線下會用對應 key 值。

### 4.2 MicroPython

- 遊戲邏輯（輸入、交換、重力、相機）在 Python。
- 交換、重力、物件座標更新後，會回寫 object C 緩衝，讓 C++ 合成立即生效。

---

## 5. 玩家與物件邏輯

### 5.1 玩家重力

- 每幀先判腳下是否有支撐（tilemap / solid object）。
- 無支撐：`vel_y += gravity`（上限 `fall_speed_max`）。
- 有支撐：落地時 `vel_y = 0`。
- 使用 `_move_axis_world(...)` 做像素級碰撞移動。

### 5.2 物件重力（目前已開）

- 每幀對 `objects_rows` 做下落更新。
- 條件：`OBJECT_GRAVITY_ENABLED=True` 且 `OBJECT_GRAVITY_STEP>0`。
- 規則：每幀最多下落 `OBJECT_GRAVITY_STEP` 像素，遇到 tilemap 實體停止。
- 更新後同步 `_repack_single_object_entry(...)` 到 C 緩衝。

### 5.3 Swap（X/Y）

- X：最遠可交換目標（鏡頭內）
- Y：最近可交換目標（鏡頭內）
- 目前採「直接交換」：
  - 不做碰撞檢查
  - 不做回滾
- 交換公式是 foot-align + 水平中心修正：
  - 玩家與物件交換後可維持較合理落點。

### 5.4 Swap 輸入穩定化（已加）

為了解決連點失效：

- 邊緣觸發：只在按下瞬間觸發
- 最小間隔：`SWAP_MIN_INTERVAL_MS`（預設 90ms）
- 目前 X 鍵接受：`btn_x_pressed` 或 `btn_b_pressed`（避免板子映射差異）

---

## 6. 目前效能狀態（方向）

大致瓶頸順序：

1. 全屏提交 `submit_us`
2. 背景合成 `bg_us`
3. world/tilemap/object 合成 `world_us`

玩家 sprite 合成已由 C API 接手，`sprite_us` 已顯著下降（相較 Python 逐像素）。

---

## 7. 目前可調參數（建議）

在 `config.py` 可調：

- `SWAP_MIN_INTERVAL_MS`：交換連點手感（建議 70~120）
- `OBJECT_GRAVITY_ENABLED`：是否開啟物件重力
- `OBJECT_GRAVITY_STEP`：物件下落每幀步進（建議 1~3）
- `PLAYER_GRAVITY` / `PLAYER_FALL_SPEED_MAX`：玩家重力手感
- `OBJECTS_COMPOSE_IMPL`：`"C_API"` / `"PYTHON"`

---

## 8. 驗證指標（看 log）

啟動確認：

- `OBJECT_MODE_ON`
- `OBJECT_COUNT=...`
- `OBJECT_COMPOSE_IMPL_CFG=C_API`
- `TILEMAP_MODE_ON`

交換確認：

- `SWAP_FAR_OK ...`
- `SWAP_NEAR_OK ...`

效能確認：

- `PROFILE fps=...`
- `PROFILE submit_us=...`
- `PROFILE bg_us=...`
- `PROFILE world_us=...`

---

## 9. 現狀結論

- 目前主線是：
  - tilemap + object + player 皆可渲染
  - object 重力啟用
  - X/Y 交換可用
  - 測試不再自動 300 幀結束
- 行為設計上，far/near 已統一為同一交換算法（只差目標選擇）。
