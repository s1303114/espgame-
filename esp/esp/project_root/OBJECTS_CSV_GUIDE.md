# 物件層說明（objects.csv）

本文件整理目前專案物件層主線，包含：

- `objects.csv` 欄位定義
- 世界座標與 tile 座標的換算
- `solid` / `trigger` / `swappable` / `gravity` / `checkpoint` 的用途
- `object_animations.json` 與 spawn sheet 的關係
- native object render buffer 的實際資料路徑

## 1. 為什麼要用 objects.csv

地形（tilemap）和物件（房子、草、重生石、箱子、裝飾）是兩個層次：

- 地形層：`map_tilemap.csv`
- 物件層：`objects.csv`

不要把所有物件烘成一張背景圖。物件應該獨立資料化，才好改位置、加事件、做碰撞、做觸發、做 swap。

## 2. 目前主線欄位格式

目前主線 `objects.csv` header 是：

```csv
id,type,world_x,world_y,w,h,sprite,solid,trigger,layer,swappable,src_x,src_y,src_w,src_h,gravity,anim_id,checkpoint
```

實例：

```csv
house,decor,16,32,64,112,house,0,0,1,0,0,0,64,112,0,,0
respawn_stone_01,checkpoint,128,112,32,32,respawn_stone,0,1,1,1,0,0,32,32,0,respawn_stone,1
grass,decor,224,112,32,32,grass,0,0,1,1,144,0,32,32,1,,0
```

欄位定義：

- `id`：唯一識別字串。
- `type`：邏輯分類，例如 `decor`、`checkpoint`。
- `world_x, world_y`：物件左上角的世界座標（像素）。
- `w, h`：邏輯尺寸與 AABB 尺寸（像素）。
- `sprite`：資源 key，主要做人工辨識與 metadata 對應。
- `solid`：`1/0`，是否阻擋玩家。
- `trigger`：`1/0`，是否作為觸發物件。
- `layer`：保留欄位，目前主線 object atlas 仍照資料順序處理。
- `swappable`：`1/0`，是否可被 B/Y swap 技能選中。
- `src_x, src_y, src_w, src_h`：此物件在 `object_altes_wire.rgb565` 裡的來源矩形。
- `gravity`：`1/0`，是否參與 object gravity 更新。
- `anim_id`：special overlay / animation key，例如 `respawn_stone`。
- `checkpoint`：`1/0`，是否視為重生點。

目前主線 **沒有 `visible` 欄位**。物件是否出現在畫面上，取決於：

- 這筆 row 是否被 loader 載入
- atlas 範圍是否合法
- 是否被 runtime 邏輯隱藏或 special overlay 取代
- 是否進入 camera 可視範圍

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

### 從 `map_tilemap.csv` 直接數

- 第一行第一格是 `(tile_x=0, tile_y=0)`
- 向右 `tile_x + 1`
- 向下 `tile_y + 1`

## 4. 捲動時如何顯示物件

物件儲存的是世界座標，每幀要轉成螢幕座標：

- `screen_x = world_x - camera_x`
- `screen_y = world_y - band_top`

如果物件超出螢幕可視範圍，native band compose 會直接 cull。

## 5. 目前渲染資料路徑

主線 object 渲染資源：

- CSV：`/sd/game/picture/object/objects.csv`
- atlas：`/sd/game/picture/object/object_altes_wire.rgb565`
- animations：`/sd/game/picture/object/object_animations.json`
- spawn sheets：
  - `/sd/game/picture/spawn/Spawnpoint_rock_wire.rgb565`
  - `/sd/game/picture/spawn/Resurrection_Anchor_wire.rgb565`
- atlas 尺寸：`OBJECTS_ATLAS_W = 256`、`OBJECTS_ATLAS_H = 256`
- byte order：panel wire-order，也就是每個 RGB565 pixel 以 `hi, lo` 存放

啟動時 Python 會：

1. 讀取 `objects.csv` 成 `objects_rows` 與 metadata。
2. 建立 `object_solids`，供玩家碰撞 / swap / gravity 使用。
3. 建立 `objects_c_buf`，供 C++ renderer 使用。
4. 載入 `object_altes_wire.rgb565`。
5. 載入 `object_animations.json`，讓 respawn stone / special overlay 可用。

## 6. Native object buffer

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

## 7. Special animation overlay

目前 object layer 支援 special animation overlay：

- 設定檔：`OBJECT_ANIMATIONS_JSON_PATH = "game/picture/object/object_animations.json"`
- `anim_id` 用來把 object row 對到 overlay 動畫，例如 `respawn_stone`
- spawn 相關圖像不在 object atlas，而是在 `/sd/game/picture/spawn/*.rgb565`
- Python 會依 object metadata、respawn anchor、enemy bullet 等狀態打包 overlay descriptor
- native band pipeline 會在基礎 object atlas 後、player sprite 前繪製 overlay

因此 respawn stone 這類物件不是只靠 `object_altes_wire.rgb565`；若 `object_animations.json` 或 `picture/spawn/*.rgb565` 缺失，物件本體可能載入了，但畫面仍不會正常顯示。

## 8. `solid`、`trigger`、`swappable`、`gravity`、`checkpoint`

- `solid=1`：會擋住玩家（碰撞阻擋）
- `trigger=1`：作為觸發物件
- `swappable=1`：可被 B/Y 交換技能選中
- `gravity=1`：會參與 object gravity 更新
- `checkpoint=1`：視為重生點邏輯物件

常見組合：

- 場景裝飾：`solid=0 trigger=0 swappable=0/1 gravity=0`
- 可交換裝飾：`solid=0 trigger=0 swappable=1 gravity=0`
- 會落下的裝飾：`solid=0 trigger=0 swappable=1 gravity=1`
- 重生石：`type=checkpoint trigger=1 checkpoint=1 anim_id=respawn_stone`

## 9. 放置物件的實務流程（推薦）

1. 先在 `map_tilemap.csv` 找 tile 位置
2. 換算成 `world_x, world_y`
3. 填入 `objects.csv`
4. 確認 `src_x/src_y/src_w/src_h` 指向 atlas 或 special animation 資源
5. 若是重生石或其他 special object，再確認 `object_animations.json` 與 spawn sheet 已部署
6. 上板 reset 測試

若要貼地：

- `object_world_y = tile_y * 16 - object_h`

## 10. 常見錯誤

- 把 `world_x,world_y` 當成螢幕座標
- `objects.csv` 已部署，但沒有 reset
- `config.py` 指向錯的 tilemap CSV 或資產路徑
- `object_animations.json` 缺失，導致重生石不顯示
- `picture/spawn/*.rgb565` 缺失，導致 special overlay 不顯示
- `src_x/src_y/src_w/src_h` 超出 atlas 範圍，C++ 會跳過該物件
- atlas 不是 wire-order，導致顏色錯或 colorkey 失效
- 以為 `fs cp` 成功就代表 SD 更新成功，卻沒有做 `umount -> mount -> readback`

## 11. 最小可用結論

若你要先快速上線：

- 座標基準統一：**左上角 world 座標**
- 碰撞規則：`solid=1` 才阻擋
- 觸發規則：`trigger=1` 才觸發
- 技能規則：`swappable=1` 才能被 B/Y 交換
- 特效規則：`anim_id` + `object_animations.json` + `picture/spawn/*.rgb565` 一起決定 special object 顯示
- 渲染規則：`src_x/src_y/src_w/src_h` 要指到 atlas 有效區域，且所有 `.rgb565` 資產都必須是 wire-order

這樣之後要擴充裝飾、重生點、觸發事件、可交換物件，都不用再改資料格式。
