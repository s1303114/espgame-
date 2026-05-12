class GameState:
    __slots__ = (
        "hp",
        "max_hp",
        "debug_enabled",
        "fps",
        "player_x",
        "player_y",
        "entity_count",
        "camera_x",
        "camera_y",
        "needs_redraw",
        "last_redraw_ms",
    )

    def __init__(self):
        self.hp = 5
        self.max_hp = 5
        self.debug_enabled = True
        self.fps = 0
        self.player_x = 0
        self.player_y = 0
        self.entity_count = 0
        self.camera_x = 0
        self.camera_y = 0
        self.needs_redraw = True
        self.last_redraw_ms = 0
