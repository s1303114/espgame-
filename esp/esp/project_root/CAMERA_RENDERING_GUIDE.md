# CAMERA 渲染說明書（目前主線）

## 1. 主線總覽

目前板上正式渲染主線是：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `TILEMAP_ENABLED = True`
- `FLOOR_LAYER_ENABLED = False`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL = "C_API"`
- `CAMERA_FULL_BULK_WIRE_ORDER = True`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 48`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`

目前 firmware 主線的 panel bus baseline：

- `micropython/user_cmodules/lgfx/lgfx_config.hpp` 的 `cfg.freq_write = 40000000`
- `80MHz` 會讓 `waitDMA` 顯著下降、FPS 提升，但實機會出現撕裂
- 因此目前正式主線固定回 `40MHz`，先以穩定顯示為優先

主線啟動結構：

- internal flash 只保留 `boot.py` / `main.py`
- `main.py` 是 SD-only launcher
- `main.py` 先驗證 `/sd/game/app.py`、`/sd/game/config.py`、`/sd/game/app_camera_test.py` 存在
- `main.py` 先 `exec /sd/game/config.py`，再 `exec /sd/game/app_camera_test.py`
- `/sd/game/app.py` 目前只保留為 wrapper / 存在性檢查備用
- 正式唯一 SD 掛載 wiring：`slot=2, width=1, sck=5, mosi=6, miso=7, cs=4, freq=1000000`

## 2. 互動與世界邏輯

目前板上互動主線：

- `B` 觸發 far swap
- `Y` 觸發 near swap
- swap 使用邊緣觸發與 `SWAP_MIN_INTERVAL_MS`
- far/near swap 都走直接交換，不做碰撞回滾
- 找不到目標只輸出 `SWAP_FAIL_NO_TARGET_V2`

物理與世界狀態：

- 玩家重力由 `PLAYER_GRAVITY` / `PLAYER_FALL_SPEED_MAX` 控制
- object 重力由 `OBJECT_GRAVITY_ENABLED` / `OBJECT_GRAVITY_STEP` 控制
- tilemap 是主線碰撞來源
- object、enemy、bullet 都會影響世界互動

## 3. 每幀流程

目前每幀流程不是 Python 先合成 full-screen `scene_buf`，而是：

1. Python 更新 input、player、camera、swap、respawn、object gravity
2. Python 更新 enemy / bullet 狀態
   - 優先走 `lgfx.update_enemies_native(...)`
   - 若 native path 失敗，印一次 `ENEMY_UPDATE_NATIVE_FALLBACK ...` 並回退 Python update
3. Python 打包 object / overlay / enemy render descriptors
4. Python 呼叫 `lgfx.render_scene_bands_rgb565(...)`
5. C++ 以 `320 x 48` 的 band 逐條 compose 與 submit

目前 band 內 C++ compose 順序：

- far background
- tilemap
- object atlas
- special overlay / respawn anchor / enemy bullet overlay
- enemy
- player sprite

## 4. Native band pipeline

目前主線提交是 **wire-order native band pipeline + DMA + cache sync**。

關鍵提交路徑：

```cpp
esp_cache_msync(
    (void *)pixels,
    expected_len,
    ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
);
lcd.startWrite();
lcd.setSwapBytes(false);
lcd.pushImageDMA(x, y, w, h, pixels);
```

重要結論：

- 主線資產必須是 **wire-order RGB565**
- DMA 前必須做 `esp_cache_msync(...)`
- 否則會出現水平條碼狀花屏、背景覆蓋 sprite 等一致性問題

目前 band submit profile 會拆成：

- `PROFILE submit_us`
- `PROFILE submit_wait_us`
- `PROFILE submit_kick_us`
- `PROFILE submit_sync_us`
- `PROFILE submit_start_us`
- `PROFILE submit_push_us`
- `PROFILE submit_dma_wait_us`
- `PROFILE submit_end_us`
- `PROFILE submit_swap_us`

其中 native band 模式下：

- `submit_us` 是整個 native band call 的總時間
- `submit_wait_us` / `submit_kick_us` 是 C++ 回傳的 wait / kick 拆分
- `submit_dma_wait_us` 幾乎就是 `lcd.waitDMA()` 本體時間
- `submit_sync_us` 是 DMA 前 `esp_cache_msync(...)` 的成本

## 5. Enemy update 主線

目前 enemy 邏輯已不是純 Python 主線。

已新增 C API：

- `lgfx.update_enemies_native(...)`

目前做的事情：

- enemy AI state transition
- enemy gravity / move / collision
- bullet spawn / move / cull / hit
- 直接原地更新 enemy / bullet buffer

板上驗證標記：

- `ENEMY_UPDATE_IMPL=C_API`
- 若 native path 失敗：`ENEMY_UPDATE_NATIVE_FALLBACK ...`

## 6. Persistent buffers

enemy native update 目前使用常駐 packed buffer，不再每幀重建。

### 6.1 Enemy rows

`enemy_rows_c_buf` 是常駐 buffer，只在這些時機重同步：

- 初始化
- Python fallback 後
- world swap 後
- respawn / restore 後

格式（stride `12`）：

- `0..1`: `wx`
- `2..3`: `wy`
- `4..5`: `w`
- `6..7`: `h`
- `8`: `visible`
- `9`: `swappable`
- `10`: `default_facing_sign`
- `11`: `static_enemy`，monk hover/waypoint 與 native attack 會用這個欄位判斷是否走 static monk path

### 6.2 Enemy states

`enemy_states` 也是 packed buffer view。

格式（stride `8`）：

- `0`: `facing_sign`
- `1`: `state`
- `2..3`: `anim_counter`
- `4..5`: `shoot_cooldown`
- `6`: `shot_fired`
- `7`: `vel_y`

### 6.3 Enemy bullets

`enemy_bullets` 使用固定容量 pool。

格式（stride `16`）：

- `0..1`: `x`
- `2..3`: `y`
- `4..5`: `vx`
- `6..7`: `vy`
- `8..9`: `w`
- `10..11`: `h`
- `12..13`: `active`
- `14..15`: `shooter_enemy_i`

### 6.4 Object solids

`object_solids_c_buf` 也已改成常駐 buffer，不再每幀 `_pack_object_solids_for_c(...)`。

只在這些時機重同步：

- 初始化
- object gravity 導致 solid object 位置改變
- world swap 後
- respawn / restore 後

格式（stride `8`）：

- `0..1`: `x`
- `2..3`: `y`
- `4..5`: `w`
- `6..7`: `h`

## 7. 目前實測結論

### 7.1 Full-screen 舊路徑

舊 full-screen wire DMA 路徑雖然 `submit_us` 可壓到約 `24.5ms`，但 Python full-screen compose 很重，總體約落在 `19 FPS` 級別。

### 7.2 Native band pipeline

目前正式主線是 native band pipeline。

目前 40MHz / `h=48` 正式主線大致觀察：

- 起始區域：`submit_us` 約 `32.1ms`、`submit_wait_us` 約 `13.8ms`、`submit_dma_wait_us` 約 `13.6ms`、`fps` 約 `25.9`
- monk 區域：`submit_us` 約 `32.6ms`、`submit_wait_us` 約 `15.9ms`、`submit_dma_wait_us` 約 `15.8ms`、`fps` 約 `25.6`

額外 probe 結論：

- 把 `cfg.freq_write` 從 `40MHz` 拉到 `80MHz` 後，`submit_us` 可降到約 `26.2ms`、`submit_dma_wait_us` 可降到約 `3.34ms`、`fps` 可到約 `31.6`
- 但 `80MHz` 會出現實機撕裂，因此目前不採用為正式主線
- 這證明目前主要瓶頸確實是 SPI bus / DMA transfer time，而不是 enemy logic 或單一圖層 compose

### 7.3 Enemy 區域

enemy update 搬到 C++ 並改成 persistent buffer 後，敵人區實測大致是：

- `update_us` 約 `5.3ms ~ 5.9ms`，偶發較高值約 `6~7ms`
- `submit_us` 仍約 `36.6ms ~ 37.3ms`
- `fps` 約 `23.1 ~ 23.7`

這代表：

1. `C++ enemy update` 已生效
2. persistent buffer 讓 `update_us` 再下降一點
3. 目前真正主瓶頸仍然是 `submit_us`，不是 enemy logic

## 8. 資產格式

目前主線 `.rgb565` 資產都應是 **wire-order**，即每個 RGB565 pixel 以 `hi, lo` 存放。

主工具：

- `/workspace/esp/esp/project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`

常用選項：

- `--byte-order wire`：主線格式
- `--byte-order le`：舊 little-endian 格式，只供舊 `swap=true` 路徑

目前主要資產：

- far 背景：`/sd/game/picture/backgound/bg_far_wire.rgb565`
- tilemap atlas：`/sd/game/Tilemap/tilemap_all_wire.rgb565`
- tilemap CSV：`/sd/game/Tilemap/map_tilemap.csv`
- object atlas：`/sd/game/picture/object/object_altes_wire.rgb565`
- object animations：`/sd/game/picture/object/object_animations.json`
- enemy CSV：`/sd/game/picture/enemy/enemies.csv`
- enemy sheet：`/sd/game/picture/enemy/enemy_bow_animation_wire.rgb565`
- player sheet：`/sd/game/picture/player/player_wire.rgb565`
- spawn sheets：`/sd/game/picture/spawn/Resurrection_Anchor_wire.rgb565`、`/sd/game/picture/spawn/Spawnpoint_rock_wire.rgb565`

## 9. 關鍵 API

`micropython/user_cmodules/lgfx/` 目前主線相關 API：

- `render_scene_bands_rgb565(...)`
- `update_enemies_native(...)`
- `compose_tilemap_rgb565(...)`
- `compose_objects_atlas_rgb565(...)`
- `compose_colorkey_rgb565(...)`
- `blit_rect565_wire_async(...)`
- `blit_rect565_wire_wait(...)`
- `blit_wait_done()`
- `async_probe_rgb565(...)`
- `submit_probe_rgb565(...)`
- `band_submit_probe_rgb565(...)`

其中主線實際使用的是：

- `render_scene_bands_rgb565(...)`
- `update_enemies_native(...)`
- `update_monk_orbs_native(...)`
- `pack_monk_orb_descriptors_native(...)`
- `pick_swappable_monk_orb_native(...)`
- `update_monk_attack_native(...)`

monk attack orb render 的重要約定：`scripted_attack` 期間 descriptor 必須繼續走 native `pack_monk_orb_descriptors_native(...)`，直接讀 `monk_orb_c_buf.current_x/current_y`。只有 `scripted_intro` 需要 Python descriptor fallback；attack 若 fallback 到 Python shadow，畫面會使用 stale orbit/script position。

monk orb descriptor 的第 6 byte 目前保存 native mode。native renderer 用它選顏色：`0 orbit` / `3 scripted_intro` 使用公轉 sprite；`1 detached` / `2 captured_return` / `4 scripted_attack` 使用第二色 sprite。source atlas 為 `object_altes_wire.rgb565`：公轉 / intro 取 `(96,16,16,16)`，detached / return / attack 取 `(96,32,16,16)`。

`OBJECTS_ATLAS_RGB565_PATH` 與 `ENEMY_MONK_ORB_ATLAS_RGB565_PATH` 目前都指向 `game/picture/object/object_altes_wire.rgb565`。`_load_enemy_runtime_assets(...)` 在路徑與尺寸相同時重用已載入的 object atlas bytes，因此 RAM 不持有第二份 256x256 RGB565 atlas。

## 10. 板上檢查點

建議優先看這些 log：

- `Launcher source: sd`
- `LOADER_SRC_PATH=/sd/game/app_camera_test.py`
- `LAUNCHER_APP_FILE=/sd/game/app_camera_test.py`
- `OBJECT_COUNT=10`
- `ENEMY_MODE_ON`
- `ENEMY_UPDATE_IMPL=C_API`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`
- `BAND_PIPELINE_SUBMIT_OK`
- `PLAYER_KILLED_BY_MONK_ORB ...`
- `PROFILE update_us=...`
- `PROFILE submit_us=...`
- `PROFILE submit_wait_us=...`
- `PROFILE submit_kick_us=...`
- `PROFILE fps=...`

若 native enemy path 失敗，會看到：

- `ENEMY_UPDATE_NATIVE_FALLBACK ...`

若 band pipeline 無法啟用，會看到：

- `BAND_PIPELINE_NATIVE_FALLBACK`

## 11. Build / Flash

firmware 改動一律走 `/tmp` 本地鏡像，不直接在 `/workspace` build：

```bash
cd /workspace/esp/esp/project_root
LOCAL_ROOT=/tmp/esp-mp-local ./build_local_tmp.sh
```

若 `/workspace -> /tmp` 複製卡在 9p I/O，而你只改了少數 user_cmodule 檔案，可以直接同步到 `/tmp/esp-mp-local` 再增量重編，例如：

```bash
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_mp.cpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_mp.cpp
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_band.cpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_band.cpp
cp /workspace/esp/esp/micropython/user_cmodules/lgfx/lgfx_shared.hpp /tmp/esp-mp-local/micropython/user_cmodules/lgfx/lgfx_shared.hpp

cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
make -j6 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT_NOBT USER_C_MODULES=/tmp/esp-mp-local/micropython/user_cmodules
```

燒錄：

```bash
cd /tmp/esp-mp-local/micropython/ports/esp32
source /opt/esp/idf/export.sh
idf.py -B build-ESP32_GENERIC_S3-SPIRAM_OCT_NOBT -p /dev/ttyACM0 flash
```

## 12. SD-only 部署

只改 Python runtime 時，不需要重編 firmware，但要用可靠流程同步到外接 SD：

1. `umount -> mount`
2. 用同一個 `mpremote` session 複製檔案
3. 同 session 或重掛載後 readback 驗證

最少要同步的主線檔：

- `/sd/game/app.py`
- `/sd/game/app_camera_test.py`
- `/sd/game/config.py`

不要只看 `fs cp` 成功訊息；一定要 readback 驗證新版內容真的在外接 SD 上。

## 13. 下一步最佳化方向

目前 enemy logic 這條線已經壓得差不多。下一步若要再拉 FPS，優先順序應放在 submit / render 路徑：

1. 目前正式主線固定 `CAMERA_BAND_PIPELINE_H = 48`
2. 若要再追 submit bottleneck，先優先檢查 panel bus / DMA 參數，而不是再關單一圖層
3. 分析 enemy 區是否讓更多 band 被迫做完整 compose
4. 減少不必要 band 更新量
5. 若還要再壓 Python，才考慮把 enemy render descriptor 也做成常駐或直接由 C++ 輸出
