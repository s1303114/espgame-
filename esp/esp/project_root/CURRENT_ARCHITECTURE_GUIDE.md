# 目前專案架構（主線）

本文件整理目前板上主線。核心原則是：內部 flash 只放 launcher，遊戲程式與資產從 SD 載入；每幀遊戲狀態由 Python 更新，重型畫面合成與 TFT submit 交給 C++ native API。

---

## 0. 執行與渲染主線

### 啟動路徑

- 內部 flash：`/boot.py`、`/main.py`
- SD 遊戲根目錄：`/sd/game`
- 啟動後由 `/sd/game/app.py` 進入 camera test 主線。
- 目前 boot log 會顯示 `Launcher source: sd`。

### 每幀責任分工

Python (`app_camera_test.py`) 負責：

- input update
- player movement / gravity
- object gravity
- B/Y swap skill
- camera tracking
- enemy / bullet / respawn state
- 選擇本幀 player sprite frame
- 打包 object、special overlay、enemy render descriptors
- 將本幀狀態與資源 buffer 傳給 C++ renderer

C++ (`lgfx` user module) 負責：

- far background band copy
- tilemap compose
- object atlas compose
- special object / respawn anchor / bullet overlay compose
- enemy compose
- player colorkey compose
- native band pipeline submit
- RGB565 wire-order DMA cache sync

目前主線 renderer：

- `lgfx.render_scene_bands_rgb565(...)`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 60`
- 4 bands：`320x60 * 4`
- 輸出標記：`SUBMIT_MODE=NATIVE_BAND_PIPELINE`、`BAND_PIPELINE_NATIVE_ON h=60`

目前實測約：

- `PROFILE total_us ~= 35.7ms`
- `PROFILE fps ~= 28.0`

### 資料與資產

主線資產都使用 wire-order RGB565：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map1_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- objects CSV：`/sd/game/picture/object/objects.csv`
- object animations：`/sd/game/picture/object/object_animations.json`
- objects atlas：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- enemies CSV：`/sd/game/picture/enemy/enemies.csv`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`

透明色主線規則：

- 語意 colorkey：RGB565 `0xF81F` (`#FF00FF`)
- wire-order raw buffer 內比較值：`0x1FF8`
- Python 傳給 C++ compose 前會做 `_swap16(...)`

---

## 1. 玩家技能架構（B/Y 交換）

### 技能定義

目前有兩個核心交換技能：

- B：與鏡頭範圍內「最遠」可交換目標交換
- Y：與鏡頭範圍內「最近」可交換目標交換
- X：目前不觸發 swap

兩者共享同一套交換算法，差別只在目標選擇（far / near）。

### 觸發與輸入層

技能觸發在 `app_camera_test.py` 主迴圈內。

輸入穩定化機制：

- 邊緣觸發：只吃 `False -> True` 按下瞬間
- 最小間隔：`SWAP_MIN_INTERVAL_MS`（預設 90ms）
- 目的：避免連點過快或長按導致重複觸發/看似失效

按鍵映射：

- B 技能：far swap（`btn_b_pressed`）
- Y 技能：near swap（`btn_y_pressed`）
- X：目前不觸發 swap

### 目標挑選規則

目標挑選由 `_pick_swappable_object_index(...)` 負責。

篩選條件：

- 必須在鏡頭可視範圍內
- `visible=1`
- `swappable=1`

距離計算：

- 以玩家中心點到物件中心點的距離平方 `d2` 計算
- far：選 `d2` 最大
- near：選 `d2` 最小

找不到目標時輸出：

- `SWAP_FAIL_NO_TARGET_V2`

### 交換落點算法（目前主線）

交換採用「足底對齊 + 水平置中修正」：

- 玩家新位置：`player_x = old_obj_x + ((obj_w - player_w) // 2)`，`player_y = old_obj_y + (obj_h - player_h)`
- 物件新位置：`obj_x = old_player_x + ((player_w - obj_w) // 2)`，`obj_y = old_player_y + (player_h - obj_h)`

目前策略：

- 直接交換生效
- 不做碰撞檢查
- 不做回滾

交換成功後：

- 立即更新 `objects_rows`
- 回寫 `objects_c_buf`
- 重建 `object_solids`
- 玩家與 object 重力後續照常生效

---

## 2. Native Band Pipeline

目前正式 renderer 是 `render_scene_bands_rgb565(...)`。Python 仍保留 full-screen compose/submit fallback，但主線應看到：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`

C++ 回傳 profile tuple：

```text
(band_count, compose_us, kick_us, wait_us, total_us)
```

Python 會將 native call 整體記入 `PROFILE submit_us`，並將 `kick_us / wait_us` 拆到：

- `PROFILE submit_kick_us`
- `PROFILE submit_wait_us`

注意：native band 模式的 `submit_us` 不是舊版純 TFT submit，而是 C++ compose + band DMA pipeline 的總耗時。

---

## 3. 可調參數

在 `config.py` / `sd_config.py` 可調：

- `CAMERA_BAND_PIPELINE_H`：band 高度，目前 60
- `SWAP_MIN_INTERVAL_MS`：交換連點間隔，建議 70~120
- `OBJECT_GRAVITY_ENABLED`：是否開啟物件重力
- `OBJECT_GRAVITY_STEP`：物件下落每幀步進
- `PLAYER_GRAVITY` / `PLAYER_FALL_SPEED_MAX`：玩家重力手感
- `CAMERA_OBJECT_COLORKEY_ENABLE` / `CAMERA_OBJECT_COLORKEY_RGB565`：object atlas colorkey
- `ENEMY_*`：enemy 偵測、移動、射擊與子彈參數

---

## 4. 設計結論

目前主線是：

```text
SD-only launcher
 -> Python game state update
 -> packed render descriptors
 -> C++ native 4-band compose
 -> wire-order DMA submit with cache sync
```

這條路徑已取代舊 full-screen Python compose + full-screen submit 主線。後續優化應集中在 band cache、static world cache、camera moving strip cache，以及 band 高度調參。
