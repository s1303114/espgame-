#pragma once

#include <stdint.h>

bool lgfx_aabb_near_view(
    int32_t wx,
    int32_t wy,
    int32_t w,
    int32_t h,
    int32_t camera_x,
    int32_t view_w,
    int32_t view_h,
    int32_t margin_x,
    int32_t margin_y
);

bool lgfx_tilemap_is_solid(const uint8_t *tilemap, int32_t map_w, int32_t map_h, int32_t tx, int32_t ty);

bool lgfx_aabb_collides_tilemap(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h
);

bool lgfx_aabb_collides_solids(
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph
);

bool lgfx_aabb_collides_world(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph
);

void lgfx_move_axis_world(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph,
    int32_t dx,
    int32_t dy,
    int32_t *out_x,
    int32_t *out_y,
    bool *hit_x,
    bool *hit_y
);

bool lgfx_enemy_has_support_ahead(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t wx,
    int32_t wy,
    int32_t ow,
    int32_t oh,
    int32_t direction,
    int32_t step_px
);