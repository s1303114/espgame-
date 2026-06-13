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

static void lgfx_wr_i32(uint8_t *buf, size_t index, int32_t value) {
    size_t off = index * 4u;
    uint32_t uv = (uint32_t)value;
    buf[off + 0] = (uint8_t)(uv & 0xffu);
    buf[off + 1] = (uint8_t)((uv >> 8) & 0xffu);
    buf[off + 2] = (uint8_t)((uv >> 16) & 0xffu);
    buf[off + 3] = (uint8_t)((uv >> 24) & 0xffu);
}

static void lgfx_write_player_result(
    uint8_t *result,
    int32_t player_x,
    int32_t player_y,
    int32_t vel_y,
    bool grounded,
    bool hit_x,
    bool hit_y,
    int32_t unembed_steps,
    int32_t flags
) {
    lgfx_wr_i32(result, 0, player_x);
    lgfx_wr_i32(result, 1, player_y);
    lgfx_wr_i32(result, 2, vel_y);
    lgfx_wr_i32(result, 3, grounded ? 1 : 0);
    lgfx_wr_i32(result, 4, hit_x ? 1 : 0);
    lgfx_wr_i32(result, 5, hit_y ? 1 : 0);
    lgfx_wr_i32(result, 6, unembed_steps);
    lgfx_wr_i32(result, 7, flags);
}

static mp_obj_t lgfx_update_player_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 17) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 17 args"));
    }

    const uint8_t *tilemap = nullptr;
    mp_buffer_info_t tilemap_info;
    int32_t tilemap_w = (int32_t)mp_obj_get_int(args[1]);
    int32_t tilemap_h = (int32_t)mp_obj_get_int(args[2]);
    int32_t tile_size = (int32_t)mp_obj_get_int(args[3]);
    if (args[0] != mp_const_none) {
        mp_get_buffer_raise(args[0], &tilemap_info, MP_BUFFER_READ);
        if (tilemap_w <= 0 || tilemap_h <= 0 || tile_size <= 0) {
            mp_raise_ValueError(MP_ERROR_TEXT("invalid tilemap dims"));
        }
        if (tilemap_info.len < (size_t)tilemap_w * (size_t)tilemap_h) {
            mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
        }
        tilemap = (const uint8_t *)tilemap_info.buf;
    } else {
        tilemap_w = 0;
        tilemap_h = 0;
    }

    const uint8_t *solids = nullptr;
    mp_buffer_info_t solids_info;
    int32_t solid_stride = (int32_t)mp_obj_get_int(args[5]);
    int32_t solid_count = (int32_t)mp_obj_get_int(args[6]);
    if (solid_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid solid count"));
    }
    if (args[4] != mp_const_none && solid_count > 0) {
        mp_get_buffer_raise(args[4], &solids_info, MP_BUFFER_READ);
        if (solid_stride < LGFX_OBJECT_SOLID_STRIDE) {
            mp_raise_ValueError(MP_ERROR_TEXT("invalid solid stride"));
        }
        if (solids_info.len < (size_t)solid_stride * (size_t)solid_count) {
            mp_raise_ValueError(MP_ERROR_TEXT("solid buf too small"));
        }
        solids = (const uint8_t *)solids_info.buf;
    } else {
        solid_count = 0;
        solid_stride = LGFX_OBJECT_SOLID_STRIDE;
    }

    int32_t player_x = (int32_t)mp_obj_get_int(args[7]);
    int32_t player_y = (int32_t)mp_obj_get_int(args[8]);
    int32_t player_w = (int32_t)mp_obj_get_int(args[9]);
    int32_t player_h = (int32_t)mp_obj_get_int(args[10]);
    int32_t move_x = (int32_t)mp_obj_get_int(args[11]);
    int32_t vel_y = (int32_t)mp_obj_get_int(args[12]);
    int32_t gravity = (int32_t)mp_obj_get_int(args[13]);
    int32_t fall_speed_max = (int32_t)mp_obj_get_int(args[14]);
    int32_t max_player_x = (int32_t)mp_obj_get_int(args[15]);

    mp_buffer_info_t result_info;
    mp_get_buffer_raise(args[16], &result_info, MP_BUFFER_WRITE);
    if (result_info.len < 32u) {
        mp_raise_ValueError(MP_ERROR_TEXT("player result buf too small"));
    }
    if (player_w <= 0 || player_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid player size"));
    }
    if (fall_speed_max < 1) {
        fall_speed_max = 1;
    }
    if (gravity < 0) {
        gravity = 0;
    }
    if (max_player_x < 0) {
        max_player_x = 0;
    }

    bool grounded = false;
    bool hit_x = false;
    bool hit_y = false;
    int32_t unembed_steps = 0;
    bool has_world = (tilemap != nullptr && tilemap_w > 0 && tilemap_h > 0 && tile_size > 0) || (solids != nullptr && solid_count > 0);

    if (has_world) {
        int32_t unembed_guard = tile_size * 4;
        if (unembed_guard < 16) {
            unembed_guard = 16;
        }
        while (unembed_guard > 0 && lgfx_aabb_collides_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, player_x, player_y, player_w, player_h)) {
            player_y -= 1;
            unembed_steps += 1;
            if (player_y < 0) {
                player_y = 0;
                break;
            }
            unembed_guard -= 1;
        }

        grounded = lgfx_aabb_collides_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, player_x, player_y + 1, player_w, player_h);
        if (!grounded) {
            vel_y += gravity;
            if (vel_y > fall_speed_max) {
                vel_y = fall_speed_max;
            }
        } else if (vel_y > 0) {
            vel_y = 0;
        }

        int32_t moved_x = player_x;
        int32_t moved_y = player_y;
        lgfx_move_axis_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, player_x, player_y, player_w, player_h, move_x, vel_y, &moved_x, &moved_y, &hit_x, &hit_y);
        player_x = moved_x;
        player_y = moved_y;
        if (hit_y) {
            vel_y = 0;
        }
        player_x = lgfx_clamp_i32(player_x, 0, max_player_x);
        if (player_y < 0) {
            player_y = 0;
            vel_y = 0;
        }
    } else {
        player_x = lgfx_clamp_i32(player_x + move_x, 0, max_player_x);
    }

    lgfx_write_player_result((uint8_t *)result_info.buf, player_x, player_y, vel_y, grounded, hit_x, hit_y, unembed_steps, 1);
    return mp_const_true;
}

MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_player_native_obj, 17, 17, lgfx_update_player_native);

#endif