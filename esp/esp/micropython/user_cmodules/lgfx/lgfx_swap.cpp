#if !defined(NO_QSTR)

#include <stddef.h>
#include <stdint.h>

extern "C" {
#include "py/obj.h"
#include "py/runtime.h"
}

#include "lgfx_game.hpp"
#include "lgfx_shared.hpp"

static constexpr int32_t kSwapTargetObject = 1;
static constexpr int32_t kSwapTargetEnemy = 2;
static constexpr int32_t kSwapTargetBullet = 3;

static int32_t lgfx_floor_div2(int32_t value) {
    if (value >= 0) {
        return value / 2;
    }
    return -(((-value) + 1) / 2);
}

static void lgfx_wr_i32(uint8_t *buf, size_t index, int32_t value) {
    size_t off = index * 4u;
    uint32_t uv = (uint32_t)value;
    buf[off + 0] = (uint8_t)(uv & 0xffu);
    buf[off + 1] = (uint8_t)((uv >> 8) & 0xffu);
    buf[off + 2] = (uint8_t)((uv >> 16) & 0xffu);
    buf[off + 3] = (uint8_t)((uv >> 24) & 0xffu);
}

static void lgfx_write_swap_result(
    uint8_t *result,
    int32_t ok,
    int32_t target_kind,
    int32_t target_index,
    int32_t player_x,
    int32_t player_y,
    int32_t vel_y,
    int32_t object_solid_count,
    int32_t changed_object_index,
    int32_t changed_enemy_index,
    int32_t changed_bullet_index,
    int32_t flags
) {
    lgfx_wr_i32(result, 0, ok);
    lgfx_wr_i32(result, 1, target_kind);
    lgfx_wr_i32(result, 2, target_index);
    lgfx_wr_i32(result, 3, player_x);
    lgfx_wr_i32(result, 4, player_y);
    lgfx_wr_i32(result, 5, vel_y);
    lgfx_wr_i32(result, 6, object_solid_count);
    lgfx_wr_i32(result, 7, changed_object_index);
    lgfx_wr_i32(result, 8, changed_enemy_index);
    lgfx_wr_i32(result, 9, changed_bullet_index);
    lgfx_wr_i32(result, 10, flags);
    lgfx_wr_i32(result, 11, 0);
}

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

static mp_obj_t lgfx_perform_swap_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 25) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 25 args"));
    }

    int32_t target_kind = (int32_t)mp_obj_get_int(args[0]);
    int32_t target_index = (int32_t)mp_obj_get_int(args[1]);
    int32_t player_x = (int32_t)mp_obj_get_int(args[2]);
    int32_t player_y = (int32_t)mp_obj_get_int(args[3]);
    int32_t player_w = (int32_t)mp_obj_get_int(args[4]);
    int32_t player_h = (int32_t)mp_obj_get_int(args[5]);
    int32_t max_player_x = (int32_t)mp_obj_get_int(args[6]);
    int32_t map_h_px = (int32_t)mp_obj_get_int(args[7]);

    mp_buffer_info_t object_state_info;
    mp_buffer_info_t objects_info;
    mp_buffer_info_t solids_info;
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t enemy_states_info;
    mp_buffer_info_t bullets_info;
    mp_buffer_info_t result_info;

    mp_get_buffer_raise(args[8], &object_state_info, MP_BUFFER_RW);
    int32_t object_state_stride = (int32_t)mp_obj_get_int(args[9]);
    int32_t object_count = (int32_t)mp_obj_get_int(args[10]);
    mp_get_buffer_raise(args[11], &objects_info, MP_BUFFER_RW);
    int32_t object_stride = (int32_t)mp_obj_get_int(args[12]);
    mp_get_buffer_raise(args[13], &solids_info, MP_BUFFER_RW);
    int32_t solid_stride = (int32_t)mp_obj_get_int(args[14]);
    int32_t solid_capacity = (int32_t)mp_obj_get_int(args[15]);
    mp_get_buffer_raise(args[16], &enemy_rows_info, MP_BUFFER_RW);
    int32_t enemy_row_stride = (int32_t)mp_obj_get_int(args[17]);
    int32_t enemy_count = (int32_t)mp_obj_get_int(args[18]);
    mp_get_buffer_raise(args[19], &enemy_states_info, MP_BUFFER_RW);
    int32_t enemy_state_stride = (int32_t)mp_obj_get_int(args[20]);
    mp_get_buffer_raise(args[21], &bullets_info, MP_BUFFER_RW);
    int32_t bullet_stride = (int32_t)mp_obj_get_int(args[22]);
    int32_t bullet_count = (int32_t)mp_obj_get_int(args[23]);
    mp_get_buffer_raise(args[24], &result_info, MP_BUFFER_WRITE);

    if (result_info.len < 48u) {
        mp_raise_ValueError(MP_ERROR_TEXT("swap result buf too small"));
    }
    uint8_t *result = (uint8_t *)result_info.buf;
    lgfx_write_swap_result(result, 0, target_kind, target_index, player_x, player_y, 0, 0, -1, -1, -1, 0);

    if (target_index < 0 || player_w <= 0 || player_h <= 0) {
        return mp_const_false;
    }
    if (max_player_x < 0) {
        max_player_x = 0;
    }
    int32_t max_player_y = map_h_px - player_h;
    if (max_player_y < 0) {
        max_player_y = 0;
    }

    uint8_t *object_states = (uint8_t *)object_state_info.buf;
    uint8_t *objects = (uint8_t *)objects_info.buf;
    uint8_t *solids = (uint8_t *)solids_info.buf;
    uint8_t *enemy_rows = (uint8_t *)enemy_rows_info.buf;
    uint8_t *enemy_states = (uint8_t *)enemy_states_info.buf;
    uint8_t *bullets = (uint8_t *)bullets_info.buf;

    if (target_kind == kSwapTargetObject) {
        if (object_state_stride < LGFX_OBJECT_STATE_STRIDE || object_stride < LGFX_OBJECT_RENDER_STRIDE || solid_stride < LGFX_OBJECT_SOLID_STRIDE) {
            mp_raise_ValueError(MP_ERROR_TEXT("invalid object swap stride"));
        }
        if (object_count < 0 || target_index >= object_count || solid_capacity < 0) {
            return mp_const_false;
        }
        if (object_state_info.len < (size_t)object_state_stride * (size_t)object_count || objects_info.len < (size_t)object_stride * (size_t)object_count || solids_info.len < (size_t)solid_stride * (size_t)solid_capacity) {
            mp_raise_ValueError(MP_ERROR_TEXT("object swap buf too small"));
        }
        uint8_t *row = object_states + ((size_t)target_index * (size_t)object_state_stride);
        uint16_t flags = (uint16_t)lgfx_rd_i16(row + 16);
        if (((flags & LGFX_OBJECT_STATE_FLAG_VISIBLE) == 0) || ((flags & LGFX_OBJECT_STATE_FLAG_SWAPPABLE) == 0)) {
            return mp_const_false;
        }
        int32_t old_px = player_x;
        int32_t old_py = player_y;
        int32_t old_ox = lgfx_rd_i16(row + 0);
        int32_t old_oy = lgfx_rd_i16(row + 2);
        int32_t obj_w = lgfx_rd_i16(row + 4);
        int32_t obj_h = lgfx_rd_i16(row + 6);
        if (obj_w <= 0 || obj_h <= 0) {
            return mp_const_false;
        }
        player_x = old_ox + lgfx_floor_div2(obj_w - player_w);
        player_y = old_oy + (obj_h - player_h);
        int32_t new_ox = old_px + lgfx_floor_div2(player_w - obj_w);
        int32_t new_oy = old_py + (player_h - obj_h);
        player_x = lgfx_clamp_i32(player_x, 0, max_player_x);
        player_y = lgfx_clamp_i32(player_y, 0, max_player_y);
        lgfx_wr_i16(row + 0, new_ox);
        lgfx_wr_i16(row + 2, new_oy);
        lgfx_write_object_render_row(objects, object_stride, object_count, target_index, row);
        int32_t solid_count = lgfx_rebuild_object_solids_from_state(object_states, object_state_stride, object_count, solids, solid_stride, solid_capacity);
        lgfx_write_swap_result(result, 1, target_kind, target_index, player_x, player_y, 0, solid_count, target_index, -1, -1, 1);
        return mp_const_true;
    }

    if (target_kind == kSwapTargetEnemy) {
        if (enemy_row_stride < LGFX_ENEMY_ROW_STRIDE || enemy_state_stride < LGFX_ENEMY_STATE_STRIDE || bullet_stride < LGFX_BULLET_STRIDE) {
            mp_raise_ValueError(MP_ERROR_TEXT("invalid enemy swap stride"));
        }
        if (enemy_count < 0 || target_index >= enemy_count || bullet_count < 0) {
            return mp_const_false;
        }
        if (enemy_rows_info.len < (size_t)enemy_row_stride * (size_t)enemy_count || enemy_states_info.len < (size_t)enemy_state_stride * (size_t)enemy_count || bullets_info.len < (size_t)bullet_stride * (size_t)bullet_count) {
            mp_raise_ValueError(MP_ERROR_TEXT("enemy swap buf too small"));
        }
        uint8_t *row = enemy_rows + ((size_t)target_index * (size_t)enemy_row_stride);
        if (row[8] == 0 || row[9] == 0) {
            return mp_const_false;
        }
        int32_t old_px = player_x;
        int32_t old_py = player_y;
        int32_t old_ex = lgfx_rd_i16(row + 0);
        int32_t old_ey = lgfx_rd_i16(row + 2);
        int32_t enemy_w = lgfx_rd_i16(row + 4);
        int32_t enemy_h = lgfx_rd_i16(row + 6);
        if (enemy_w <= 0 || enemy_h <= 0) {
            return mp_const_false;
        }
        player_x = old_ex + lgfx_floor_div2(enemy_w - player_w);
        player_y = old_ey + (enemy_h - player_h);
        int32_t new_ex = old_px + lgfx_floor_div2(player_w - enemy_w);
        int32_t new_ey = old_py + (player_h - enemy_h);
        player_x = lgfx_clamp_i32(player_x, 0, max_player_x);
        player_y = lgfx_clamp_i32(player_y, 0, max_player_y);
        lgfx_wr_i16(row + 0, new_ex);
        lgfx_wr_i16(row + 2, new_ey);
        uint8_t *state = enemy_states + ((size_t)target_index * (size_t)enemy_state_stride);
        state[7] = 0;
        for (int32_t bi = 0; bi < bullet_count; ++bi) {
            uint8_t *bullet = bullets + ((size_t)bi * (size_t)bullet_stride);
            if (lgfx_rd_i16(bullet + 14) == target_index) {
                lgfx_wr_i16(bullet + 14, -1);
            }
        }
        lgfx_write_swap_result(result, 1, target_kind, target_index, player_x, player_y, 0, -1, -1, target_index, -1, 2);
        return mp_const_true;
    }

    if (target_kind == kSwapTargetBullet) {
        if (bullet_stride < LGFX_BULLET_STRIDE) {
            mp_raise_ValueError(MP_ERROR_TEXT("invalid bullet swap stride"));
        }
        if (bullet_count < 0 || target_index >= bullet_count) {
            return mp_const_false;
        }
        if (bullets_info.len < (size_t)bullet_stride * (size_t)bullet_count) {
            mp_raise_ValueError(MP_ERROR_TEXT("bullet swap buf too small"));
        }
        uint8_t *row = bullets + ((size_t)target_index * (size_t)bullet_stride);
        if (lgfx_rd_i16(row + 12) == 0) {
            return mp_const_false;
        }
        int32_t old_px = player_x;
        int32_t old_py = player_y;
        int32_t old_bx = lgfx_rd_i16(row + 0);
        int32_t old_by = lgfx_rd_i16(row + 2);
        int32_t bullet_w = lgfx_rd_i16(row + 8);
        int32_t bullet_h = lgfx_rd_i16(row + 10);
        if (bullet_w <= 0 || bullet_h <= 0) {
            return mp_const_false;
        }
        player_x = old_bx + lgfx_floor_div2(bullet_w - player_w);
        player_y = old_by + (bullet_h - player_h);
        int32_t new_bx = old_px + lgfx_floor_div2(player_w - bullet_w);
        int32_t new_by = old_py + (player_h - bullet_h);
        player_x = lgfx_clamp_i32(player_x, 0, max_player_x);
        player_y = lgfx_clamp_i32(player_y, 0, max_player_y);
        lgfx_wr_i16(row + 0, new_bx);
        lgfx_wr_i16(row + 2, new_by);
        lgfx_wr_i16(row + 14, -1);
        lgfx_write_swap_result(result, 1, target_kind, target_index, player_x, player_y, 0, -1, -1, -1, target_index, 4);
        return mp_const_true;
    }

    return mp_const_false;
}

MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_perform_swap_native_obj, 25, 25, lgfx_perform_swap_native);

#endif