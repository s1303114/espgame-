# 物件層說明（objects.csv）

本文件整理目前專案的物件層設計，包含：
- `objects.csv` 欄位定義
- 世界座標與 tile 座標的換算
- `solid` / `trigger` / `type` 的實際用途
- 捲動（camera）下如何轉成螢幕座標

---

## 1. 為什麼要用 objects.csv

地形（tilemap）和物件（箱子、門、道具、觸發區）是兩個層次：

- 地形層：`map1_tilemap.csv`
- 物件層：`objects.csv`

不要把所有物件烘成一張背景圖。物件應該獨立資料化，才好改位置、加事件、做碰撞、做觸發。

---

## 2. 建議欄位格式

```csv
id,type,world_x,world_y,w,h,sprite,solid,trigger,layer,visible
1,block,160,176,32,32,crate_01,1,0,1,1
2,pickup,240,160,16,16,coin_01,0,1,2,1
3,door,640,144,32,48,door_01,1,1,3,1
```

欄位定義：

- `id`：唯一編號
- `type`：物件類型（邏輯用標籤）
- `world_x, world_y`：物件左上角的世界座標（像素）
- `w, h`：碰撞盒尺寸（像素）
- `sprite`：對應到資源 key（atlas/frame 名稱）
- `solid`：`1/0`，是否阻擋玩家
- `trigger`：`1/0`，是否觸發事件（通常不阻擋）
- `layer`：繪製層級（數字小先畫）
- `visible`：`1/0`，顯示開關

---

## 3. 世界座標怎麼數

世界座標是地圖固定座標，不是螢幕座標。

- 原點在地圖左上角：`(0,0)`
- 往右 `x` 增加
- 往下 `y` 增加

### 和 tile 座標的關係（tile=16）

- `world_x = tile_x * 16`
- `world_y = tile_y * 16`
- `tile_x = world_x // 16`
- `tile_y = world_y // 16`

### 從 `map1_tilemap.csv` 直接數

- 第一行第一格是 `(tile_x=0, tile_y=0)`
- 向右 `tile_x +1`
- 向下 `tile_y +1`

---

## 4. 捲動時如何顯示物件

物件儲存的是世界座標，每幀要轉成螢幕座標：

- `screen_x = world_x - camera_x`
- `screen_y = world_y - band_top`

如果物件超出螢幕可視範圍，直接跳過（culling）。

---

## 5. solid 與 trigger 差異

- `solid=1`：會擋住玩家（碰撞阻擋）
- `trigger=1`：不擋住，但進入區域會觸發事件

可以同時存在，例如門：
- 平常 `solid=1`
- 玩家達成條件後改 `solid=0`
- 接觸時 `trigger=1` 觸發換場

---

## 6. type 建議值

`type` 沒有固定標準，建議先用以下集合：

- `decor`：裝飾
- `block`：一般障礙
- `platform`：平台
- `hazard`：傷害區
- `pickup`：可撿物
- `checkpoint`：檢查點
- `door`：門
- `portal`：傳送
- `npc`：NPC
- `switch`：開關
- `breakable`：可破壞物
- `spawn`：出生點
- `event`：劇情事件區

重點：
- `type` 負責「邏輯分類」
- `solid` / `trigger` 負責「碰撞/觸發行為」

---

## 7. 物件大小不一致怎麼辦

不用統一尺寸。每筆物件自己帶 `w,h` 即可。

- 渲染：依 `sprite` 實際尺寸畫
- 碰撞：依 `w,h` 做 AABB

這也是物件層不該烘成一張背景圖的原因。

---

## 8. 放置物件的實務流程（推薦）

1. 先在 `map1_tilemap.csv` 找 tile 位置
2. 換算成 `world_x, world_y`
3. 填入 `objects.csv`
4. 上板測試
5. 若要貼地：
   - `object_world_y = tile_y * 16 - object_h`

---

## 9. 常見錯誤

- 把 `world_x,world_y` 當成螢幕座標（錯）
- 同一份資料混用中心點與左上角（錯）
- `solid=1` 和 `trigger=1` 的語意沒分開（後續邏輯會亂）
- 物件沒做 culling，導致每幀繪製太多不可見物件

---

## 10. 最小可用結論

若你要先快速上線：

- 座標基準統一：**左上角 world 座標**
- 碰撞規則：`solid=1` 才阻擋
- 觸發規則：`trigger=1` 才觸發
- 類型判斷：用 `type` 做 dispatch

這樣之後要擴充（道具、傳送、對話、事件）都不用改資料格式。
