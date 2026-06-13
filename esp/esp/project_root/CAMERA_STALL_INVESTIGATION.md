# Camera Stall Investigation

日期：2026-06-12 至 2026-06-13

本文件整理 map1 camera renderer 掉幀 / 800ms 級 stall 的完整追查過程，從最早觀察到的現象、每一輪 log 證據、已做修改、驗證結果，到目前剩餘問題與下一步計畫。

## 目標與原則

一開始的要求是：不要猜，要用實質證據找出掉幀原因。整個過程都依照這個原則進行：

- 先加低噪音 trace，只在 stall 時 dump 前後幀。
- 每次只針對 log 指向的 hot path 修改。
- 修改後重新部署到 SD / firmware，跑 board capture 驗證。
- 如果 stall 位置改變，就繼續加更細 marker，而不是直接推測。

## 執行環境

- Board：ESP32-S3，MicroPython custom firmware。
- App source：`/sd/game/app_camera_test.py`。
- App runtime：flash `main.py` launcher 會優先載入 `/sd/game/app_camera_test.mpy`，避免巨大 source 在板上 `exec` 時 bytecode overflow。
- 主要渲染模式：`ROWS_SAFE_PROGRESSIVE`。
- Native renderer：`lgfx.render_scene_bands_rgb565(...)`。
- Native band pipeline：`CAMERA_BAND_PIPELINE_NATIVE=True`，band height 48。
- SD mount：`machine.SDCard(slot=2, width=1, sck=5, mosi=6, miso=7, cs=4, freq=1000000)`。

## 相關檔案

### Python runtime

- `sd_game_template/game/app_camera_test.py`
  - 主遊戲 loop、camera render submit context、Python fallback、enemy/orb state glue。
- `sd_game_template/game/native_submit_glue.py`
  - 建立 native-only submit context extension 與 scratch buffers，避免把更多初始化 bytecode 塞回巨大主檔。
- `sd_game_template/game/stall_trace.py`
  - 低噪音 stall trace ring buffer，只在超過門檻時 dump。
- `sd_game_template/game/config.py`
  - trace / profile / quiet log 開關。
- `main.py`
  - flash launcher，負責載入 SD app；已加入 reload 時清掉 `stall_trace` / `native_submit_glue` module cache，並優先 import `.mpy`。

### Native MicroPython module

- `../micropython/user_cmodules/lgfx/lgfx_band.cpp`
  - native band renderer、tail wait、render profile buffer、native submit orchestration wrapper。
- `../micropython/user_cmodules/lgfx/lgfx_mp.cpp`
  - lgfx module export table 與其他 native API。
- `../micropython/user_cmodules/lgfx/lgfx_shared.hpp`
  - cross-file function object declaration。

### 重要 log

- `logs/board_capture_2026-06-12_stall_trace_refined.log`
- `logs/board_capture_2026-06-12_update_part_trace.log`
- `logs/board_capture_2026-06-12_desc_part_trace.log`
- `logs/board_capture_2026-06-12_overlay_debug_gate_validation.log`
- `logs/board_capture_2026-06-12_packed_enemy_desc_validation.log`
- `/tmp/esp_native_submit_run_90s.txt`
  - native submit wrapper 初版驗證；仍有一次 stall，證明 wrapper 因 fallback guard 未真正接管。
- `/tmp/esp_native_submit_run_90s_2.txt`
  - 移除錯誤 fallback guard 後的 90 秒驗證；native submit active，無 stall。

## 一開始看到的問題

症狀是遊戲偶發掉幀，單幀時間到 800ms 左右。早期 log 顯示：

```text
STALL_FRAME total_us=819349 update_us=4756 submit_us=33350 desc_us=5390 compose_us=10306 wait_dma_us=15618 dma_us=24731
```

或類似：

```text
STALL_FRAME total_us=822065 update_us=4984 submit_us=35429 desc_us=7277 compose_us=10278 wait_dma_us=15712 dma_us=24732
```

重點是：

- `compose_us` 約 10ms。
- `wait_dma_us` 約 14-16ms。
- `dma_us` 約 24-25ms。
- C++ renderer 內部時間不像 800ms。
- 但外層 frame total 會到 800ms。

因此初步排除「LCD/DMA 本身卡 800ms」。問題比較像 Python / MicroPython object allocation / GC，或 native return 物件建立後才被計入外層時間。

## 第一階段：建立 stall trace

新增 `stall_trace.py`，記錄每幀重要時間點，只有超過門檻才 dump ring buffer。

主要 marker：

- frame start / finish
- update end
- tail wait end
- submit start / end
- native render done
- native profile unpack done
- debug/profile/hud marker

當時 config：

```python
CAMERA_STALL_FRAME_US = 200000
CAMERA_STALL_LOG_ENABLED = True
CAMERA_STALL_TRACE_ENABLED = True
CAMERA_STALL_TRACE_SIZE = 32
```

目標是避免每幀大量 print，降低 log 本身造成的干擾。

## 第二階段：native 大 tuple / Python unpack 問題

### 證據

`stall_trace_refined` / `update_part_trace` 顯示：

```text
sub_wall=816577 sub_us=35429 sub_extra=781148
```

以及：

```text
sub_wall=796492 sub_us=35837 sub_extra=760655
```

其中：

- `sub_us` 是 `_submit_native_band_frame()` 內量到的時間，大約 35ms。
- `sub_wall` 是外層看到 submit path 的 wall time，大約 800ms。
- `sub_extra` 高達 760-781ms。

這表示 stall 不在 C++ compose/DMA 本體，而是在 native call 回來後或 Python unpack/return 之間。

### 原因

`lgfx.render_scene_bands_rgb565(...)` 原本會回傳大型 tuple，詳細 profile 模式可到 29 fields。C++ 內部 `total_us` 是在 tuple 建立前量的，因此 tuple allocation / MicroPython GC 不會被 C++ profile 反映。

Python 端也會 unpack 大 tuple，且 `_submit_native_band_frame()` 早期還會回傳 tuple 給 caller，造成每幀額外 allocation。

### 修改

1. C++ renderer 加 short tuple / profile detail flag。
2. Python `_unpack_band_profile_result(band_res, out)` 改成填入 preallocated list/array。
3. `_submit_native_band_frame(..., band_profile=None, submit_result=None)` 不再回傳大型 tuple，而是填入 caller-provided buffers。
4. C++ 新增 global profile snapshot + out-buffer API：

```cpp
lgfx.copy_last_render_profile(out_obj)
```

5. Python 使用：

```python
native_submit_profile = array('I', [0] * 28)
_lgfx.copy_last_render_profile(native_submit_profile)
```

### 相關檔案

- `lgfx_band.cpp`
  - `g_last_render_profile`
  - `set_last_render_profile(...)`
  - `lgfx_copy_last_render_profile(...)`
  - `probe_flags & 0x4` 時回傳 `None`，profile 由 buffer copy 取得。
- `lgfx_shared.hpp`
  - 宣告 `lgfx_copy_last_render_profile_obj`。
- `lgfx_mp.cpp`
  - export `copy_last_render_profile`。
- `app_camera_test.py`
  - `_native_profile_buffer_supported()`
  - `_new_native_submit_profile()`
  - `_submit_native_band_frame(..., band_profile, submit_result)`

### 驗證結果

在後續 trace 中，原本 760-781ms 的 `sub_extra` 消失，正常幀約：

```text
sub_extra=531
post_native=115
post_unpack=42
```

這證明 native return/profile allocation 問題已被修掉。

## 第三階段：descriptor packing 開始浮現

profile-buffer 修掉後，新的 stall 顯示：

```text
frame=1628 total_us=841483
update_us=4721
submit_us=835472
sub_extra=531
post_native=117
post_unpack=39
desc_us=806858
compose_us=12618
wait_dma_us=13750
dma_us=24753
```

重點：

- `sub_extra` 已正常。
- native return / unpack 已不是問題。
- `desc_us` 變成 806ms。

因此問題轉移到 Python descriptor packing。

## 第四階段：加入 d0..d8 descriptor trace

為了找出是哪段 descriptor packing，加入 d0..d8：

- `d0`：special object descriptors。
- `d1`：monk orb descriptors。
- `d2`：intro orb descriptors。
- `d3`：final path descriptors。
- `d4`：swap preview descriptor。
- `d5`：assembled special copy。
- `d6`：overlay descriptors，主要是 bullet overlay。
- `d7`：enemy descriptors + monk death render state。
- `d8`：intro enemy body descriptors + merge。

## 第五階段：d6 overlay descriptor stall

### 證據

`board_capture_2026-06-12_desc_part_trace.log`：

```text
STALL_TRACE f=1537 ... desc=768357 ... d6=765003 ...
STALL_FRAME total_us=803253 update_us=5655 submit_us=796427 desc_us=768357
```

解讀：

- C++ compose/DMA 正常。
- native return/profile 正常。
- descriptor packing 中 d6 佔 765ms。
- d6 對應 `_pack_special_render_overlays(...)`。

### 原因

`_pack_special_render_overlays(...)` 內有：

```python
if overlay_count <= 3:
    _bullet_debug(
        "BULLET_OVERLAY",
        "wx=%d ..." % (...),
    )
```

問題是 `_bullet_debug()` 內雖然會在 `_BULLET_DEBUG_LIMIT` 滿後 return，但呼叫端已經先做完字串格式化。也就是 quiet logs 不印，仍然每幀配置 debug string。

這種每幀 allocation 會累積 GC 壓力，最後在 d6 區段偶發 800ms stall。

### 修改

新增：

```python
def _bullet_debug_enabled():
    return _bullet_debug_count < _BULLET_DEBUG_LIMIT
```

把 debug call 改成先 gate 再格式化：

```python
if overlay_count <= 3 and _bullet_debug_enabled():
    _bullet_debug(...)
```

同時修其他 bullet debug hot path：

- `_spawn_enemy_bullet(...)`
- `_update_enemies_and_bullets(...)`
- `_bullet_debug_active(...)`

另外 `_PackedEnemyBullets.clear()` 改成只清 active flag，不釋放 bytearray：

```python
while i < self._count:
    _buf_set_i16_le(self._buf, base + 12, 0)
```

避免死亡 / 重生後重新配置 bullet buffer。

### 驗證結果

`board_capture_2026-06-12_overlay_debug_gate_validation.log`：

```text
desc_us=7023
d6=2627
```

d6 從 765003us 降到約 2.6ms。

但同一份 validation 又暴露下一層問題：

```text
STALL_TRACE f=3537 ... desc=806899 ... d7=802364 ...
```

## 第六階段：d7 enemy descriptor stall

### 證據

`board_capture_2026-06-12_overlay_debug_gate_validation.log`：

```text
STALL_TRACE f=3537 ... desc=806899 ... d7=802364 ...
STALL_FRAME total_us=841495 submit_us=835470 desc_us=806899
```

解讀：

- d6 已正常。
- 新的大 stall 位於 d7。
- d7 對應 `_pack_enemy_render_descriptors(...)` + `_apply_monk_death_render_state(...)`。

### 原因

`_pack_enemy_render_descriptors(...)` 每幀走 Python dict/string path：

```python
state.get("anim_counter", 0)
state.get("state", _ENEMY_STATE_IDLE)
state.get("facing", 1)
str(meta.get("type", "bow") or "bow")
```

`enemy_states` 雖然已是 `_PackedEnemyStates`，但 `state = enemy_states[ei]` 仍建立 view object，`state.get(...)` 也走 Python method dispatch。`meta.get(...)` 和 `str(...)` 每幀也會製造 object / GC 壓力。

### 修改

新增一次性 enemy type code buffer：

```python
_enemy_type_codes = bytearray(...)
```

實際新增 helper：

- `_pack_enemy_type_codes(meta_rows)`
- `_sync_enemy_type_codes(type_codes, meta_rows)`
- `_pack_enemy_render_descriptors_packed(...)`
- `_pack_enemy_render_descriptors_fast(...)`

新的 fast path 從 fixed buffers 讀資料：

- `enemy_rows_c_buf`
- `enemy_states._buf`
- `enemy_type_codes`

不再每幀讀 `enemy_meta` dict，也不再每幀 `str(meta.get(...))`。

live monk 從 encounter 生成時，同步更新 `enemy_type_codes`，避免 monk 被畫成 bow。

### 相關修改點

- `_load_enemy_runtime_assets(...)`
  - 建立並保存 `enemy_type_codes`。
- `_instantiate_live_monk_from_encounter(...)`
  - 新增 `enemy_type_codes` 參數。
  - monk live enemy append / meta replace 後呼叫 `_sync_enemy_type_codes(...)`。
- `_update_monk_encounters(...)`
  - 傳遞 `enemy_type_codes`。
- `_submit_native_band_frame(...)`
  - d7 改用 `_pack_enemy_render_descriptors_fast(...)`。

### 驗證結果

`board_capture_2026-06-12_packed_enemy_desc_validation.log`：

```text
STALL_TRACE f=1719 ... d6=1891 d7=719 d8=243 ...
```

d7 從 802364us 降到 719us。

## 第七階段：剩餘問題變成超長 Python function call entry

### 新增 call boundary marker

為了確認 stall 是否在 helper 內部，新增：

- `mark_submit_call_start(t)`
- `mark_submit_helper_enter(t)`

trace 輸出新增：

- `call0`
- `call1`
- `call_enter_us`
- `helper_gap_us`

### 最新證據

`board_capture_2026-06-12_packed_enemy_desc_validation.log`：

```text
STALL_TRACE f=1719 ...
sub0=5643
call0=5667
call1=785171
native_done=819920
sub_wall=814624
sub_us=34598
sub_extra=780026
call_enter_us=779504
helper_gap_us=34749
desc=6481
comp=10356
wait_dma=15639
dma=24766
d6=1891
d7=719
```

解讀：

- `call0` 到 `call1` 花了 779504us。
- `call1` 是 `_submit_native_band_frame(...)` 第一行 marker。
- 所以 stall 發生在進入 helper 之前。
- helper 內部時間 `helper_gap_us=34749`，與正常 render submit 約 34ms 相符。
- `desc=6481`，d6/d7 都正常。

目前結論：最新大 stall 不是 LCD/DMA，不是 C++ renderer，不是 C++ 回傳資料，也不是 d6/d7 descriptor 內部，而是 Python 每幀呼叫超長 `_submit_native_band_frame(...)` positional-argument function 時，MicroPython call frame / VM / GC 壓力造成的偶發長停頓。

## 為什麼一開始感覺沒有這麼常

這不是單一問題，而是一串 hot path allocation / call pressure 被逐層剝開：

1. 最早 native tuple return / Python unpack 的 760-781ms 蓋住其他問題。
2. 修掉後，d6 overlay debug string allocation 浮出來。
3. 修掉 d6 後，d7 enemy descriptor dict/string path 浮出來。
4. 修掉 d7 後，超長 positional function call entry 浮出來。

此外：

- 遊戲狀態後期更複雜，例如 monk/orb/clash/lost 後 `enemies=4`、`orbs=20`。
- 現在是 180 秒 capture，較容易抓到偶發 GC spike。
- `stall_trace` 本身是低噪音，但仍增加一些 Python work，所以最後確認時要關掉 trace 再跑乾淨 validation。

## 第八階段：Python submit context 過渡驗證

### 目標

把原本 `_submit_native_band_frame(...)` 的 90 個以上 positional arguments 改成單一 reusable context list：

```python
_submit_native_band_frame(native_submit_ctx)
```

這個階段是過渡驗證，目的不是一次搬完所有 submit orchestration，而是先減少 MicroPython 每幀建立大型 call frame 的壓力，並保留 Python fallback 方便比對。

### 修改

- 新增 `_new_native_submit_ctx(...)`：初始化固定資源 slot。
- 新增 `_refresh_native_submit_ctx(...)`：每幀只更新 camera、player、animation、dirty countdown、tail overlap 等會變的 slot。
- `_submit_native_band_frame_fallback(ctx)` 保留原本 Python 大流程，但只 unpack `ctx[:93]`，忽略 native-only extension。
- `run()` hot path 改成呼叫 `_submit_native_band_frame(native_submit_ctx)`。

### 結果

context call 降低了函式簽名複雜度，但還沒完全解決剩餘 800ms stall。後續 trace 顯示 stall 仍可發生在進入 `_submit_native_band_frame(ctx)` 這個 Python helper 的 call boundary，因此需要把 submit orchestration 直接搬進 C++，讓 Python 每幀只做最薄的一層 native call。

## 第九階段：C++ native submit orchestration

### 目標

把 Python submit helper 內的 descriptor packing、band compose、DMA submit、profile/result 回寫搬進 C++：

```python
_lgfx.submit_native_band_frame(ctx)
```

Python 端只保留：

- high-level game state / config / assets。
- submit context 初始化與少量 slot refresh。
- C++ wrapper 不支援時的 fallback。

### 修改

#### C++ / native module

新增 `lgfx.submit_native_band_frame(ctx)`：

- 從 ctx 讀取固定 buffers、tilemap、objects、enemy rows/states、monk orbs、attack buffers、player sprite、profile/result buffers。
- C++ 內部打包：
  - special objects
  - monk orbs
  - swap preview
  - bullet overlays
  - enemies
- C++ 直接呼叫 native band compose / DMA submit。
- 將 `g_last_render_profile` copy 到 caller-provided profile buffer。
- 將 `sprite_x`、`sprite_y`、`spr_y`、`total_us`、`dirty_log_countdown`、`descriptor_us` 寫回 caller-provided result list。
- 成功時回傳 `True`，不支援時回傳 `False` 讓 Python fallback 接手。

新增 / 更新的 native 註冊：

- `lgfx_band.cpp`
  - `lgfx_submit_native_band_frame(...)`
  - `MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_submit_native_band_frame_obj, 1, 1, ...)`
- `lgfx_shared.hpp`
  - `extern const mp_obj_fun_builtin_var_t lgfx_submit_native_band_frame_obj;`
- `lgfx_mp.cpp`
  - real module globals 加入 `submit_native_band_frame`
  - `NO_QSTR` globals 也加入同名 entry，避免 qstr build 問題

#### Python runtime

- `app_camera_test.py`
  - optional import `native_submit_glue`
  - `_new_native_submit_ctx(...)` 建立原本 93-field context 後呼叫 `native_submit_glue.extend_ctx(...)` 加上 native-only 欄位
  - `_submit_native_band_frame(ctx)` 改成 native-first wrapper：先呼叫 `_lgfx.submit_native_band_frame(ctx)`，成功就直接 return，失敗才 fallback
- `native_submit_glue.py`
  - 建立 special object spec buffer
  - 建立 special/enemy/overlay descriptor scratch buffers
  - 將 object state buffer、enemy state buffer、bullet buffer、color key 等 native-only 欄位 append 到 ctx

#### Launcher / deploy

`app_camera_test.py` 已經大到在板上 source `exec` 會出現：

```text
RuntimeError: bytecode overflow
SAFE MODE
```

因此 flash `main.py` 改成：

- 若同名 `.mpy` 存在，優先 `__import__(name)` 載入 `.mpy`。
- 若 `.mpy` 不存在，才 fallback 讀 `.py` source 並 `exec`。
- reload 時 purge `native_submit_glue`。

目前部署規則：修改 `config.py`、`native_submit_glue.py`、`app_camera_test.py` 後，要重新用 `mpy-cross` 產生並部署對應 `.mpy`。

### 初版驗證與問題

native symbol probe 已通過：

```text
HAS_SUBMIT_NATIVE True
```

launcher 改 `.mpy` 後，safe mode / bytecode overflow 消失。

但第一段 90 秒 capture 仍有一次 stall：

```text
STALL_TRACE f=1259 ...
sub_wall=813442
sub_us=33382
sub_extra=780060
call_enter_us=779386
helper_gap_us=33636
desc=5274
d0=1734 d6=457 d7=458 d8=639
```

解讀：

- d0/d6/d7/d8 都正常。
- C++ submit body 約 33ms。
- 779ms 仍在 Python helper call entry。
- 當時沒有 `BAND_PIPELINE_SUBMIT_OK`，代表 native wrapper 沒有穩定接管。

### 最後 root cause：錯誤 fallback guard

C++ wrapper 初版有一個過度保守條件：看到 `ctx[25]` 的 `monk_encounters` list truthy 就回傳 `False`。

這個判斷是錯的，因為 `monk_encounters` list 在穩態也可能常駐非空；它不代表當幀一定需要 Python-only intro render。結果是大多數 frame 直接 fallback 到 Python helper，800ms call-entry 問題自然還會出現。

修正方式：移除這個 truthy-list guard，讓 C++ wrapper 依實際 buffer/state 支援度處理當幀 submit。

### 最終驗證

重新 build / flash 後，短 boot check 已看到 native wrapper 成功標記：

```text
BAND_PIPELINE_SUBMIT_OK
```

接著跑 90 秒 capture：

```text
SAFE MODE 0
bytecode overflow 0
Traceback 0
SUBMIT_NATIVE_WRAPPER_FAIL 0
BAND_PIPELINE_SUBMIT_OK 58
STALL_TRACE_BEGIN 0
STALL_FRAME 0
```

這段驗證證明：

- `.mpy` launcher 解掉 bytecode overflow / safe mode。
- `lgfx.submit_native_band_frame(ctx)` 已真正接管 submit path。
- 先前約 800ms 的 Python call-entry stall 在這段 90 秒驗證中沒有再出現。

## 目前已完成修改總表

### C++ / native module

#### `lgfx_band.cpp`

- 新增 `g_last_render_profile` fixed-size profile snapshot。
- 新增 `set_last_render_profile(...)`。
- 新增 `lgfx_copy_last_render_profile(out_obj)`。
- `render_scene_bands_rgb565(...)` 支援：
  - short tuple fallback。
  - detail profile flag。
  - profile-to-buffer flag `probe_flags & 0x4`。
  - profile-to-buffer 時回傳 `None`，避免大型 tuple allocation。
- 新增 `lgfx_submit_native_band_frame(ctx)`，把 submit orchestration / descriptor packing / band compose / DMA submit 搬進 C++。

#### `lgfx_shared.hpp`

- 宣告 `lgfx_copy_last_render_profile_obj`。
- 宣告 `lgfx_submit_native_band_frame_obj`。
- 注意 typedef 使用 `mp_obj_fun_builtin_fixed_t`。

#### `lgfx_mp.cpp`

- export `copy_last_render_profile` 到 `lgfx` module。
- export `submit_native_band_frame` 到 real globals 與 `NO_QSTR` globals。

### Python runtime

#### `app_camera_test.py`

- import optional `array`。
- import optional `stall_trace`。
- 新增 `_native_profile_buffer_ready`。
- 新增 `_native_profile_buffer_supported()`。
- 新增 `_new_native_submit_profile()`。
- `_unpack_band_profile_result(band_res, out)` 改成 out-buffer。
- `_submit_native_band_frame(...)` 改成填入 caller-provided `band_profile` / `submit_result`。
- 使用 `_lgfx.copy_last_render_profile(band_profile)`。
- 新增 `_trace_desc_part(...)`。
- descriptor packing 加上 d0..d8 marker。
- 新增 `_bullet_debug_enabled()`，所有 bullet debug format 前先 gate。
- `_PackedEnemyBullets.clear()` 保留 capacity，只清 active flag。
- 新增 `enemy_type_codes` 快取。
- 新增 packed enemy descriptor path：
  - `_pack_enemy_type_codes(...)`
  - `_sync_enemy_type_codes(...)`
  - `_pack_enemy_render_descriptors_packed(...)`
  - `_pack_enemy_render_descriptors_fast(...)`
- live monk instantiate 時同步 `enemy_type_codes`。
- 新增 submit call boundary markers：
  - `mark_submit_call_start`
  - `mark_submit_helper_enter`
- 新增 native submit context：
  - `_new_native_submit_ctx(...)`
  - `_refresh_native_submit_ctx(...)`
  - `_submit_native_band_frame(ctx)` native-first wrapper
  - `_submit_native_band_frame_fallback(ctx)` Python fallback

#### `native_submit_glue.py`

- 新增 submit ctx native extension：
  - object state buffer / stride / count
  - special object spec buffer
  - special / enemy / overlay descriptor scratch buffers
  - player / transparent / object color keys
  - enemy state packed buffer
  - enemy bullet packed buffer

#### `stall_trace.py`

- ring buffer trace。
- update part markers `up0..up7`。
- descriptor part markers `d0..d8`。
- submit detailed markers：
  - `native_done`
  - `unpack_done`
  - `log0/log1`
  - `pre_ret`
  - `call0/call1`
  - `call_enter_us`
  - `helper_gap_us`

#### `config.py`

目前為了驗證保留：

```python
CAMERA_QUIET_LOGS = True
CAMERA_RUNTIME_VERBOSE = False
CAMERA_RENDER_PROFILE_DETAIL = False
CAMERA_NATIVE_PROFILE_DETAIL = False
CAMERA_STALL_FRAME_US = 200000
CAMERA_STALL_LOG_ENABLED = True
CAMERA_STALL_TRACE_ENABLED = True
CAMERA_STALL_TRACE_SIZE = 32
CAMERA_GC_THRESHOLD_BYTES = 0
```

最後驗證完成後，`CAMERA_STALL_TRACE_ENABLED` 應改回 `False` 或保留為 debug-only。

#### `main.py`

- reload SD app 前 purge `stall_trace` / `native_submit_glue`，避免 SD 更新後仍用舊 module。
- `_exec_module_from_path(...)` 優先載入 `.mpy`，避免 `app_camera_test.py` source `exec` bytecode overflow。

## 目前尚未完成 / 下一步

### 短期

1. 跑更長時間 soak test，確認 `BAND_PIPELINE_SUBMIT_OK` 持續出現且沒有 `STALL_FRAME`。
2. 最終乾淨 validation 時可關掉或縮小 stall trace，減少 debug overhead。
3. 刪除臨時 helper：
   - `tmp_mount_sd.py`
   - `tmp_check_profile_api.py`
4. audit 其他 native tuple API：
   - `render_elevator_scene_bands_rgb565` 仍回傳 29-field tuple，map2 之後要改 profile buffer。
   - `update_objects_native` / `update_enemies_native` 目前是 2-tuple，優先級較低，但可改 out-buffer。
   - `band_pipeline_tail_wait` 是 5-tuple，目前沒有證據指向它，但長期可改 fixed buffer。
5. 中長期把 swap target query、monk/orb state 更完整地往 C++ / fixed buffer 移。

## 當前結論

目前已證明並完成：

- 不是 LCD/DMA 送畫面卡 800ms。
- 不是 C++ renderer compose 本體卡 800ms。
- native 大 tuple/profile return 曾經是問題，已修。
- d6 overlay descriptor 曾經是問題，已修。
- d7 enemy descriptor 曾經是問題，已修。
- Python submit helper call-entry 曾是最新剩餘問題，`call_enter_us` 可到約 779ms。
- Python context 過渡降低了呼叫簽名壓力，但仍保留 Python helper boundary。
- C++ `lgfx.submit_native_band_frame(ctx)` 搬走 submit orchestration 後，需確保 wrapper 真的接管，不能被錯誤 fallback guard 擋掉。
- 移除 `monk_encounters` truthy fallback guard 後，native wrapper 在 90 秒驗證中成功接管，`BAND_PIPELINE_SUBMIT_OK=58`，`STALL_FRAME=0`。

當前狀態：800ms 級 camera submit stall 在最新 90 秒板上驗證中已消失。下一步是更長時間 soak 與 debug trace 收斂，不是再回頭改 LCD/DMA 或 d6/d7。
