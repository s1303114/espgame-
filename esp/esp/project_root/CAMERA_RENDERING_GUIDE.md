# CAMERA 渲染說明書（最終主線）

## 1. 最終主線總覽

板上最終渲染主線固定為：

- `CAMERA_TEST_MODE = "ROWS_SAFE_PROGRESSIVE"`
- `TILEMAP_ENABLED = True`
- `FLOOR_LAYER_ENABLED = False`
- `CAMERA_PLAYER_SPRITE_COMPOSE_IMPL = "C_API"`
- `CAMERA_RENDER_WIRE_ORDER = True`
- `CAMERA_RENDER_BACK_BUFFER = True`
- `CAMERA_BAND_PIPELINE_NATIVE = True`
- `CAMERA_BAND_PIPELINE_H = 48`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=48`

firmware 的 panel bus baseline 固定為：

- `micropython/user_cmodules/lgfx/lgfx_config.hpp` 的 `cfg.freq_write = 40000000`
- `80MHz` 會讓 `waitDMA` 顯著下降、FPS 提升，但實機會出現撕裂
- 因此最終主線固定使用 `40MHz`，以穩定顯示為優先

主線啟動結構：

- internal flash 只保留 `boot.py` / `main.py`
- `main.py` 是 SD-only launcher
- `main.py` 先驗證 `/sd/game/app.py`、`/sd/game/config.py`、`/sd/game/app_camera_test.py` 存在
- `main.py` 先 `exec /sd/game/config.py`，再 `exec /sd/game/app_camera_test.py`
- `/sd/game/app.py` 只保留為 wrapper / 存在性檢查備用
- 正式唯一 SD 掛載 wiring：`slot=2, width=1, sck=5, mosi=6, miso=7, cs=4, freq=1000000`

不再視為主線的路徑：

- 舊 full-screen Python compose / direct blit 路徑只保留為歷史參考或 bring-up probe。
- `80MHz` panel bus 只保留為性能 probe，不列入最終主線，除非未來另有實機穩定性證據。
- `FULL_BUFFER_TEST`、`SPI_TFT_*`、`ROWS_SAFE_NEAR_TILE_TEST` 已從 SD runtime 主線移除；若要再使用，應另外建立開發期 bring-up 檔案或手動恢復。
- 後續最佳化以維持 `ROWS_SAFE_PROGRESSIVE + NATIVE_BAND_PIPELINE + h=48 + 40MHz` 為前提，不再把切回舊 renderer 當作方向。

## 2. 互動與世界邏輯

板上互動主線：

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

最終每幀流程不是 Python 先合成 full-screen `scene_buf`，而是：

1. Python 更新 input、player、camera、swap、respawn、object gravity
2. Python 更新 enemy / bullet 狀態
   - 優先走 `lgfx.update_enemies_native(...)`
   - 若 native path 失敗，印一次 `ENEMY_UPDATE_NATIVE_FALLBACK ...` 並回退 Python update
3. Python 打包 object / overlay / enemy render descriptors
4. Python 呼叫 `lgfx.render_scene_bands_rgb565(...)`
5. C++ 以 `320 x 48` 的 band 逐條 compose 與 submit

band 內 C++ compose 順序：

- far background
- tilemap
- object atlas
- special overlay / respawn anchor / enemy bullet overlay
- enemy
- player sprite

## 4. Native band pipeline

最終主線提交是 **wire-order native band pipeline + DMA + cache sync**。

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

最終主線 profile 使用分層 log，避免把不同時間座標混在一起：

```text
FRAME_WALL total_us=... update_us=... submit_call_us=... tail_res_us=... wait_exposed_us=... fps=...
CPU_WORK update_us=... compose_us=... desc_us=... kick_cpu_us=... sync_us=... start_us=... push_us=... swap_us=...
CPU_COMP bg_us=... tile_us=... obj_us=... enemy_us=... special_us=... player_us=...
DMA_SUM bytes=... spi_hz=... ideal_us=... elapsed_us=... gap_us=... exposed_dma_us=... not_waitdma_us=... kick_us=... wait_dma_us=... end_us=... tail_dma_us=... tail_total_us=... tail_res_us=...
PIPE_OVERLAP band_comp_us=... band_wait_exposed_us=... tail_update_us=... tail_hidden_us=...
UPDATE_BREAK input_us=... object_us=... enemy_us=... monk_us=... swap_us=... physics_us=... camera_us=... respawn_us=... misc_us=...
```

欄位意義：

- `FRAME_WALL.total_us` 是一幀從 frame start 到 render submit 完成後的牆上時間。
- `FRAME_WALL.submit_call_us` 是 Python 呼叫 `render_scene_bands_rgb565(...)` 的 wall time；tail-overlap 模式下不包含下一幀才等待的最後一段 DMA，因此不可拿它直接減 SPI 理論值。
- `FRAME_WALL.tail_res_us` 是下一幀 update 後，CPU 還需要真的等待 deferred tail DMA 的 residual wall time。
- `FRAME_WALL.wait_exposed_us` 是本幀實際暴露在 CPU wall 上的 wait，已含 C++ band wait 與 tail residual wait。
- `CPU_WORK.desc_us` 是 Python render descriptor packing 時間，發生在 native band call 之前。
- `CPU_WORK.compose_us` 是 C++ compose 所有 bands 的總時間。
- `CPU_WORK.kick_cpu_us` 是 C++ 啟動 DMA 的 CPU 成本，包含 cache sync、`startWrite` / `setSwapBytes`、`pushImageDMA` call。
- `CPU_WORK.sync_us` 是所有 band 的 `esp_cache_msync(...)` 總成本。
- `CPU_WORK.start_us` 是 `startWrite` / `setSwapBytes(false)` 的總成本。
- `CPU_WORK.push_us` 是 `pushImageDMA(...)` call 本身的總成本。
- `DMA_SUM.ideal_us` 是以 `bytes * 8 / spi_hz` 算出的純 SPI 理論傳輸時間。目前 `320*240*2 bytes`、`40MHz` 時是 `30720us`。
- `DMA_SUM.elapsed_us` 是完整 DMA transaction elapsed：C++ 從 `pushImageDMA(...)` 呼叫進入開始量，到 `waitDMA()` 完成為止；tail-overlap 的最後一段由 `tail_dma_us` 補入。
- `DMA_SUM.gap_us = elapsed_us - ideal_us`，這才是可以和 SPI 理論直接比較的差值。
- `DMA_SUM.exposed_dma_us` 是 CPU 實際卡在 `waitDMA()` 的時間。
- `DMA_SUM.not_waitdma_us = elapsed_us - exposed_dma_us`，代表 DMA 在跑但 CPU 沒卡在 `waitDMA()` 的時間，通常被 compose/update 等工作重疊掉。
- `DMA_SUM.tail_dma_us` 是 deferred final band 的完整 DMA elapsed。
- `DMA_SUM.tail_total_us` 是 tail 從前一幀 submit 結尾被 defer 到下一幀 wait 完成的總 wall time，包含被 update 蓋住的時間。
- `DMA_SUM.tail_res_us` 是下一幀 update 後仍需等待的 tail residual wall time。
- `PIPE_OVERLAP.band_comp_us` 是每個 band 的 compose time。
- `PIPE_OVERLAP.band_wait_exposed_us` 是每個非 deferred band 暴露在 CPU wall 上的 wait time。
- `PIPE_OVERLAP.tail_update_us` 是 tail DMA 被下一幀 update 蓋住的時間。
- `PIPE_OVERLAP.tail_hidden_us = tail_total_us - tail_res_us`，是 tail DMA 沒暴露成 residual wait 的時間。

嚴格比較規則：

- 要證明 SPI/DMA 相對理論還剩多少，只能看 `DMA_SUM.ideal_us`、`DMA_SUM.elapsed_us`、`DMA_SUM.gap_us`。
- 不可用 `submit_call_us - ideal_us`。在 tail-overlap 模式下，`submit_call_us` 沒有包含 deferred final DMA 的完整 elapsed。
- `submit_call_us` 仍有用，但它回答的是「Python 呼叫 native renderer 這段 wall time 多長」，不是「整個 full-frame DMA 傳輸多長」。

## 5. Enemy update 主線

enemy 邏輯已不是純 Python 主線。

已新增 C API：

- `lgfx.update_enemies_native(...)`

native enemy update 做的事情：

- enemy AI state transition
- enemy gravity / move / collision
- bullet spawn / move / cull / hit
- 直接原地更新 enemy / bullet buffer

板上驗證標記：

- `ENEMY_UPDATE_IMPL=C_API`
- 若 native path 失敗：`ENEMY_UPDATE_NATIVE_FALLBACK ...`

## 6. Persistent buffers

enemy native update 使用常駐 packed buffer，不再每幀重建。

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

## 7. 最終主線實測結論

### 7.1 Full-screen 舊路徑

舊 full-screen wire DMA 路徑雖然 `submit_us` 可壓到約 `24.5ms`，但 Python full-screen compose 很重，總體約落在 `19 FPS` 級別。這條路徑不再作為正式渲染策略，只保留為歷史資料與 bring-up 參考。

### 7.2 Native band pipeline

最終主線是 native band pipeline。

40MHz / `h=48` 最終主線大致觀察：

- 起始區域：`submit_us` 約 `32.1ms`、`submit_wait_us` 約 `13.8ms`、`submit_dma_wait_us` 約 `13.6ms`、`fps` 約 `25.9`
- monk 區域：`submit_us` 約 `32.6ms`、`submit_wait_us` 約 `15.9ms`、`submit_dma_wait_us` 約 `15.8ms`、`fps` 約 `25.6`

額外 probe 結論：

- 把 `cfg.freq_write` 從 `40MHz` 拉到 `80MHz` 後，`submit_us` 可降到約 `26.2ms`、`submit_dma_wait_us` 可降到約 `3.34ms`、`fps` 可到約 `31.6`
- 但 `80MHz` 會出現實機撕裂，因此不採用為最終主線
- 這證明 SPI bus / DMA transfer time 是重要下限，但新版 timing log 顯示，剩餘時間不能再只用 `submit_us` 判斷；必須分開看完整 DMA elapsed、descriptor packing、第一個 band compose、cache sync/start 和 tail overlap

### 7.3 2026-06-10 嚴謹 timing sample

這次實測使用新版分層 log，來源是板上 `/tmp/render_profile_rigorous.log`。代表樣本：

```text
FRAME_WALL total_us=38092 update_us=4157 submit_call_us=31706 tail_res_us=1169 wait_exposed_us=18129 fps=26.25
CPU_WORK update_us=4157 compose_us=8992 desc_us=3918 kick_cpu_us=1460 sync_us=1206 start_us=92 push_us=161 swap_us=177
CPU_COMP bg_us=6513 tile_us=1674 obj_us=83 enemy_us=13 special_us=370 player_us=283
DMA_SUM bytes=153600 spi_hz=40000000 ideal_us=30720 elapsed_us=30986 gap_us=266 exposed_dma_us=18026 not_waitdma_us=12960 kick_us=1460 wait_dma_us=18026 end_us=103 tail_dma_us=6264 tail_total_us=6290 tail_res_us=1169
PIPE_OVERLAP band_comp_us=1349,1371,1354,2527,2389,0 band_wait_exposed_us=4783,4796,3629,3764,0,0 tail_update_us=4112 tail_hidden_us=5121
UPDATE_BREAK input_us=709 object_us=992 enemy_us=618 monk_us=681 swap_us=177 physics_us=203 camera_us=761 respawn_us=0 misc_us=16
```

這筆可以直接驗算：

```text
總剩餘 = FRAME_WALL.total_us - DMA_SUM.ideal_us
       = 38092 - 30720
       = 7372us

DMA gap = DMA_SUM.elapsed_us - DMA_SUM.ideal_us
    = 30986 - 30720
    = 266us

DMA window 外時間 = FRAME_WALL.total_us - DMA_SUM.elapsed_us
          = 38092 - 30986
          = 7106us

266 + 7106 = 7372us
```

因此這筆 sample 的重點是：完整 DMA transaction 只比 40MHz 理論多 `266us`；不是 SPI/DMA 本身慢了 `7.3ms`。

四筆 sample 的總剩餘拆解：

```text
#1 remaining=7372us  dma_gap=266us   outside_dma_window=7106us
#2 remaining=7012us  dma_gap=440us   outside_dma_window=6572us
#3 remaining=8288us  dma_gap=810us   outside_dma_window=7478us
#4 remaining=9410us  dma_gap=1018us  outside_dma_window=8392us
```

平均：

```text
total_us                         38740us
ideal_us                         30720us
remaining total_us - ideal_us     8020us
DMA elapsed_us                   31354us
DMA gap_us                         634us
outside DMA window                7387us
```

所以最終主線目前「總剩餘約 7.0-9.4ms」主要拆成：

- `DMA gap`：約 `0.27-1.02ms`，平均 `0.63ms`
- `DMA window 外時間`：約 `6.57-8.39ms`，平均 `7.39ms`

再把 `outside DMA window` 拆開，四筆平均約是：

```text
outside DMA window                7387us
descriptor packing                4434us
第一個 band compose               1381us
cache sync + startWrite           1341us
endWrite / swapBytes               104us
未被 tail overlap 蓋掉的 update      11us
剩餘雜項 / 量測誤差                  115us
```

這裡的拆法是：

```text
outside DMA window
~= CPU_WORK.desc_us
 + PIPE_OVERLAP.band_comp_us[0]
 + (CPU_WORK.kick_cpu_us - CPU_WORK.push_us)
 + DMA_SUM.end_us
 + max(FRAME_WALL.update_us - PIPE_OVERLAP.tail_update_us, 0)
 + remainder
```

含意：

- `descriptor packing` 發生在 native band call 前，DMA 還沒開始，所以完整暴露在 DMA window 外。
- 第一個 band 必須先 compose 完，才能開始第一段 DMA，所以 `band_comp_us[0]` 也完整暴露在 DMA window 外。
- `cache sync + startWrite` 是每個 band 啟動 DMA 前的 CPU setup，主要來自 `esp_cache_msync(...)`。
- `endWrite / swapBytes` 是 `waitDMA()` 完成後的收尾。
- update 大多已經覆蓋 deferred tail DMA；以 sample 來看，真正沒被 tail overlap 蓋掉的 update 幾乎為零。

### 7.4 Enemy 區域

enemy update 搬到 C++ 並改成 persistent buffer 後，敵人區實測大致是：

- `update_us` 約 `5.3ms ~ 5.9ms`，偶發較高值約 `6~7ms`
- `submit_call_us` / 舊 `submit_us` 仍約 `36.6ms ~ 37.3ms`
- `fps` 約 `23.1 ~ 23.7`

這代表：

1. `C++ enemy update` 已生效
2. persistent buffer 讓 `update_us` 再下降一點
3. 瓶頸不再用單一 `submit_us` 判斷；依新版 timing log，主因是 DMA window 外的 descriptor packing、第一個 band compose、cache sync/start，以及完整 DMA elapsed 本身

## 8. 資產格式

最終主線 `.rgb565` 資產都應是 **wire-order**，即每個 RGB565 pixel 以 `hi, lo` 存放。

主工具：

- `/workspace/esp/esp/project_root/sd_game_template/game/tools/convert_png_to_rgb565.py`

常用選項：

- `--byte-order wire`：主線格式
- `--byte-order le`：舊 little-endian 格式，只供舊 `swap=true` 路徑

最終主線主要資產：

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

`micropython/user_cmodules/lgfx/` 最終主線相關 API：

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

其中最終主線實際使用的是：

- `render_scene_bands_rgb565(...)`
- `update_enemies_native(...)`
- `update_monk_orbs_native(...)`
- `pack_monk_orb_descriptors_native(...)`
- `pick_swappable_monk_orb_native(...)`
- `update_monk_attack_native(...)`

monk attack orb render 的重要約定：`scripted_attack` 期間 descriptor 必須繼續走 native `pack_monk_orb_descriptors_native(...)`，直接讀 `monk_orb_c_buf.current_x/current_y`。只有 `scripted_intro` 需要 Python descriptor fallback；attack 若 fallback 到 Python shadow，畫面會使用 stale orbit/script position。

monk orb descriptor 的第 6 byte 保存 native mode。native renderer 用它選顏色：`0 orbit` / `3 scripted_intro` 使用公轉 sprite；`1 detached` / `2 captured_return` / `4 scripted_attack` 使用第二色 sprite。source atlas 為 `object_altes_wire.rgb565`：公轉 / intro 取 `(96,16,16,16)`，detached / return / attack 取 `(96,32,16,16)`。

`OBJECTS_ATLAS_RGB565_PATH` 與 `ENEMY_MONK_ORB_ATLAS_RGB565_PATH` 都指向 `game/picture/object/object_altes_wire.rgb565`。`_load_enemy_runtime_assets(...)` 在路徑與尺寸相同時重用已載入的 object atlas bytes，因此 RAM 不持有第二份 256x256 RGB565 atlas。

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
- `FRAME_WALL total_us=... update_us=... submit_call_us=... tail_res_us=...`
- `CPU_WORK update_us=... compose_us=... desc_us=... kick_cpu_us=...`
- `CPU_COMP bg_us=... tile_us=... obj_us=... enemy_us=...`
- `DMA_SUM ideal_us=... elapsed_us=... gap_us=... exposed_dma_us=... tail_dma_us=...`
- `PIPE_OVERLAP band_comp_us=... band_wait_exposed_us=... tail_update_us=... tail_hidden_us=...`
- `UPDATE_BREAK input_us=... object_us=... enemy_us=... monk_us=...`

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

enemy logic 這條線已經壓得差不多。以最終主線為固定基線時，若要再拉 FPS，優先順序應放在 DMA window 外的前置工作與 setup：

1. 先看 `CPU_WORK.desc_us`。目前平均約 `4.4ms`，是 DMA window 外最大的項目；優先考慮把更多 render descriptor packing 搬到 C++ 或做常駐/增量 buffer。
2. 再看 `PIPE_OVERLAP.band_comp_us[0]`。第一個 band compose 必須在第一段 DMA 前完成，平均約 `1.38ms`；若能降低第一 band 成本，會直接縮短 frame wall。
3. 再看 `CPU_WORK.sync_us` 與 `CPU_WORK.kick_cpu_us - CPU_WORK.push_us`。目前 cache sync + startWrite 約 `1.3-1.4ms`，可研究 band buffer/cache sync 範圍與 panel transaction setup。
4. `DMA_SUM.gap_us` 平均約 `0.63ms`，代表 40MHz SPI full-frame DMA 本身已接近理論值；除非能安全提高 SPI frequency，否則這裡可壓空間有限。
5. `PIPE_OVERLAP.tail_update_us` 顯示 update 大多已藏進 deferred tail DMA；下一步不應只盯 `update_us`，而要看 `update_us - tail_update_us` 是否真的暴露在 frame wall 上。
6. 最終主線固定 `CAMERA_BAND_PIPELINE_H = 48`。若實驗性調 band height，必須同時觀察 `band_comp_us`、`band_wait_exposed_us`、`sync_us`、`DMA_SUM.gap_us`，不能只看 `submit_call_us`；調整結果需重新證明畫面穩定，才可考慮改變基線。
