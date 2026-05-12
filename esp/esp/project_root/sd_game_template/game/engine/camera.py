class Camera:
    __slots__ = ("x", "y", "view_w", "view_h", "world_w", "world_h")

    def __init__(self, view_w, view_h, world_w, world_h):
        self.x = 0
        self.y = 0
        self.view_w = int(view_w)
        self.view_h = int(view_h)
        self.world_w = int(world_w)
        self.world_h = int(world_h)

    def _clamp(self):
        max_x = self.world_w - self.view_w
        max_y = self.world_h - self.view_h
        if max_x < 0:
            max_x = 0
        if max_y < 0:
            max_y = 0

        if self.x < 0:
            self.x = 0
        elif self.x > max_x:
            self.x = max_x

        if self.y < 0:
            self.y = 0
        elif self.y > max_y:
            self.y = max_y

    def follow(self, target_x, target_y):
        self.x = int(target_x) - (self.view_w // 2)
        self.y = int(target_y) - (self.view_h // 2)
        self._clamp()
