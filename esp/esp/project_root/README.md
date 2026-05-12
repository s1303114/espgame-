# ESP32-S3 MicroPython Swap Prototype

## 專案結構
- `boot.py`: 開機最小化初始化（保持輕量、避免副作用）。
- `main.py`: root launcher，嘗試 SD 掛載並固定進入 `test_entry.run()`。
- `test_entry.py`: TEST/FORMAL 模式切換與 app 匯入路徑控制。
- `sd_game_template/game/app.py`: Phase 5~8 主迴圈與驗收 runtime。
- `sd_game_template/game/config.py`: 顏色、按鍵、phase mode、驗收幀數常數。
- `sd_game_template/game/engine/ui.py`: Phase 8 HUD 圖塊組裝（固定頂部區域）。
- `sd_game_template/game/engine/save_system.py`: Phase 8 JSON save/load（容錯與白名單 reason）。
- `sd_game_template/game/maps/stage01.json`: 主關卡資料。
- `sd_game_template/game/save/save0.json`: 預設存檔模板。

正式 SD 內容目錄為 `/sd/game`，可由 `sd_game_template/game` 部署得到。

## 啟動流程
1. 裝置重啟後執行 `boot.py`。
2. 進入 `main.py`，嘗試掛載 SD（容錯，不可因無卡而 crash）。
3. `main.py` 載入 `test_entry.py` 並呼叫 `test_entry.run()`（reset 驗收鏈固定保留）。
4. `test_entry.py`：
   - `MODE="TEST"`：固定幀 deterministic 驗收（root 優先、sd fallback）。
   - `MODE="FORMAL"`：正式模式（sd 優先、root fallback）。
5. `app.run()` 依 `config.PHASE_ACCEPTANCE_STAGE` 切到對應 phase runtime。

## 已完成功能
- Phase 0: 顯示底層整合。
- Phase 1: 專案骨架。
- Phase 2: 最小顯示 API 擴充。
- Phase 3: 局部重繪壓測。
- Phase 4: 輸入系統（含 edge trigger）。
- Phase 5: 玩家左右移動、重力、墜落、地圖碰撞。
- Phase 6: `Entity / enemy_basic / enemy_shooter / bullet pool`。
- Phase 7: `Near Swap / Far Swap / air-swap-fall`。
- Phase 8（目前版本）：
  - 固定頂部 HUD 圖塊（HP、X/B 提示、SAVE 狀態、DEBUG 狀態）
  - save_system 最小可用 JSON 讀寫（事件驅動）
  - Phase8 deterministic marker（UI/SAVE/DRAW）
  - SD 啟動路徑容錯 marker（`PHASE8_SD_BOOT_OK`）

## 待辦項目
- Phase 8 人工驗收最終確認（目前未宣告通過）。
- README 後續維護：新增硬體版本差異與更多部署案例。
- 後續 phase 的玩法擴充與系統化（非本階段範圍）。

## 部署 / 驗收方式
### 部署
1. 將 `sd_game_template/game` 部署到板上（root 或 `/sd/game`）。
2. root 保留 `boot.py/main.py/test_entry.py`。
3. reset 後由 `main -> test_entry -> app` 自動執行。

### deterministic 驗收
1. `test_entry.MODE="TEST"`。
2. 設 `config.PHASE_ACCEPTANCE_STAGE="PHASE8"`。
3. 觀察 marker：
   - `APP_RUN_START_PHASE8`
   - `PHASE8_UI_OK`
   - `PHASE8_SAVE_OK`
   - `PHASE8_DRAW_OK`
   - `APP_RUN_END_PHASE8`
   - `PHASE8_SD_BOOT_OK`（由 test_entry 路徑容錯邏輯輸出）
   - `TEST_ENTRY_PASS`

### MANUAL 驗收
1. `config.PHASE8_ACCEPTANCE_MODE="MANUAL"`。
2. `BTN_A`：觸發 save（SAVE OK/FAIL 圖塊短暫顯示後回中立）。
3. `BTN_Y`：debug on/off（同步輸出 `PHASE8_DEBUG_ON/OFF`）。
4. `BTN_X/BTN_B`：保持 Near/Far。
5. 觀察畫面不可回歸：黑撕裂、粉紅化、白點、邊界裁切。
