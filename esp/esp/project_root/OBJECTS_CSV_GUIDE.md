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

## 2. 目前主線欄位格式

目前 `app_camera_test.py` 的 loader 需要以下基礎欄位。若存在 `anim_id` 等額外欄位，會被保留到 metadata，供 special animation overlay 使用：

```csv
id,type,world_x,world_y,w,h,sprite,solid,trigger,layer,visible,swappable,src_x,src_y,src_w,src_h
1,block,160,176,32,32,crate_01,1,0,1,1,1,0,0,32,32
2,pickup,240,160,16,16,coin_01,0,1,2,1,0,32,0,16,16
3,door,640,144,32,48,door_01,1,1,3,1,1,64,0,32,48
```

欄位定義：

- `id`：唯一編號，目前主要給人工辨識。
- `type`：物件類型（邏輯用標籤）。
- `world_x, world_y`：物件左上角的世界座標（像素）。
- `w, h`：碰撞盒尺寸（像素）。
- `sprite`：資源 key，目前主線渲染不直接用這欄，而是用 `src_x/src_y/src_w/src_h` 指到 atlas。
- `solid`：`1/0`，是否阻擋玩家。
- `trigger`：`1/0`，是否觸發事件（通常不阻擋）。
- `layer`：繪製層級，保留欄位；目前基礎 object atlas 仍照 CSV 順序打包/繪製。
- `visible`：`1/0`，顯示開關；不可見物件不會被打包到 C++ render buffer。
- `swappable`：`1/0`，是否可被 B/Y 交換技能選中。
- `src_x, src_y, src_w, src_h`：此物件在 `objects_atlas_wire.rgb565` 裡的來源矩形。

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


## 4.1 目前渲染資料路徑

主線 object 渲染資源：

- CSV：`/sd/game/picture/object/objects.csv`
- atlas：`/sd/game/picture/object/objects_atlas_wire.rgb565`
- atlas 尺寸：目前 `OBJECTS_ATLAS_W = 256`、`OBJECTS_ATLAS_H = 256`
- byte order：panel wire-order，也就是每個 RGB565 pixel 以 `hi, lo` 存放。

啟動時 Python 會：

1. 讀取 `objects.csv` 成 `objects_rows`。
2. 建立 `object_solids`，供玩家碰撞/交換邏輯使用。
3. 將 visible object 打包成 `objects_c_buf`，供 C++ renderer 使用。
4. 載入 `objects_atlas_wire.rgb565`。

`objects_c_buf` 每筆固定 12 bytes：

```text
int16/uint16 little-endian fields:
world_x, world_y, src_x, src_y, src_w, src_h
```

也就是：

```text
byte 0..1   world_x
byte 2..3   world_y
byte 4..5   src_x
byte 6..7   src_y
byte 8..9   src_w
byte 10..11 src_h
```

注意：這個 12-byte buffer 是 CPU 端資料結構，不是 RGB565 pixel buffer，所以欄位本身仍是 little-endian 整數。只有 atlas 圖像像素是 wire-order。

目前 native band pipeline 中，object 由 C++ `render_scene_bands_rgb565(...)` 在每個 band 內 compose。透明色使用 magenta `#FF00FF`：

- 語意 RGB565：`0xF81F`
- wire-order raw compare value：`0x1FF8`

Python 傳給 C++ 前會對 colorkey 做 `_swap16(...)`，所以 C++ 可以直接用 raw 16-bit value 比較 atlas 內的 wire-order bytes。


### 4.2 Special animation overlay

目前 object layer 另外支援 special animation overlay：

- 設定路徑：`OBJECT_ANIMATIONS_JSON_PATH = "game/picture/object/object_animations.json"`
- 圖像來源仍是 `objects_atlas_wire.rgb565`。
- Python 會依 object metadata、respawn anchor、enemy bullet 等狀態打包 overlay descriptor。
- native band pipeline 會在基礎 object atlas 後、player sprite 前繪製 overlay。
- 因此 special object 不再需要 fallback 到 Python 逐像素繪製。

overlay 與 object atlas 一樣使用 wire-order RGB565，透明比較值仍是 `0x1FF8`。

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
- `visible=0` 但仍期待畫面出現（不可見物件不會進 C++ render buffer）
- `src_x/src_y/src_w/src_h` 超出 atlas 範圍（C++ 會跳過該物件）
- atlas 不是 wire-order，導致顏色錯或 colorkey 失效
- 物件沒做 culling，導致每幀繪製太多不可見物件

---

## 10. 最小可用結論

若你要先快速上線：

- 座標基準統一：**左上角 world 座標**
- 碰撞規則：`solid=1` 才阻擋
- 觸發規則：`trigger=1` 才觸發
- 技能規則：`swappable=1` 才能被 B/Y 交換
- 渲染規則：`visible=1` 且 `src_x/src_y/src_w/src_h` 指到 atlas 有效區域
- 類型判斷：用 `type` 做 dispatch

這樣之後要擴充（道具、傳送、對話、事件）都不用改資料格式。
