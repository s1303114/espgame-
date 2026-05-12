class EntityManager:
    __slots__ = ("entities", "count", "max_entities", "bullet_pool")

    def __init__(self, max_entities):
        self.max_entities = int(max_entities)
        self.entities = [None] * self.max_entities
        self.count = 0
        self.bullet_pool = None

    def set_bullet_pool(self, bullet_pool):
        self.bullet_pool = bullet_pool

    def add(self, ent):
        if self.count >= self.max_entities:
            return False
        self.entities[self.count] = ent
        self.count += 1
        return True

    def spawn_enemy(self, ent):
        return self.add(ent)

    def update_all(self, now_ms, stage_data, step_entity_cb):
        i = 0
        while i < self.count:
            ent = self.entities[i]
            if ent is not None and ent.active:
                ent.update(now_ms, stage_data, self.bullet_pool)
                if ent.active and step_entity_cb is not None:
                    step_entity_cb(ent, stage_data)
            i += 1

        if self.bullet_pool is not None:
            self.bullet_pool.update_all(now_ms, stage_data)

    def draw_all(self, renderer_mod):
        i = 0
        while i < self.count:
            ent = self.entities[i]
            if ent is not None and ent.active and ent.visible:
                renderer_mod.draw_enemy(ent)
            i += 1

        if self.bullet_pool is not None:
            self.bullet_pool.draw_all(renderer_mod)

    def get_active_entities(self):
        return self.entities, self.count

    def get_skill_query_sources(self):
        return self.entities, self.count, self.bullet_pool

    def cleanup(self):
        self.remove_inactive()

    def remove_inactive(self):
        write_idx = 0
        for i in range(self.count):
            ent = self.entities[i]
            if ent is not None and ent.active:
                self.entities[write_idx] = ent
                write_idx += 1
        for i in range(write_idx, self.count):
            self.entities[i] = None
        self.count = write_idx
