#include "lgfx_world.hpp"

#include <stddef.h>

#include "lgfx_game.hpp"

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
) {
    if (w <= 0 || h <= 0 || view_w <= 0 || view_h <= 0) {
        return false;
    }
    int32_t left = wx;
    int32_t top = wy;
    int32_t right = left + w;
    int32_t bottom = top + h;
    int32_t view_left = camera_x - margin_x;
    int32_t view_top = -margin_y;
    int32_t view_right = camera_x + view_w + margin_x;
    int32_t view_bottom = view_h + margin_y;
    return left < view_right && right > view_left && top < view_bottom && bottom > view_top;
}

bool lgfx_tilemap_is_solid(const uint8_t *tilemap, int32_t map_w, int32_t map_h, int32_t tx, int32_t ty) {
    if (!tilemap || tx < 0 || ty < 0 || tx >= map_w || ty >= map_h) {
        return false;
    }
    return tilemap[(size_t)ty * (size_t)map_w + (size_t)tx] != 0u;
}

bool lgfx_aabb_collides_tilemap(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h
) {
    if (!tilemap || map_w <= 0 || map_h <= 0 || tile_size <= 0 || w <= 0 || h <= 0) {
        return false;
    }
    int32_t left = x / tile_size;
    int32_t right = (x + w - 1) / tile_size;
    int32_t top = y / tile_size;
    int32_t bottom = (y + h - 1) / tile_size;
    if (x < 0 && (x % tile_size)) {
        left -= 1;
    }
    if (y < 0 && (y % tile_size)) {
        top -= 1;
    }
    for (int32_t ty = top; ty <= bottom; ++ty) {
        for (int32_t tx = left; tx <= right; ++tx) {
            if (lgfx_tilemap_is_solid(tilemap, map_w, map_h, tx, ty)) {
                return true;
            }
        }
    }
    return false;
}

bool lgfx_aabb_collides_solids(
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph
) {
    if (!solids || solid_stride < LGFX_OBJECT_SOLID_STRIDE || solid_count <= 0 || pw <= 0 || ph <= 0) {
        return false;
    }
    int32_t p_right = px + pw;
    int32_t p_bottom = py + ph;
    for (int32_t i = 0; i < solid_count; ++i) {
        const uint8_t *sb = solids + ((size_t)i * (size_t)solid_stride);
        int32_t ox = lgfx_rd_i16(sb + 0);
        int32_t oy = lgfx_rd_i16(sb + 2);
        int32_t ow = lgfx_rd_i16(sb + 4);
        int32_t oh = lgfx_rd_i16(sb + 6);
        if (ow <= 0 || oh <= 0) {
            continue;
        }
        if (px < (ox + ow) && p_right > ox && py < (oy + oh) && p_bottom > oy) {
            return true;
        }
    }
    return false;
}

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
) {
    if (lgfx_aabb_collides_tilemap(tilemap, map_w, map_h, tile_size, px, py, pw, ph)) {
        return true;
    }
    if (lgfx_aabb_collides_solids(solids, solid_stride, solid_count, px, py, pw, ph)) {
        return true;
    }
    return false;
}

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
) {
    bool local_hit_x = false;
    bool local_hit_y = false;
    int32_t nx = px;
    int32_t ny = py;
    int32_t sx = (dx > 0) ? 1 : -1;
    int32_t sy = (dy > 0) ? 1 : -1;
    int32_t ax = (dx >= 0) ? dx : -dx;
    int32_t ay = (dy >= 0) ? dy : -dy;

    while (ax > 0) {
        int32_t tx = nx + sx;
        if (lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, tx, ny, pw, ph)) {
            local_hit_x = true;
            break;
        }
        nx = tx;
        ax -= 1;
    }
    while (ay > 0) {
        int32_t ty = ny + sy;
        if (lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, nx, ty, pw, ph)) {
            local_hit_y = true;
            break;
        }
        ny = ty;
        ay -= 1;
    }

    *out_x = nx;
    *out_y = ny;
    *hit_x = local_hit_x;
    *hit_y = local_hit_y;
}

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
) {
    int32_t step = step_px < 1 ? 1 : step_px;
    int32_t probe_x = (direction >= 0) ? (wx + ow + step - 2) : (wx - step);
    int32_t probe_y = wy + oh + 1;
    return lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, probe_x, probe_y, 2, 2);
}