try:
    import ujson as json
except Exception:
    import json

import config


def _default_stage():
    width = 20
    height = 15
    tiles = []
    for y in range(height):
        row = [0] * width
        if y == height - 1:
            for x in range(width):
                row[x] = 1
        tiles.append(row)
    return {
        "width": width,
        "height": height,
        "tile_size": config.TILE_SIZE,
        "tile_layers": [tiles],
        "solid_tiles": [1],
        "player_spawn": {"x": 32, "y": 180},
        "enemy_spawns": [],
        "stage_goal": {"x": 280, "y": 176, "w": 16, "h": 32},
    }


def load_stage(path):
    try:
        with open(path, "r") as fp:
            stage = json.load(fp)
        if "tile_layers" not in stage:
            return _default_stage()
        return stage
    except Exception:
        return _default_stage()


def load_phase5_test_stage():
    width = 20
    height = 15
    tile_size = int(config.TILE_SIZE)

    tiles = []
    y = 0
    while y < height:
        tiles.append([0] * width)
        y += 1

    # Ground row for fall/landing checks.
    x = 0
    while x < width:
        tiles[height - 1][x] = 1
        x += 1

    # Mid platform for "walk off edge then fall" checks.
    x = 5
    while x <= 11:
        tiles[8][x] = 1
        x += 1

    # Right wall for horizontal collision checks.
    y = 6
    while y <= 13:
        tiles[y][12] = 1
        y += 1

    return {
        "width": width,
        "height": height,
        "tile_size": tile_size,
        "tile_layers": [tiles],
        "solid_tiles": [1],
        "player_spawn": {
            "x": 6 * tile_size,
            "y": (8 * tile_size) - 16,
        },
        "enemy_spawns": [],
        "stage_goal": {
            "x": 0,
            "y": 0,
            "w": 0,
            "h": 0,
        },
    }
