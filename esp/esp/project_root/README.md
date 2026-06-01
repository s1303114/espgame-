# ESP32S3 Camera Test Mainline

目前主線是：

- internal flash 只保留 `boot.py` / `main.py`
- 遊戲與資產從 `/sd/game` 載入
- Python 更新遊戲狀態
- C++ `lgfx.update_enemies_native(...)` 更新 enemy / bullet
- C++ `lgfx.render_scene_bands_rgb565(...)` 做 4-band compose + wire-order DMA submit

## 目前重點

- 渲染主線：`NATIVE_BAND_PIPELINE`
- band 高度：`60`
- enemy update：`C_API`
- 資產格式：wire-order RGB565
- DMA 前會做 cache sync

## 主要文件

- `BUILD_DETAILED_GUIDE.md`
- `CAMERA_RENDERING_GUIDE.md`
- `CURRENT_ARCHITECTURE_GUIDE.md`
- `OBJECTS_CSV_GUIDE.md`

## 主線驗證標記

板上應看到：

- `Launcher source: sd`
- `SUBMIT_MODE=NATIVE_BAND_PIPELINE`
- `BAND_PIPELINE_NATIVE_ON h=60`
- `ENEMY_UPDATE_IMPL=C_API`
- `BAND_PIPELINE_SUBMIT_OK`

## 建置原則

- firmware 一律優先在 `/tmp/esp-mp-local` 編譯
- `user_cmodules` 改動需要重編 firmware
- 只改 Python / 資產時，用 SD-only 部署
- 外接 SD 同步後一定要 readback 驗證
