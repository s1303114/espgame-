# 目前架構說明書（Camera Test 主線）

本文件描述目前 Camera Test 主線的實際架構。以目前程式碼與板上驗證結果為準：內部 flash 只放 launcher，遊戲程式與資產由 SD 卡 `/sd/game` 載入；每幀狀態由 Python 更新，重型畫面合成與 TFT submit 交給 C++ native renderer。

---

## 1. 啟動與入口

- 內部 flash 只需要 `/boot.py` 與 `/main.py`。
- `main.py` 會掛載外接 SD 卡，將 `/sd/game` 放到 `sys.path` 前面，然後執行 `/sd/game/app.py`。
- 沒有 SD 卡、或 SD 上沒有 `/sd/game/app.py` 時，launcher 進入 safe mode，不跑內部舊遊戲。
- 目前標準啟動 log 應看到 `Launcher source: sd`。

SD 遊戲根目錄至少需要：

```text
/sd/game/
  app.py
  app_camera_test.py
  config.py
  assets.py
  state.py
  actors/
  engine/
  save/
  Tilemap/
  picture/
```

---

## 2. 渲染主線

目前 Step 4 主線是 **native 4-band pipeline**：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 60`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`

螢幕 `320x240` 拆成 4 條 `320x60` band。Python 每幀更新遊戲狀態後，把 far background、tilemap、object atlas、player sprite、special overlay、enemy 描述子傳給：

```python
lgfx.render_scene_bands_rgb565(...)
```

C++ 在每個 band 內完成：

1. far background copy
2. tilemap compose
3. object atlas compose
4. special object / respawn anchor / bullet overlay compose
5. enemy compose
6. player colorkey sprite compose
7. wire-order DMA submit

板上主線標記：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`
- `SUBMIT_BYTE_ORDER=WIRE_NOSWAP`

目前實測大約：

- `PROFILE total_us ~= 35.7ms`
- `PROFILE fps ~= 28.0`
- native 模式下 `PROFILE submit_us` 包含 C++ compose + band submit，不是舊版單純 full-screen submit。

---

## 3. 資產格式與路徑

主線 `.rgb565` 圖像資產都使用 **panel wire-order**，也就是每個 RGB565 pixel 以 `hi, lo` 存放。不要在每幀做 runtime byte swap。

目前主線資產：

- far bg：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map1_tilemap.csv`
- tileset：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- object CSV：`/sd/game/picture/object/objects.csv`
- object animations：`/sd/game/picture/object/object_animations.json`
- object atlas：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- enemy CSV：`/sd/game/picture/enemy/enemies.csv`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`

透明色規則：

- 語意色：magenta `#FF00FF`
- RGB565 語意值：`0xF81F`
- wire-order raw compare value：`0x1FF8`
- Python 傳入 C++ compose 前會用 `_swap16(...)` 轉成 raw compare value。

---

## 4. Python / C++ 分工

Python (`app_camera_test.py`) 負責：

- input update
- player movement / gravity
- object gravity
- swap skill
- camera tracking
- enemy state / bullet state
- respawn state
- player animation frame selection
- object/enemy/overlay descriptor packing

C++ (`lgfx` user module) 負責：

- `render_scene_bands_rgb565(...)` native band compose + submit
- `compose_tilemap_rgb565(...)` fallback/測試用 tilemap compose
- `compose_objects_atlas_rgb565(...)` fallback/測試用 object atlas compose
- `compose_colorkey_rgb565(...)` fallback/測試用 player sprite compose
- `blit_rect565_wire_async(...)` full-screen wire DMA fallback/測試路徑
- DMA 前 `esp_cache_msync(..., DIR_C2M | UNALIGNED)`，避免 PSRAM/cache coherency 造成水平條碼花屏

---

## 5. 玩家、物件與技能

### 玩家與物件重力

- 玩家重力由 `PLAYER_GRAVITY` / `PLAYER_FALL_SPEED_MAX` 控制。
- object 重力由 `OBJECT_GRAVITY_ENABLED` / `OBJECT_GRAVITY_STEP` 控制。
- object 每幀下落後會回寫 `objects_c_buf`，C++ renderer 立即使用新座標。

### Swap

目前按鍵映射：

- `B`：far swap
- `Y`：near swap
- `X`：目前不觸發 swap

swap 使用：

- 邊緣觸發
- `SWAP_MIN_INTERVAL_MS` 最小間隔
- 直接交換
- 不做碰撞回滾

交換成功 log：

- `SWAP_FAR_OK_V2 ...`
- `SWAP_NEAR_OK_V2 ...`

---

## 6. 驗證指標

啟動與資源：

- `OBJECT_MODE_ON`
- `OBJECT_COUNT=...`
- `TILEMAP_MODE_ON`
- `CAMERA_PLAYER_SPRITE_READY=1`

渲染主線：

- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`
- `PROFILE submit_us=...`
- `PROFILE submit_kick_us=...`
- `PROFILE submit_wait_us=...`
- `PROFILE fps=...`

若看到 `BAND_PIPELINE_NATIVE_FALLBACK`，先檢查 firmware 是否真的匯出：

```python
import lgfx
print(hasattr(lgfx, 'render_scene_bands_rgb565'))
```

---

## 7. 目前結論

目前主線已不是舊 full-screen Python compose + full-screen submit。正式路徑是：

```text
SD launcher
 -> app.py
 -> app_camera_test.py
 -> Python 更新遊戲狀態
 -> C++ render_scene_bands_rgb565
 -> 4-band wire-order DMA submit
```

下一步主要優化方向是減少每 band 重組成本，例如 static world band cache、camera static frame cache、camera moving strip cache，以及測試不同 `CAMERA_BAND_PIPELINE_H` 的 compose/DMA overlap。
