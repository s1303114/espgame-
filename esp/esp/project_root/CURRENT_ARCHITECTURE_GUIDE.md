# 玩家技能架構（X/Y 交換）

本文件只描述「玩家技能」相關架構。

---

## 1. 技能定義

目前有兩個核心技能：

- X：與鏡頭範圍內「最遠」可交換目標交換
- Y：與鏡頭範圍內「最近」可交換目標交換

兩者共享同一套交換算法，差別只在目標選擇（far / near）。

---

## 2. 觸發與輸入層

技能觸發在 `app_camera_test.py` 主迴圈內。

輸入穩定化機制：

- 邊緣觸發：只吃 `False -> True` 按下瞬間
- 最小間隔：`SWAP_MIN_INTERVAL_MS`（預設 90ms）
- 目的：避免連點過快或長按導致重複觸發/看似失效

按鍵映射：

- X 技能：`btn_x_pressed` 或 `btn_b_pressed`（兼容板子映射）
- Y 技能：`btn_y_pressed`

---

## 3. 目標挑選規則

目標挑選由 `_pick_swappable_object_index(...)` 負責。

篩選條件：

- 必須在鏡頭可視範圍內
- `visible=1`
- `swappable=1`

距離計算：

- 以玩家中心點到物件中心點的距離平方 `d2` 計算
- X（far）：選 `d2` 最大
- Y（near）：選 `d2` 最小

找不到目標時輸出：

- `SWAP_FAIL_NO_TARGET`

---

## 4. 交換落點算法（目前主線）

交換採用「足底對齊 + 水平置中修正」：

- 玩家新位置
  - `player_x = old_obj_x + ((obj_w - player_w) // 2)`
  - `player_y = old_obj_y + (obj_h - player_h)`
- 物件新位置
  - `obj_x = old_player_x + ((player_w - obj_w) // 2)`
  - `obj_y = old_player_y + (player_h - obj_h)`

目前你指定的策略是：

- 直接交換生效
- 不做碰撞檢查
- 不做回滾

因此 far/near 行為一致，不會因碰撞檢查走不同分支。

---

## 5. 資料結構（objects.csv）

技能依賴 `objects.csv` 內以下欄位：

- `world_x, world_y`：物件世界座標（左上角）
- `w, h`：物件尺寸
- `visible`：是否可見
- `swappable`：是否可被交換（1 可交換，0 不可）

目前路徑：

- `game/picture/object/objects.csv`

---

## 6. 與重力/渲染的關係

交換成功後：

- 會立即更新 `objects_rows`
- 會回寫 `objects_c_buf`（給 C++ 合成用）
- 玩家重力在後續幀照常生效
- object 重力（若啟用）也在後續幀照常生效

渲染上，技能不直接畫圖；它只改世界座標，畫面由原本渲染管線刷新。

---

## 7. 可調參數

在 `config.py` 可調：

- `SWAP_MIN_INTERVAL_MS`：技能連點間隔（建議 70~120）

---

## 8. 驗證方式（看 log）

成功：

- `SWAP_FAR_OK idx=... px=... py=...`
- `SWAP_NEAR_OK idx=... px=... py=...`

失敗：

- `SWAP_FAIL_NO_TARGET`

---

## 9. 設計結論

目前技能架構是：

- 輸入層穩定（邊緣觸發 + 間隔）
- 目標選擇清楚（far/near）
- 交換算法統一（只有目標不同）
- 與渲染層/重力層解耦（只改座標，不改繪製流程）
