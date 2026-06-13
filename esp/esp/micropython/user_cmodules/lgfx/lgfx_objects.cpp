#if !defined(NO_QSTR)

#include <stddef.h>
#include <stdint.h>

extern "C" {
#include "py/obj.h"
#include "py/runtime.h"
}

#include "lgfx_game.hpp"
#include "lgfx_shared.hpp"
#include "lgfx_world.hpp"

static void lgfx_write_object_render_row(uint8_t *objects, int32_t object_stride, int32_t object_count, int32_t index, const uint8_t *state) {
    if (!objects || !state || object_stride < LGFX_OBJECT_RENDER_STRIDE || index < 0 || index >= object_count) {
        return;
    }
    uint8_t *dst = objects + ((size_t)index * (size_t)object_stride);
    uint16_t flags = (uint16_t)lgfx_rd_i16(state + 16);
    bool visible = (flags & LGFX_OBJECT_STATE_FLAG_VISIBLE) != 0;
    bool special = (flags & LGFX_OBJECT_STATE_FLAG_SPECIAL_RENDER) != 0;
    int32_t sx = visible && !special ? lgfx_rd_i16(state + 8) : 0;
    int32_t sy = visible && !special ? lgfx_rd_i16(state + 10) : 0;
    int32_t sw = visible && !special ? lgfx_rd_i16(state + 12) : 0;
    int32_t sh = visible && !special ? lgfx_rd_i16(state + 14) : 0;
    lgfx_wr_i16(dst + 0, lgfx_rd_i16(state + 0));
    lgfx_wr_i16(dst + 2, lgfx_rd_i16(state + 2));
    lgfx_wr_i16(dst + 4, sx);
    lgfx_wr_i16(dst + 6, sy);
    lgfx_wr_i16(dst + 8, sw);
    lgfx_wr_i16(dst + 10, sh);
}

static int32_t lgfx_rebuild_object_solids_from_state(
    const uint8_t *object_states,
    int32_t object_state_stride,
    int32_t object_count,
    uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_capacity
) {
    if (!object_states || !solids || object_state_stride < LGFX_OBJECT_STATE_STRIDE || solid_stride < LGFX_OBJECT_SOLID_STRIDE || object_count <= 0 || solid_capacity <= 0) {
        return 0;
    }
    int32_t out_count = 0;
    for (int32_t i = 0; i < object_count && out_count < solid_capacity; ++i) {
        const uint8_t *row = object_states + ((size_t)i * (size_t)object_state_stride);
        uint16_t flags = (uint16_t)lgfx_rd_i16(row + 16);
        if (((flags & LGFX_OBJECT_STATE_FLAG_VISIBLE) == 0) || ((flags & LGFX_OBJECT_STATE_FLAG_SOLID) == 0)) {
            continue;
        }
        int32_t w = lgfx_rd_i16(row + 4);
        int32_t h = lgfx_rd_i16(row + 6);
        if (w <= 0 || h <= 0) {
            continue;
        }
        uint8_t *dst = solids + ((size_t)out_count * (size_t)solid_stride);
        lgfx_wr_i16(dst + 0, lgfx_rd_i16(row + 0));
        lgfx_wr_i16(dst + 2, lgfx_rd_i16(row + 2));
        lgfx_wr_i16(dst + 4, w);
        lgfx_wr_i16(dst + 6, h);
        ++out_count;
    }
    for (int32_t i = out_count; i < solid_capacity; ++i) {
        uint8_t *dst = solids + ((size_t)i * (size_t)solid_stride);
        lgfx_wr_i16(dst + 0, 0);
        lgfx_wr_i16(dst + 2, 0);
        lgfx_wr_i16(dst + 4, 0);
        lgfx_wr_i16(dst + 6, 0);
    }
    return out_count;
}

static mp_obj_t lgfx_update_objects_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 21) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 21 args"));
    }
    mp_buffer_info_t object_state_info;
    mp_buffer_info_t objects_info;
    mp_buffer_info_t solids_info;
    mp_buffer_info_t tilemap_info;
    mp_get_buffer_raise(args[0], &object_state_info, MP_BUFFER_RW);
    mp_int_t object_state_stride = mp_obj_get_int(args[1]);
    mp_int_t object_count = mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &objects_info, MP_BUFFER_RW);
    mp_int_t object_stride = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &solids_info, MP_BUFFER_RW);
    mp_int_t solid_stride = mp_obj_get_int(args[6]);
    mp_int_t solid_capacity = mp_obj_get_int(args[7]);
    mp_get_buffer_raise(args[8], &tilemap_info, MP_BUFFER_READ);
    mp_int_t tilemap_w = mp_obj_get_int(args[9]);
    mp_int_t tilemap_h = mp_obj_get_int(args[10]);
    mp_int_t tile_size = mp_obj_get_int(args[11]);
    bool gravity_enabled = mp_obj_is_true(args[12]);
    mp_int_t gravity_step = mp_obj_get_int(args[13]);
    mp_int_t map_h_px = mp_obj_get_int(args[14]);
    mp_int_t death_margin = mp_obj_get_int(args[15]);
    mp_int_t camera_x = mp_obj_get_int(args[16]);
    mp_int_t view_w = mp_obj_get_int(args[17]);
    mp_int_t view_h = mp_obj_get_int(args[18]);
    mp_int_t margin_x = mp_obj_get_int(args[19]);
    mp_int_t margin_y = mp_obj_get_int(args[20]);

    if (object_state_stride < LGFX_OBJECT_STATE_STRIDE || object_stride < LGFX_OBJECT_RENDER_STRIDE || solid_stride < LGFX_OBJECT_SOLID_STRIDE) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid object stride"));
    }
    if (object_count < 0 || solid_capacity < 0 || tilemap_w <= 0 || tilemap_h <= 0 || tile_size <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid object dims"));
    }
    if (object_state_info.len < (size_t)object_state_stride * (size_t)object_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("object state buf too small"));
    }
    if (objects_info.len < (size_t)object_stride * (size_t)object_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("object render buf too small"));
    }
    if (solids_info.len < (size_t)solid_stride * (size_t)solid_capacity) {
        mp_raise_ValueError(MP_ERROR_TEXT("object solid buf too small"));
    }
    if (tilemap_info.len < (size_t)tilemap_w * (size_t)tilemap_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
    }

    uint8_t *object_states = (uint8_t *)object_state_info.buf;
    uint8_t *objects = (uint8_t *)objects_info.buf;
    uint8_t *solids = (uint8_t *)solids_info.buf;
    const uint8_t *tilemap = (const uint8_t *)tilemap_info.buf;
    int32_t moved_count = 0;

    if (gravity_enabled && gravity_step > 0) {
        for (int32_t oi = 0; oi < object_count; ++oi) {
            uint8_t *row = object_states + ((size_t)oi * (size_t)object_state_stride);
            uint16_t flags = (uint16_t)lgfx_rd_i16(row + 16);
            if (((flags & LGFX_OBJECT_STATE_FLAG_VISIBLE) == 0) || ((flags & LGFX_OBJECT_STATE_FLAG_GRAVITY) == 0)) {
                continue;
            }
            int32_t x = lgfx_rd_i16(row + 0);
            int32_t y = lgfx_rd_i16(row + 2);
            int32_t w = lgfx_rd_i16(row + 4);
            int32_t h = lgfx_rd_i16(row + 6);
            if (w <= 0 || h <= 0) {
                continue;
            }
            if (!lgfx_aabb_near_view(x, y, w, h, camera_x, view_w, view_h, margin_x, margin_y)) {
                continue;
            }
            int32_t steps = gravity_step;
            int32_t moved_y = 0;
            bool removed = false;
            while (steps > 0) {
                int32_t ny = y + 1;
                if (lgfx_aabb_collides_tilemap(tilemap, tilemap_w, tilemap_h, tile_size, x, ny, w, h)) {
                    break;
                }
                y = ny;
                ++moved_y;
                if (y > (map_h_px + death_margin)) {
                    removed = true;
                    break;
                }
                --steps;
            }
            if (removed) {
                flags &= (uint16_t)~LGFX_OBJECT_STATE_FLAG_VISIBLE;
                lgfx_wr_i16(row + 2, y);
                lgfx_wr_i16(row + 16, (int16_t)flags);
                lgfx_write_object_render_row(objects, object_stride, object_count, oi, row);
                ++moved_count;
            } else if (moved_y > 0) {
                lgfx_wr_i16(row + 2, y);
                lgfx_write_object_render_row(objects, object_stride, object_count, oi, row);
                ++moved_count;
            }
        }
    }

    int32_t solid_count = lgfx_rebuild_object_solids_from_state(object_states, object_state_stride, object_count, solids, solid_stride, solid_capacity);
    mp_obj_t out[2] = {
        mp_obj_new_int(moved_count),
        mp_obj_new_int(solid_count),
    };
    return mp_obj_new_tuple(2, out);
}

MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_objects_native_obj, 21, 21, lgfx_update_objects_native);

#endif
