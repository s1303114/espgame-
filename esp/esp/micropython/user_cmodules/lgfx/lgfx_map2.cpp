#if !defined(NO_QSTR)
extern "C" {
#include "py/obj.h"
#include "py/runtime.h"
}

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "lgfx_game.hpp"
#include "lgfx_shared.hpp"

static constexpr int32_t kMap2BowStateIdle = 0;
static constexpr int32_t kMap2BowStateShoot = 1;
static constexpr int32_t kMap2BowStateDeath = 3;
static constexpr int32_t kMap2BowDeathFrameCount = 5;
static constexpr int32_t kMap2SwapTargetNone = 0;
static constexpr int32_t kMap2SwapTargetBow = 2;
static constexpr int32_t kMap2SwapTargetArrow = 3;
static constexpr int32_t kMap2SwapTargetStar = 4;
static constexpr int32_t kMap2CollectActiveOff = 0;
static constexpr int32_t kMap2CollectPendingOff = 1;
static constexpr int32_t kMap2CollectSlotOff = 2;
static constexpr int32_t kMap2CollectXOff = 4;
static constexpr int32_t kMap2CollectYOff = 6;
static constexpr int32_t kMap2CollectCountOff = 8;
static constexpr int32_t kMap2CollectTotalOff = 10;
static constexpr int32_t kMap2CollectWallSpeedOff = 12;
static constexpr int32_t kMap2CollectSeqOff = 14;
static constexpr int32_t kMap2CollectSeqMask = 0x00FF;
static constexpr int32_t kMap2CollectReqLeft = 0x0100;
static constexpr int32_t kMap2CollectReqRight = 0x0200;
static constexpr int32_t kMap2EnvWallScrollOff = 0;
static constexpr int32_t kMap2EnvDoorYOff = 2;
static constexpr int32_t kMap2EnvDoorEnabledOff = 4;
static constexpr int32_t kMap2EnvLeverRunningOff = 5;
static constexpr int32_t kMap2EnvFloorLeftYOff = 6;
static constexpr int32_t kMap2EnvFloorRightYOff = 8;
static constexpr int32_t kMap2EnvLeftBowGapOff = 10;
static constexpr int32_t kMap2EnvRightBowGapOff = 12;
static constexpr int32_t kMap2EnvBowRngOff = 14;
static constexpr int32_t kMap2EnvLeftWrappedOff = 18;
static constexpr int32_t kMap2EnvRightWrappedOff = 19;
static constexpr int32_t kMap2EnvPlayerDeathOff = 20;
static constexpr int32_t kMap2EnvWallSpeedOff = 22;
static constexpr int32_t kMap2EnvDoorSpeedOff = 24;
static constexpr int32_t kMap2EnvPlatformSpeedOff = 26;
static constexpr int32_t kMap2StarXOff = 0;
static constexpr int32_t kMap2StarYOff = 2;
static constexpr int32_t kMap2StarVyOff = 4;
static constexpr int32_t kMap2StarWOff = 6;
static constexpr int32_t kMap2StarHOff = 8;
static constexpr int32_t kMap2StarActiveOff = 10;
static constexpr int32_t kMap2StarStartedOff = 11;
static constexpr int32_t kMap2StarTimerOff = 12;

static bool map2_aabb(int32_t ax, int32_t ay, int32_t aw, int32_t ah, int32_t bx, int32_t by, int32_t bw, int32_t bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

static void map2_wr_i32(uint8_t *p, int32_t v) {
    uint32_t uv = (uint32_t)v;
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
    p[2] = (uint8_t)((uv >> 16) & 0xFFu);
    p[3] = (uint8_t)((uv >> 24) & 0xFFu);
}

static int32_t map2_rd_i32(const uint8_t *p) {
    uint32_t uv = (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    return (int32_t)uv;
}

static int32_t map2_next_floor_bow_random(uint8_t *env_buf) {
    int32_t seed = map2_rd_i32(env_buf + kMap2EnvBowRngOff);
    seed = (int32_t)(((uint32_t)seed * 1103515245u + 12345u) & 0x7FFFFFFFu);
    map2_wr_i32(env_buf + kMap2EnvBowRngOff, seed);
    return (seed >> 16) & 0x7FFF;
}

static int32_t map2_platform_x0(int32_t slot, int32_t floor_x, int32_t left_w, int32_t middle_w) {
    if (slot == 0) {
        return floor_x;
    }
    if (slot == 1) {
        return floor_x + left_w;
    }
    return floor_x + left_w + middle_w;
}

static int32_t map2_platform_w(int32_t slot, int32_t left_w, int32_t middle_w, int32_t right_w) {
    if (slot == 0) {
        return left_w;
    }
    if (slot == 1) {
        return middle_w;
    }
    return right_w;
}

static int32_t map2_platform_top(int32_t slot, int32_t floor_y, int32_t left_y, int32_t right_y, int32_t screen_h) {
    int32_t top = floor_y;
    if (slot == 0) {
        top = left_y;
    } else if (slot == 2) {
        top = right_y;
    }
    if (top < 0 || top >= screen_h) {
        return INT32_MIN;
    }
    return top;
}

static bool map2_overlaps_platform_x(int32_t x, int32_t w, int32_t slot, int32_t floor_x, int32_t left_w, int32_t middle_w, int32_t right_w) {
    int32_t px = map2_platform_x0(slot, floor_x, left_w, middle_w);
    int32_t pw = map2_platform_w(slot, left_w, middle_w, right_w);
    return x < px + pw && x + w > px;
}

static int32_t map2_visible_target_distance2(
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t screen_w,
    int32_t screen_h
) {
    int32_t x1 = x + w;
    int32_t y1 = y + h;
    int32_t cx0 = x < 0 ? 0 : x;
    int32_t cy0 = y < 0 ? 0 : y;
    int32_t cx1 = x1 > screen_w ? screen_w : x1;
    int32_t cy1 = y1 > screen_h ? screen_h : y1;
    if (cx1 <= cx0 || cy1 <= cy0) {
        return -1;
    }
    int32_t visible_w = cx1 - cx0;
    int32_t visible_h = cy1 - cy0;
    if (visible_w < 10 || visible_h < 10 || visible_w * visible_h < 128) {
        return -1;
    }
    int32_t px = player_x + (player_w / 2);
    int32_t py = player_y + (player_h / 2);
    int32_t ox = (cx0 + cx1) / 2;
    int32_t oy = (cy0 + cy1) / 2;
    int32_t dx = ox - px;
    int32_t dy = oy - py;
    return dx * dx + dy * dy;
}

static int32_t map2_bow_index_for_slot(uint8_t *bow_buf, int32_t bow_stride, int32_t bow_count, int32_t slot) {
    for (int32_t i = 0; i < bow_count; ++i) {
        uint8_t *bow = bow_buf + ((size_t)i * (size_t)bow_stride);
        if (lgfx_rd_i16(bow + 10) == slot) {
            return i;
        }
    }
    return -1;
}

static uint8_t *map2_bow_for_slot(uint8_t *bow_buf, int32_t bow_stride, int32_t bow_count, int32_t slot) {
    int32_t idx = map2_bow_index_for_slot(bow_buf, bow_stride, bow_count, slot);
    if (idx < 0) {
        return nullptr;
    }
    return bow_buf + ((size_t)idx * (size_t)bow_stride);
}

static bool map2_bow_alive(const uint8_t *bow) {
    return bow && bow[8] != 0u && bow[12] != kMap2BowStateDeath;
}

static bool map2_bound_bow_blocks_collect_slot(uint8_t *bow_buf, int32_t bow_stride, int32_t bow_count, int32_t slot) {
    for (int32_t i = 0; i < bow_count; ++i) {
        uint8_t *bow = bow_buf + ((size_t)i * (size_t)bow_stride);
        if (lgfx_rd_i16(bow + 10) == slot && bow[8] != 0u && bow[9] != 0u) {
            return true;
        }
    }
    return false;
}

static int32_t map2_bound_bow_x(int32_t slot, int32_t floor_x, int32_t left_w, int32_t middle_w, int32_t bow_w, int32_t left_offset_x, int32_t right_offset_x) {
    int32_t offset = slot == 0 ? left_offset_x : right_offset_x;
    int32_t base_x = slot == 0 ? floor_x : floor_x + left_w + middle_w;
    return base_x + offset - (bow_w / 2);
}

static void map2_update_bound_bow_position(uint8_t *bow, int32_t slot, int32_t floor_x, int32_t floor_y, int32_t left_w, int32_t middle_w, int32_t left_y, int32_t right_y, int32_t bow_w, int32_t bow_h, int32_t left_offset_x, int32_t right_offset_x) {
    if (!bow || !bow[8] || !bow[9]) {
        return;
    }
    int32_t top = floor_y;
    if (slot == 0) {
        top = left_y;
    } else if (slot == 2) {
        top = right_y;
    }
    lgfx_wr_i16(bow + 0, map2_bound_bow_x(slot, floor_x, left_w, middle_w, bow_w, left_offset_x, right_offset_x));
    lgfx_wr_i16(bow + 2, top - bow_h);
}

static void map2_roll_floor_bow_native(
    uint8_t *env_buf,
    uint8_t *bow,
    int32_t slot,
    int32_t gap_off,
    bool bow_enabled,
    int32_t min_gap,
    int32_t chance,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t left_y,
    int32_t right_y,
    int32_t bow_w,
    int32_t bow_h,
    int32_t left_offset_x,
    int32_t right_offset_x,
    int32_t shoot_interval
) {
    if (!bow) {
        return;
    }
    if (!bow_enabled) {
        bow[8] = 0u;
        return;
    }
    if (bow[8] != 0u) {
        bow[9] = 1u;
        map2_update_bound_bow_position(bow, slot, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x);
        return;
    }
    if (min_gap < 0) {
        min_gap = 0;
    }
    int32_t gap = lgfx_rd_i16(env_buf + gap_off);
    if (gap < min_gap) {
        lgfx_wr_i16(env_buf + gap_off, gap + 1);
        bow[8] = 0u;
        return;
    }
    if (chance < 0) {
        chance = 0;
    }
    if (chance > 100) {
        chance = 100;
    }
    bool spawn = (map2_next_floor_bow_random(env_buf) % 100) < chance;
    lgfx_wr_i16(env_buf + gap_off, spawn ? 0 : gap + 1);
    bow[8] = spawn ? 1u : 0u;
    bow[9] = 1u;
    lgfx_wr_i16(bow + 4, bow_w);
    lgfx_wr_i16(bow + 6, bow_h);
    lgfx_wr_i16(bow + 10, slot);
    bow[12] = kMap2BowStateIdle;
    bow[13] = 0u;
    lgfx_wr_i16(bow + 14, 0);
    lgfx_wr_i16(bow + 16, shoot_interval);
    lgfx_wr_i16(bow + 18, 0);
    if (spawn) {
        map2_update_bound_bow_position(bow, slot, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x);
    }
}

static int32_t map2_collect_platform_top_unculled(int32_t slot, int32_t floor_y, int32_t left_y, int32_t right_y) {
    if (slot == 0) {
        return left_y;
    }
    if (slot == 2) {
        return right_y;
    }
    return floor_y;
}

static int32_t map2_collect_wall_speed(int32_t collected) {
    int32_t speed = collected + 1;
    if (speed < 1) {
        speed = 1;
    }
    if (speed > 5) {
        speed = 5;
    }
    return speed;
}

static void map2_write_collectible_position(
    uint8_t *collect_buf,
    int32_t slot,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t left_y,
    int32_t right_y,
    int32_t local_x,
    int32_t local_y
) {
    int32_t x = map2_platform_x0(slot, floor_x, left_w, middle_w) + local_x;
    int32_t y = map2_collect_platform_top_unculled(slot, floor_y, left_y, right_y) + local_y;
    lgfx_wr_i16(collect_buf + kMap2CollectXOff, x);
    lgfx_wr_i16(collect_buf + kMap2CollectYOff, y);
}

static void map2_update_collectible(
    uint8_t *collect_buf,
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t left_y,
    int32_t right_y,
    int32_t collect_w,
    int32_t collect_h,
    int32_t local_x,
    int32_t local_y,
    int32_t total
) {
    if (!collect_buf) {
        return;
    }
    if (collect_w <= 0) {
        collect_w = 32;
    }
    if (collect_h <= 0) {
        collect_h = 32;
    }
    if (total <= 0) {
        total = 5;
    }
    int32_t collected = lgfx_rd_i16(collect_buf + kMap2CollectCountOff);
    if (collected < 0) {
        collected = 0;
    }
    if (collected > total) {
        collected = total;
    }
    int32_t seq_flags = lgfx_rd_i16(collect_buf + kMap2CollectSeqOff);
    bool request_left = (seq_flags & kMap2CollectReqLeft) != 0;
    bool request_right = (seq_flags & kMap2CollectReqRight) != 0;
    int32_t seq = seq_flags & kMap2CollectSeqMask;
    bool active = collect_buf[kMap2CollectActiveOff] != 0u;
    int32_t slot = lgfx_rd_i16(collect_buf + kMap2CollectSlotOff);
    if (slot != 0 && slot != 2) {
        active = false;
        slot = -1;
    }
    if (collected >= total) {
        collect_buf[kMap2CollectActiveOff] = 0u;
        collect_buf[kMap2CollectPendingOff] = 0u;
        lgfx_wr_i16(collect_buf + kMap2CollectSlotOff, -1);
        lgfx_wr_i16(collect_buf + kMap2CollectCountOff, collected);
        lgfx_wr_i16(collect_buf + kMap2CollectTotalOff, total);
        lgfx_wr_i16(collect_buf + kMap2CollectWallSpeedOff, map2_collect_wall_speed(collected));
        lgfx_wr_i16(collect_buf + kMap2CollectSeqOff, seq);
        return;
    }
    if (active && map2_bound_bow_blocks_collect_slot(bow_buf, bow_stride, bow_count, slot)) {
        active = false;
        slot = -1;
    }
    if (!active && (request_left || request_right)) {
        slot = -1;
        int32_t first_slot = (seq & 1) ? 2 : 0;
        int32_t second_slot = first_slot == 0 ? 2 : 0;
        bool first_requested = first_slot == 0 ? request_left : request_right;
        bool second_requested = second_slot == 0 ? request_left : request_right;
        if (first_requested && !map2_bound_bow_blocks_collect_slot(bow_buf, bow_stride, bow_count, first_slot)) {
            slot = first_slot;
            active = true;
            ++seq;
        } else if (second_requested && !map2_bound_bow_blocks_collect_slot(bow_buf, bow_stride, bow_count, second_slot)) {
            slot = second_slot;
            active = true;
            ++seq;
        }
    }
    if (active) {
        map2_write_collectible_position(collect_buf, slot, floor_x, floor_y, left_w, middle_w, left_y, right_y, local_x, local_y);
        int32_t collect_x = lgfx_rd_i16(collect_buf + kMap2CollectXOff);
        int32_t collect_y = lgfx_rd_i16(collect_buf + kMap2CollectYOff);
        if (map2_aabb(player_x, player_y, player_w, player_h, collect_x, collect_y, collect_w, collect_h)) {
            ++collected;
            if (collected > total) {
                collected = total;
            }
            active = false;
            slot = -1;
        }
    }
    collect_buf[kMap2CollectActiveOff] = active ? 1u : 0u;
    collect_buf[kMap2CollectPendingOff] = (!active && collected < total) ? 1u : 0u;
    lgfx_wr_i16(collect_buf + kMap2CollectSlotOff, slot);
    lgfx_wr_i16(collect_buf + kMap2CollectCountOff, collected);
    lgfx_wr_i16(collect_buf + kMap2CollectTotalOff, total);
    lgfx_wr_i16(collect_buf + kMap2CollectWallSpeedOff, map2_collect_wall_speed(collected));
    lgfx_wr_i16(collect_buf + kMap2CollectSeqOff, seq & kMap2CollectSeqMask);
}

static void map2_clear_swap(uint8_t *swap_buf) {
    swap_buf[0] = 0u;
    swap_buf[1] = 0u;
    swap_buf[2] = 0u;
    swap_buf[3] = 0u;
    lgfx_wr_i16(swap_buf + 4, -1);
    lgfx_wr_i16(swap_buf + 6, 0);
    lgfx_wr_i16(swap_buf + 8, 0);
    lgfx_wr_i16(swap_buf + 10, 0);
    lgfx_wr_i16(swap_buf + 12, 0);
    map2_wr_i32(swap_buf + 14, -1);
    lgfx_wr_i16(swap_buf + 18, 0);
}

static void map2_set_swap_preview(uint8_t *swap_buf, bool active, bool valid, int32_t kind, int32_t index, int32_t x, int32_t y, int32_t w, int32_t h, int32_t d2) {
    swap_buf[0] = active ? 1u : 0u;
    swap_buf[1] = valid ? 1u : 0u;
    swap_buf[3] = (uint8_t)(kind & 0xFF);
    lgfx_wr_i16(swap_buf + 4, index);
    lgfx_wr_i16(swap_buf + 6, x);
    lgfx_wr_i16(swap_buf + 8, y);
    lgfx_wr_i16(swap_buf + 10, w);
    lgfx_wr_i16(swap_buf + 12, h);
    map2_wr_i32(swap_buf + 14, d2);
}

static void map2_pick_swap_target(
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *arrow_buf,
    int32_t arrow_stride,
    int32_t arrow_count,
    uint8_t *star_buf,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    bool pick_far,
    int32_t screen_w,
    int32_t screen_h,
    int32_t *out_kind,
    int32_t *out_index,
    int32_t *out_x,
    int32_t *out_y,
    int32_t *out_w,
    int32_t *out_h,
    int32_t *out_d2
) {
    int32_t best_bow_slot = -1;
    int32_t best_bow_x = 0;
    int32_t best_bow_y = 0;
    int32_t best_bow_w = 0;
    int32_t best_bow_h = 0;
    int32_t best_bow_d2 = -1;
    for (int32_t i = 0; i < bow_count; ++i) {
        uint8_t *bow = bow_buf + ((size_t)i * (size_t)bow_stride);
        if (!map2_bow_alive(bow)) {
            continue;
        }
        int32_t x = lgfx_rd_i16(bow + 0);
        int32_t y = lgfx_rd_i16(bow + 2);
        int32_t w = lgfx_rd_i16(bow + 4);
        int32_t h = lgfx_rd_i16(bow + 6);
        int32_t d2 = map2_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, screen_w, screen_h);
        if (d2 < 0) {
            continue;
        }
        if (best_bow_slot < 0 || (pick_far && d2 > best_bow_d2) || (!pick_far && d2 < best_bow_d2)) {
            best_bow_slot = lgfx_rd_i16(bow + 10);
            best_bow_x = x;
            best_bow_y = y;
            best_bow_w = w;
            best_bow_h = h;
            best_bow_d2 = d2;
        }
    }

    int32_t best_arrow_i = -1;
    int32_t best_arrow_x = 0;
    int32_t best_arrow_y = 0;
    int32_t best_arrow_w = 0;
    int32_t best_arrow_h = 0;
    int32_t best_arrow_d2 = -1;
    for (int32_t i = 0; i < arrow_count; ++i) {
        uint8_t *arrow = arrow_buf + ((size_t)i * (size_t)arrow_stride);
        if (lgfx_rd_i16(arrow + 12) == 0) {
            continue;
        }
        int32_t x = lgfx_rd_i16(arrow + 0);
        int32_t y = lgfx_rd_i16(arrow + 2);
        int32_t w = lgfx_rd_i16(arrow + 8);
        int32_t h = lgfx_rd_i16(arrow + 10);
        int32_t d2 = map2_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, screen_w, screen_h);
        if (d2 < 0) {
            continue;
        }
        if (best_arrow_i < 0 || (pick_far && d2 > best_arrow_d2) || (!pick_far && d2 < best_arrow_d2)) {
            best_arrow_i = i;
            best_arrow_x = x;
            best_arrow_y = y;
            best_arrow_w = w;
            best_arrow_h = h;
            best_arrow_d2 = d2;
        }
    }

    int32_t best_star_i = -1;
    int32_t best_star_x = 0;
    int32_t best_star_y = 0;
    int32_t best_star_w = 0;
    int32_t best_star_h = 0;
    int32_t best_star_d2 = -1;
    if (star_buf && star_buf[kMap2StarActiveOff] != 0u) {
        int32_t x = lgfx_rd_i16(star_buf + kMap2StarXOff);
        int32_t y = lgfx_rd_i16(star_buf + kMap2StarYOff);
        int32_t w = lgfx_rd_i16(star_buf + kMap2StarWOff);
        int32_t h = lgfx_rd_i16(star_buf + kMap2StarHOff);
        int32_t d2 = map2_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, screen_w, screen_h);
        if (d2 >= 0) {
            best_star_i = 0;
            best_star_x = x;
            best_star_y = y;
            best_star_w = w;
            best_star_h = h;
            best_star_d2 = d2;
        }
    }

    *out_kind = kMap2SwapTargetNone;
    *out_index = -1;
    *out_x = 0;
    *out_y = 0;
    *out_w = 0;
    *out_h = 0;
    *out_d2 = -1;
    if (best_bow_slot < 0 && best_arrow_i < 0 && best_star_i < 0) {
        return;
    }
    int32_t best_kind = kMap2SwapTargetNone;
    int32_t best_index = -1;
    int32_t best_x = 0;
    int32_t best_y = 0;
    int32_t best_w = 0;
    int32_t best_h = 0;
    int32_t best_d2 = -1;
    if (best_bow_slot >= 0) {
        best_kind = kMap2SwapTargetBow;
        best_index = best_bow_slot;
        best_x = best_bow_x;
        best_y = best_bow_y;
        best_w = best_bow_w;
        best_h = best_bow_h;
        best_d2 = best_bow_d2;
    }
    if (best_arrow_i >= 0 && (best_kind == kMap2SwapTargetNone || (pick_far && best_arrow_d2 > best_d2) || (!pick_far && best_arrow_d2 < best_d2))) {
        best_kind = kMap2SwapTargetArrow;
        best_index = best_arrow_i;
        best_x = best_arrow_x;
        best_y = best_arrow_y;
        best_w = best_arrow_w;
        best_h = best_arrow_h;
        best_d2 = best_arrow_d2;
    }
    if (best_star_i >= 0 && (best_kind == kMap2SwapTargetNone || (pick_far && best_star_d2 > best_d2) || (!pick_far && best_star_d2 < best_d2))) {
        best_kind = kMap2SwapTargetStar;
        best_index = best_star_i;
        best_x = best_star_x;
        best_y = best_star_y;
        best_w = best_star_w;
        best_h = best_star_h;
        best_d2 = best_star_d2;
    }
    if (best_kind == kMap2SwapTargetArrow) {
        *out_kind = kMap2SwapTargetArrow;
        *out_index = best_index;
        *out_x = best_x;
        *out_y = best_y;
        *out_w = best_w;
        *out_h = best_h;
        *out_d2 = best_d2;
        return;
    }
    *out_kind = best_kind;
    *out_index = best_index;
    *out_x = best_x;
    *out_y = best_y;
    *out_w = best_w;
    *out_h = best_h;
    *out_d2 = best_d2;
}

static void map2_player_ground_after_swap(
    uint8_t *result_buf,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t left_y,
    int32_t right_y,
    int32_t screen_h
) {
    int32_t foot_x = player_x + (player_w / 2);
    int32_t slot = -1;
    int32_t left_x1 = floor_x + left_w;
    int32_t middle_x1 = left_x1 + middle_w;
    int32_t right_x1 = middle_x1 + right_w;
    if (foot_x >= floor_x && foot_x < right_x1) {
        if (foot_x < left_x1) {
            slot = 0;
        } else if (foot_x < middle_x1) {
            slot = 1;
        } else {
            slot = 2;
        }
    }
    uint8_t airborne = 1u;
    int32_t matched_slot = -1;
    if (slot >= 0) {
        int32_t top = map2_platform_top(slot, floor_y, left_y, right_y, screen_h);
        if (top != INT32_MIN && player_y + player_h == top) {
            airborne = 0u;
            matched_slot = slot;
        }
    }
    result_buf[5] = airborne;
    lgfx_wr_i16(result_buf + 6, matched_slot);
    lgfx_wr_i16(result_buf + 8, 0);
    result_buf[10] = 1u;
}

static void map2_perform_swap(
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *arrow_buf,
    int32_t arrow_stride,
    int32_t arrow_count,
    uint8_t *star_buf,
    uint8_t *result_buf,
    int32_t kind,
    int32_t index,
    bool pick_far,
    int32_t *player_x,
    int32_t *player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t min_player_x,
    int32_t max_player_x,
    int32_t screen_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t left_y,
    int32_t right_y
) {
    (void)pick_far;
    int32_t old_px = *player_x;
    int32_t old_py = *player_y;
    int32_t max_y = screen_h - player_h;
    if (max_y < 0) {
        max_y = 0;
    }
    if (kind == kMap2SwapTargetBow) {
        uint8_t *bow = map2_bow_for_slot(bow_buf, bow_stride, bow_count, index);
        if (!map2_bow_alive(bow)) {
            return;
        }
        int32_t bow_x = lgfx_rd_i16(bow + 0);
        int32_t bow_y = lgfx_rd_i16(bow + 2);
        int32_t bow_w = lgfx_rd_i16(bow + 4);
        int32_t bow_h = lgfx_rd_i16(bow + 6);
        *player_x = bow_x + ((bow_w - player_w) / 2);
        *player_y = bow_y + (bow_h - player_h);
        *player_x = lgfx_clamp_i32(*player_x, min_player_x, max_player_x);
        *player_y = lgfx_clamp_i32(*player_y, 0, max_y);
        bow[9] = 0u;
        lgfx_wr_i16(bow + 0, old_px + ((player_w - bow_w) / 2));
        lgfx_wr_i16(bow + 2, old_py + (player_h - bow_h));
        lgfx_wr_i16(bow + 18, 0);
        for (int32_t i = 0; i < arrow_count; ++i) {
            uint8_t *arrow = arrow_buf + ((size_t)i * (size_t)arrow_stride);
            if (lgfx_rd_i16(arrow + 14) == index) {
                lgfx_wr_i16(arrow + 14, -1);
            }
        }
        map2_player_ground_after_swap(result_buf, *player_x, *player_y, player_w, player_h, floor_x, floor_y, left_w, middle_w, right_w, left_y, right_y, screen_h);
    } else if (kind == kMap2SwapTargetArrow) {
        if (index < 0 || index >= arrow_count) {
            return;
        }
        uint8_t *arrow = arrow_buf + ((size_t)index * (size_t)arrow_stride);
        if (lgfx_rd_i16(arrow + 12) == 0) {
            return;
        }
        int32_t arrow_x = lgfx_rd_i16(arrow + 0);
        int32_t arrow_y = lgfx_rd_i16(arrow + 2);
        int32_t arrow_w = lgfx_rd_i16(arrow + 8);
        int32_t arrow_h = lgfx_rd_i16(arrow + 10);
        *player_x = arrow_x + ((arrow_w - player_w) / 2);
        *player_y = arrow_y + (arrow_h - player_h);
        *player_x = lgfx_clamp_i32(*player_x, min_player_x, max_player_x);
        *player_y = lgfx_clamp_i32(*player_y, 0, max_y);
        lgfx_wr_i16(arrow + 0, old_px + ((player_w - arrow_w) / 2));
        lgfx_wr_i16(arrow + 2, old_py + (player_h - arrow_h));
        lgfx_wr_i16(arrow + 14, -1);
        map2_player_ground_after_swap(result_buf, *player_x, *player_y, player_w, player_h, floor_x, floor_y, left_w, middle_w, right_w, left_y, right_y, screen_h);
    } else if (kind == kMap2SwapTargetStar) {
        if (!star_buf || star_buf[kMap2StarActiveOff] == 0u) {
            return;
        }
        int32_t star_x = lgfx_rd_i16(star_buf + kMap2StarXOff);
        int32_t star_y = lgfx_rd_i16(star_buf + kMap2StarYOff);
        int32_t star_w = lgfx_rd_i16(star_buf + kMap2StarWOff);
        int32_t star_h = lgfx_rd_i16(star_buf + kMap2StarHOff);
        *player_x = star_x + ((star_w - player_w) / 2);
        *player_y = star_y + (star_h - player_h);
        *player_x = lgfx_clamp_i32(*player_x, min_player_x, max_player_x);
        *player_y = lgfx_clamp_i32(*player_y, 0, max_y);
        lgfx_wr_i16(star_buf + kMap2StarXOff, old_px + ((player_w - star_w) / 2));
        lgfx_wr_i16(star_buf + kMap2StarYOff, old_py + (player_h - star_h));
        map2_player_ground_after_swap(result_buf, *player_x, *player_y, player_w, player_h, floor_x, floor_y, left_w, middle_w, right_w, left_y, right_y, screen_h);
    }
}

static void map2_update_swap(
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *arrow_buf,
    int32_t arrow_stride,
    int32_t arrow_count,
    uint8_t *star_buf,
    uint8_t *swap_buf,
    uint8_t *result_buf,
    int32_t *player_x,
    int32_t *player_y,
    int32_t player_w,
    int32_t player_h,
    bool btn_b_down,
    bool btn_y_down,
    int32_t screen_w,
    int32_t screen_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t left_y,
    int32_t right_y,
    int32_t min_player_x,
    int32_t max_player_x
) {
    uint8_t b_now = btn_b_down ? 1u : 0u;
    uint8_t y_now = btn_y_down ? 1u : 0u;
    uint8_t b_prev = swap_buf[20] ? 1u : 0u;
    uint8_t y_prev = swap_buf[21] ? 1u : 0u;
    bool b_edge = b_now && !b_prev;
    bool y_edge = y_now && !y_prev;
    bool b_release = !b_now && b_prev;
    bool y_release = !y_now && y_prev;
    swap_buf[20] = b_now;
    swap_buf[21] = y_now;

    if (!swap_buf[0]) {
        if (b_edge) {
            swap_buf[0] = 1u;
            swap_buf[2] = 1u;
            lgfx_wr_i16(swap_buf + 18, 1);
        } else if (y_edge) {
            swap_buf[0] = 1u;
            swap_buf[2] = 0u;
            lgfx_wr_i16(swap_buf + 18, 2);
        }
    }

    if (swap_buf[0]) {
        bool pick_far = swap_buf[2] != 0u;
        int32_t button = lgfx_rd_i16(swap_buf + 18);
        if ((button == 1 && b_now) || (button == 2 && y_now)) {
            int32_t kind = 0;
            int32_t index = -1;
            int32_t x = 0;
            int32_t y = 0;
            int32_t w = 0;
            int32_t h = 0;
            int32_t d2 = -1;
            map2_pick_swap_target(bow_buf, bow_stride, bow_count, arrow_buf, arrow_stride, arrow_count, star_buf, *player_x, *player_y, player_w, player_h, pick_far, screen_w, screen_h, &kind, &index, &x, &y, &w, &h, &d2);
            map2_set_swap_preview(swap_buf, true, kind != kMap2SwapTargetNone, kind, index, x, y, w, h, d2);
        } else if ((button == 1 && b_release) || (button == 2 && y_release)) {
            if (swap_buf[1]) {
                int32_t kind = (int32_t)swap_buf[3];
                int32_t index = lgfx_rd_i16(swap_buf + 4);
                map2_perform_swap(bow_buf, bow_stride, bow_count, arrow_buf, arrow_stride, arrow_count, star_buf, result_buf, kind, index, pick_far, player_x, player_y, player_w, player_h, min_player_x, max_player_x, screen_h, floor_x, floor_y, left_w, middle_w, right_w, left_y, right_y);
            }
            map2_clear_swap(swap_buf);
        } else if (!b_now && !y_now) {
            map2_clear_swap(swap_buf);
        }
    } else if (!b_now && !y_now) {
        map2_set_swap_preview(swap_buf, false, false, kMap2SwapTargetNone, -1, 0, 0, 0, 0, -1);
    }
}

static bool map2_spawn_arrow(uint8_t *arrow_buf, int32_t arrow_stride, int32_t arrow_count, int32_t x, int32_t y, int32_t vx, int32_t w, int32_t h, int32_t owner_slot) {
    for (int32_t i = 0; i < arrow_count; ++i) {
        uint8_t *arrow = arrow_buf + ((size_t)i * (size_t)arrow_stride);
        if (lgfx_rd_i16(arrow + 12) == 0) {
            lgfx_wr_i16(arrow + 0, x);
            lgfx_wr_i16(arrow + 2, y);
            lgfx_wr_i16(arrow + 4, vx);
            lgfx_wr_i16(arrow + 6, 0);
            lgfx_wr_i16(arrow + 8, w);
            lgfx_wr_i16(arrow + 10, h);
            lgfx_wr_i16(arrow + 12, 1);
            lgfx_wr_i16(arrow + 14, owner_slot);
            return true;
        }
    }
    return false;
}

static void map2_hide_bow(uint8_t *bow, int32_t shoot_interval) {
    bow[8] = 0u;
    bow[9] = 1u;
    bow[12] = kMap2BowStateIdle;
    bow[13] = 0u;
    lgfx_wr_i16(bow + 14, 0);
    lgfx_wr_i16(bow + 16, shoot_interval);
    lgfx_wr_i16(bow + 18, 0);
}

static void map2_kill_bow(uint8_t *bow) {
    if (!bow || !bow[8] || bow[12] == kMap2BowStateDeath) {
        return;
    }
    bow[12] = kMap2BowStateDeath;
    bow[13] = 0u;
    lgfx_wr_i16(bow + 14, 0);
    lgfx_wr_i16(bow + 16, 0);
}

static void map2_update_free_bow_physics(
    uint8_t *bow,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t floor_h,
    int32_t left_y,
    int32_t right_y,
    int32_t screen_h,
    int32_t gravity,
    int32_t max_fall_speed,
    int32_t death_y,
    int32_t shoot_interval
) {
    (void)floor_h;
    if (!bow || !bow[8] || bow[9]) {
        return;
    }
    int32_t bow_x = lgfx_rd_i16(bow + 0);
    int32_t bow_y = lgfx_rd_i16(bow + 2);
    int32_t bow_w = lgfx_rd_i16(bow + 4);
    int32_t bow_h = lgfx_rd_i16(bow + 6);
    for (int32_t slot = 0; slot < 3; ++slot) {
        int32_t top = map2_platform_top(slot, floor_y, left_y, right_y, screen_h);
        if (top == INT32_MIN) {
            continue;
        }
        if (bow_y + bow_h == top && map2_overlaps_platform_x(bow_x, bow_w, slot, floor_x, left_w, middle_w, right_w)) {
            lgfx_wr_i16(bow + 18, 0);
            return;
        }
    }
    int32_t vel_y = lgfx_rd_i16(bow + 18) + gravity;
    if (vel_y > max_fall_speed) {
        vel_y = max_fall_speed;
    }
    int32_t old_foot = bow_y + bow_h;
    int32_t new_y = bow_y + vel_y;
    int32_t new_foot = new_y + bow_h;
    for (int32_t slot = 0; slot < 3; ++slot) {
        int32_t top = map2_platform_top(slot, floor_y, left_y, right_y, screen_h);
        if (top == INT32_MIN) {
            continue;
        }
        if (old_foot <= top && new_foot >= top && map2_overlaps_platform_x(bow_x, bow_w, slot, floor_x, left_w, middle_w, right_w)) {
            lgfx_wr_i16(bow + 2, top - bow_h);
            lgfx_wr_i16(bow + 18, 0);
            return;
        }
    }
    lgfx_wr_i16(bow + 2, new_y);
    lgfx_wr_i16(bow + 18, vel_y);
    if (new_y > death_y) {
        map2_hide_bow(bow, shoot_interval);
    }
}

static void map2_update_bow_actor(
    uint8_t *bow,
    uint8_t *arrow_buf,
    int32_t arrow_stride,
    int32_t arrow_count,
    int32_t shoot_interval,
    int32_t fire_frame,
    int32_t shoot_frames,
    int32_t frame_hold,
    int32_t arrow_speed,
    int32_t arrow_w,
    int32_t arrow_h
) {
    if (!bow || !bow[8]) {
        return;
    }
    if (shoot_interval < 1) {
        shoot_interval = 15;
    }
    if (fire_frame < 0) {
        fire_frame = 0;
    }
    if (shoot_frames < 1) {
        shoot_frames = 10;
    }
    if (frame_hold < 1) {
        frame_hold = 1;
    }
    if (arrow_speed < 1) {
        arrow_speed = 1;
    }
    int32_t slot = lgfx_rd_i16(bow + 10);
    int32_t state = bow[12];
    int32_t anim = lgfx_rd_i16(bow + 14) + 1;
    if (state == kMap2BowStateDeath) {
        if (anim >= kMap2BowDeathFrameCount * frame_hold) {
            map2_hide_bow(bow, shoot_interval);
            return;
        }
    } else if (state == kMap2BowStateIdle) {
        int32_t cooldown = lgfx_rd_i16(bow + 16) - 1;
        if (cooldown <= 0) {
            state = kMap2BowStateShoot;
            anim = 0;
            bow[13] = 0u;
        }
        lgfx_wr_i16(bow + 16, cooldown);
    } else {
        if (!bow[13] && (anim / frame_hold) >= fire_frame) {
            int32_t bow_x = lgfx_rd_i16(bow + 0);
            int32_t bow_y = lgfx_rd_i16(bow + 2);
            int32_t bow_w = lgfx_rd_i16(bow + 4);
            int32_t bow_h = lgfx_rd_i16(bow + 6);
            int32_t arrow_x = 0;
            int32_t vx = 0;
            if (slot == 0) {
                arrow_x = bow_x + bow_w;
                vx = arrow_speed;
            } else {
                arrow_x = bow_x - arrow_w;
                vx = -arrow_speed;
            }
            int32_t arrow_y = bow_y + ((bow_h - arrow_h) / 2);
            map2_spawn_arrow(arrow_buf, arrow_stride, arrow_count, arrow_x, arrow_y, vx, arrow_w, arrow_h, slot);
            bow[13] = 1u;
        }
        if (anim >= shoot_frames * frame_hold) {
            state = kMap2BowStateIdle;
            anim = 0;
            bow[13] = 0u;
            lgfx_wr_i16(bow + 16, shoot_interval);
        }
    }
    bow[12] = (uint8_t)(state & 0xFF);
    lgfx_wr_i16(bow + 14, anim);
}

static bool map2_arrow_hits_floor(
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t floor_h,
    int32_t left_y,
    int32_t right_y,
    int32_t screen_h
) {
    for (int32_t slot = 0; slot < 3; ++slot) {
        int32_t top = map2_platform_top(slot, floor_y, left_y, right_y, screen_h);
        if (top == INT32_MIN) {
            continue;
        }
        int32_t px = map2_platform_x0(slot, floor_x, left_w, middle_w);
        int32_t pw = map2_platform_w(slot, left_w, middle_w, right_w);
        if (map2_aabb(x, y, w, h, px, top, pw, floor_h)) {
            return true;
        }
    }
    return false;
}

static void map2_update_arrows(
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *arrow_buf,
    int32_t arrow_stride,
    int32_t arrow_count,
    uint8_t *result_buf,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t screen_w,
    int32_t screen_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t floor_h,
    int32_t left_wall_x,
    int32_t right_wall_x,
    int32_t wall_strip_w,
    int32_t left_y,
    int32_t right_y,
    int32_t cull_margin
) {
    if (cull_margin < 0) {
        cull_margin = 0;
    }
    for (int32_t i = 0; i < arrow_count; ++i) {
        uint8_t *arrow = arrow_buf + ((size_t)i * (size_t)arrow_stride);
        if (lgfx_rd_i16(arrow + 12) == 0) {
            continue;
        }
        int32_t x = lgfx_rd_i16(arrow + 0) + lgfx_rd_i16(arrow + 4);
        int32_t y = lgfx_rd_i16(arrow + 2) + lgfx_rd_i16(arrow + 6);
        int32_t w = lgfx_rd_i16(arrow + 8);
        int32_t h = lgfx_rd_i16(arrow + 10);
        int32_t owner = lgfx_rd_i16(arrow + 14);
        lgfx_wr_i16(arrow + 0, x);
        lgfx_wr_i16(arrow + 2, y);
        if (x + w < -cull_margin || x > screen_w + cull_margin || y + h < -cull_margin || y > screen_h + cull_margin) {
            lgfx_wr_i16(arrow + 12, 0);
            continue;
        }
        if (map2_aabb(x, y, w, h, left_wall_x, 0, wall_strip_w, screen_h) || map2_aabb(x, y, w, h, right_wall_x, 0, wall_strip_w, screen_h)) {
            lgfx_wr_i16(arrow + 12, 0);
            continue;
        }
        if (map2_arrow_hits_floor(x, y, w, h, floor_x, floor_y, left_w, middle_w, right_w, floor_h, left_y, right_y, screen_h)) {
            lgfx_wr_i16(arrow + 12, 0);
            continue;
        }
        bool killed_enemy = false;
        for (int32_t bi = 0; bi < bow_count; ++bi) {
            uint8_t *bow = bow_buf + ((size_t)bi * (size_t)bow_stride);
            int32_t slot = lgfx_rd_i16(bow + 10);
            if (owner == slot || !map2_bow_alive(bow)) {
                continue;
            }
            int32_t bx = lgfx_rd_i16(bow + 0);
            int32_t by = lgfx_rd_i16(bow + 2);
            int32_t bw = lgfx_rd_i16(bow + 4);
            int32_t bh = lgfx_rd_i16(bow + 6);
            if (by >= screen_h || by + bh <= 0) {
                continue;
            }
            if (map2_aabb(x, y, w, h, bx, by, bw, bh)) {
                map2_kill_bow(bow);
                lgfx_wr_i16(arrow + 12, 0);
                killed_enemy = true;
                break;
            }
        }
        if (killed_enemy) {
            continue;
        }
        if (map2_aabb(player_x, player_y, player_w, player_h, x, y, w, h)) {
            lgfx_wr_i16(arrow + 12, 0);
            if (result_buf[4] == 0u) {
                result_buf[4] = 1u;
            }
        }
    }
}

static void map2_reset_star(uint8_t *star_buf, int32_t star_w, int32_t star_h, int32_t star_speed) {
    if (!star_buf) {
        return;
    }
    star_buf[kMap2StarActiveOff] = 0u;
    lgfx_wr_i16(star_buf + kMap2StarXOff, 0);
    lgfx_wr_i16(star_buf + kMap2StarYOff, -star_h);
    lgfx_wr_i16(star_buf + kMap2StarVyOff, star_speed);
    lgfx_wr_i16(star_buf + kMap2StarWOff, star_w);
    lgfx_wr_i16(star_buf + kMap2StarHOff, star_h);
}

static void map2_update_star(
    uint8_t *star_buf,
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *result_buf,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t screen_h,
    int32_t floor_x,
    int32_t floor_y,
    int32_t left_w,
    int32_t middle_w,
    int32_t right_w,
    int32_t floor_h,
    int32_t left_y,
    int32_t right_y,
    int32_t lever_x,
    int32_t lever_w,
    int32_t spawn_frames,
    int32_t star_speed,
    int32_t star_w,
    int32_t star_h
) {
    if (!star_buf) {
        return;
    }
    if (star_w <= 0) {
        star_w = 16;
    }
    if (star_h <= 0) {
        star_h = 16;
    }
    if (star_speed < 1) {
        star_speed = 3;
    }
    if (spawn_frames < 1) {
        spawn_frames = 150;
    }
    lgfx_wr_i16(star_buf + kMap2StarWOff, star_w);
    lgfx_wr_i16(star_buf + kMap2StarHOff, star_h);
    lgfx_wr_i16(star_buf + kMap2StarVyOff, star_speed);

    if (star_buf[kMap2StarStartedOff] != 0u && star_buf[kMap2StarActiveOff] == 0u) {
        int32_t timer = lgfx_rd_i16(star_buf + kMap2StarTimerOff) + 1;
        if (timer >= spawn_frames) {
            int32_t spawn_x = lever_x + (lever_w / 2) - (star_w / 2);
            lgfx_wr_i16(star_buf + kMap2StarXOff, spawn_x);
            lgfx_wr_i16(star_buf + kMap2StarYOff, -star_h);
            star_buf[kMap2StarActiveOff] = 1u;
            timer = 0;
        }
        lgfx_wr_i16(star_buf + kMap2StarTimerOff, timer);
    }
    if (star_buf[kMap2StarActiveOff] == 0u) {
        return;
    }

    int32_t x = lgfx_rd_i16(star_buf + kMap2StarXOff);
    int32_t y = lgfx_rd_i16(star_buf + kMap2StarYOff) + star_speed;
    lgfx_wr_i16(star_buf + kMap2StarYOff, y);
    if (y > screen_h) {
        map2_reset_star(star_buf, star_w, star_h, star_speed);
        return;
    }
    if (map2_aabb(player_x, player_y, player_w, player_h, x, y, star_w, star_h)) {
        map2_reset_star(star_buf, star_w, star_h, star_speed);
        if (result_buf[4] == 0u) {
            result_buf[4] = 2u;
        }
        return;
    }
    for (int32_t bi = 0; bi < bow_count; ++bi) {
        uint8_t *bow = bow_buf + ((size_t)bi * (size_t)bow_stride);
        if (!map2_bow_alive(bow)) {
            continue;
        }
        int32_t bx = lgfx_rd_i16(bow + 0);
        int32_t by = lgfx_rd_i16(bow + 2);
        int32_t bw = lgfx_rd_i16(bow + 4);
        int32_t bh = lgfx_rd_i16(bow + 6);
        if (by >= screen_h || by + bh <= 0) {
            continue;
        }
        if (map2_aabb(x, y, star_w, star_h, bx, by, bw, bh)) {
            map2_kill_bow(bow);
            map2_reset_star(star_buf, star_w, star_h, star_speed);
            return;
        }
    }
    if (map2_arrow_hits_floor(x, y, star_w, star_h, floor_x, floor_y, left_w, middle_w, right_w, floor_h, left_y, right_y, screen_h)) {
        map2_reset_star(star_buf, star_w, star_h, star_speed);
        return;
    }
}

static void map2_check_player_bow_hit(
    uint8_t *bow_buf,
    int32_t bow_stride,
    int32_t bow_count,
    uint8_t *result_buf,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t screen_h
) {
    (void)bow_buf;
    (void)bow_stride;
    (void)bow_count;
    if (result_buf[4] != 0u) {
        return;
    }
    (void)result_buf;
    (void)player_x;
    (void)player_y;
    (void)player_w;
    (void)player_h;
    (void)screen_h;
}

static mp_obj_t lgfx_update_map2_environment_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 35) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 35 args"));
    }

    mp_buffer_info_t env_info;
    mp_buffer_info_t bow_info;
    mp_buffer_info_t collect_info;
    mp_get_buffer_raise(args[0], &env_info, MP_BUFFER_RW);
    mp_int_t env_stride = mp_obj_get_int(args[1]);
    mp_get_buffer_raise(args[2], &bow_info, MP_BUFFER_RW);
    mp_int_t bow_stride = mp_obj_get_int(args[3]);
    mp_int_t bow_count = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &collect_info, MP_BUFFER_RW);
    mp_int_t collect_stride = mp_obj_get_int(args[6]);
    int32_t screen_h = mp_obj_get_int(args[7]);
    int32_t floor_x = mp_obj_get_int(args[8]);
    int32_t floor_y = mp_obj_get_int(args[9]);
    int32_t left_w = mp_obj_get_int(args[10]);
    int32_t middle_w = mp_obj_get_int(args[11]);
    int32_t floor_h = mp_obj_get_int(args[12]);
    int32_t wall_h = mp_obj_get_int(args[13]);
    int32_t bow_w = mp_obj_get_int(args[14]);
    int32_t bow_h = mp_obj_get_int(args[15]);
    int32_t left_offset_x = mp_obj_get_int(args[16]);
    int32_t right_offset_x = mp_obj_get_int(args[17]);
    bool bow_enabled = mp_obj_is_true(args[18]);
    int32_t bow_chance = mp_obj_get_int(args[19]);
    int32_t bow_min_gap = mp_obj_get_int(args[20]);
    int32_t shoot_interval = mp_obj_get_int(args[21]);
    int32_t door_speed = mp_obj_get_int(args[22]);
    int32_t platform_speed = mp_obj_get_int(args[23]);
    int32_t current_slot = mp_obj_get_int(args[24]);
    bool player_airborne = mp_obj_is_true(args[25]);
    int32_t left_slot = mp_obj_get_int(args[26]);
    int32_t right_slot = mp_obj_get_int(args[27]);
    int32_t default_wall_speed = mp_obj_get_int(args[28]);
    int32_t door_limit_y = mp_obj_get_int(args[29]);
    int32_t left_bow_index = mp_obj_get_int(args[30]);
    int32_t right_bow_index = mp_obj_get_int(args[31]);
    int32_t left_gap_off = mp_obj_get_int(args[32]);
    int32_t right_gap_off = mp_obj_get_int(args[33]);
    int32_t collect_seq_off = mp_obj_get_int(args[34]);

    if (env_stride < 28 || bow_stride < 24 || collect_stride < 16 || bow_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid map2 env dims"));
    }
    if (env_info.len < (size_t)env_stride || bow_info.len < (size_t)bow_stride * (size_t)bow_count || collect_info.len < (size_t)collect_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("map2 env buf too small"));
    }
    if (screen_h <= 0 || floor_h <= 0 || left_w <= 0 || middle_w <= 0) {
        return mp_const_false;
    }
    if (wall_h <= 0) {
        wall_h = screen_h;
    }
    if (bow_w <= 0) {
        bow_w = 32;
    }
    if (bow_h <= 0) {
        bow_h = 32;
    }
    if (door_speed < 0) {
        door_speed = 0;
    }
    if (platform_speed < 1) {
        platform_speed = 1;
    }
    if (default_wall_speed < 1) {
        default_wall_speed = 1;
    }
    if (door_limit_y <= 0) {
        door_limit_y = screen_h;
    }

    uint8_t *env_buf = (uint8_t *)env_info.buf;
    uint8_t *bow_buf = (uint8_t *)bow_info.buf;
    uint8_t *collect_buf = (uint8_t *)collect_info.buf;
    env_buf[kMap2EnvLeftWrappedOff] = 0u;
    env_buf[kMap2EnvRightWrappedOff] = 0u;
    env_buf[kMap2EnvPlayerDeathOff] = 0u;

    int32_t left_y = lgfx_rd_i16(env_buf + kMap2EnvFloorLeftYOff);
    int32_t right_y = lgfx_rd_i16(env_buf + kMap2EnvFloorRightYOff);
    bool lever_running = env_buf[kMap2EnvLeverRunningOff] != 0u;
    int32_t wall_speed = lgfx_rd_i16(env_buf + kMap2EnvWallSpeedOff);
    if (wall_speed < 1) {
        wall_speed = default_wall_speed;
    }

    if (lever_running) {
        int32_t wall_scroll_y = lgfx_rd_i16(env_buf + kMap2EnvWallScrollOff) + wall_speed;
        if (wall_h > 0) {
            wall_scroll_y %= wall_h;
        }
        lgfx_wr_i16(env_buf + kMap2EnvWallScrollOff, wall_scroll_y);

        left_y += platform_speed;
        if (!player_airborne && current_slot == left_slot && left_y >= screen_h) {
            env_buf[kMap2EnvPlayerDeathOff] = 1u;
        }
        if (left_y > screen_h) {
            left_y = -floor_h;
            env_buf[kMap2EnvLeftWrappedOff] = 1u;
        }

        right_y -= platform_speed;
        if (!player_airborne && current_slot == right_slot && right_y < 0) {
            env_buf[kMap2EnvPlayerDeathOff] = 1u;
        }
        if (right_y + floor_h < 0) {
            right_y = screen_h;
            env_buf[kMap2EnvRightWrappedOff] = 1u;
        }

        lgfx_wr_i16(env_buf + kMap2EnvFloorLeftYOff, left_y);
        lgfx_wr_i16(env_buf + kMap2EnvFloorRightYOff, right_y);

        if (env_buf[kMap2EnvDoorEnabledOff] != 0u) {
            int32_t door_y = lgfx_rd_i16(env_buf + kMap2EnvDoorYOff) + door_speed;
            lgfx_wr_i16(env_buf + kMap2EnvDoorYOff, door_y);
            if (door_y >= door_limit_y) {
                env_buf[kMap2EnvDoorEnabledOff] = 0u;
            }
        }

        if (env_buf[kMap2EnvLeftWrappedOff] && left_bow_index >= 0 && left_bow_index < bow_count) {
            map2_roll_floor_bow_native(env_buf, bow_buf + ((size_t)left_bow_index * (size_t)bow_stride), left_slot, left_gap_off, bow_enabled, bow_min_gap, bow_chance, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x, shoot_interval);
        }
        if (env_buf[kMap2EnvRightWrappedOff] && right_bow_index >= 0 && right_bow_index < bow_count) {
            map2_roll_floor_bow_native(env_buf, bow_buf + ((size_t)right_bow_index * (size_t)bow_stride), right_slot, right_gap_off, bow_enabled, bow_min_gap, bow_chance, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x, shoot_interval);
        }
        int32_t collect_seq = lgfx_rd_i16(collect_buf + collect_seq_off) & kMap2CollectSeqMask;
        if (env_buf[kMap2EnvLeftWrappedOff]) {
            collect_seq |= kMap2CollectReqLeft;
        }
        if (env_buf[kMap2EnvRightWrappedOff]) {
            collect_seq |= kMap2CollectReqRight;
        }
        lgfx_wr_i16(collect_buf + collect_seq_off, collect_seq);
    }

    if (left_bow_index >= 0 && left_bow_index < bow_count) {
        map2_update_bound_bow_position(bow_buf + ((size_t)left_bow_index * (size_t)bow_stride), left_slot, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x);
    }
    if (right_bow_index >= 0 && right_bow_index < bow_count) {
        map2_update_bound_bow_position(bow_buf + ((size_t)right_bow_index * (size_t)bow_stride), right_slot, floor_x, floor_y, left_w, middle_w, left_y, right_y, bow_w, bow_h, left_offset_x, right_offset_x);
    }
    return mp_const_true;
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_map2_environment_native_obj, 35, 35, lgfx_update_map2_environment_native);

static mp_obj_t lgfx_update_map2_elevator_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 44 && n_args != 51 && n_args != 60) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 44, 51 or 60 args"));
    }

    mp_buffer_info_t bow_info;
    mp_buffer_info_t arrow_info;
    mp_buffer_info_t swap_info;
    mp_buffer_info_t result_info;
    mp_buffer_info_t collect_info;
    mp_buffer_info_t star_info;
    collect_info.buf = nullptr;
    collect_info.len = 0;
    star_info.buf = nullptr;
    star_info.len = 0;
    mp_get_buffer_raise(args[0], &bow_info, MP_BUFFER_RW);
    mp_int_t bow_stride = mp_obj_get_int(args[1]);
    mp_int_t bow_count = mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &arrow_info, MP_BUFFER_RW);
    mp_int_t arrow_stride = mp_obj_get_int(args[4]);
    mp_int_t arrow_count = mp_obj_get_int(args[5]);
    mp_get_buffer_raise(args[6], &swap_info, MP_BUFFER_RW);
    mp_int_t swap_stride = mp_obj_get_int(args[7]);
    mp_get_buffer_raise(args[8], &result_info, MP_BUFFER_RW);
    mp_int_t result_stride = mp_obj_get_int(args[9]);
    int32_t player_x = mp_obj_get_int(args[10]);
    int32_t player_y = mp_obj_get_int(args[11]);
    mp_int_t player_w = mp_obj_get_int(args[12]);
    mp_int_t player_h = mp_obj_get_int(args[13]);
    bool btn_b_down = mp_obj_is_true(args[14]);
    bool btn_y_down = mp_obj_is_true(args[15]);
    mp_int_t screen_w = mp_obj_get_int(args[16]);
    mp_int_t screen_h = mp_obj_get_int(args[17]);
    mp_int_t floor_x = mp_obj_get_int(args[18]);
    mp_int_t floor_y = mp_obj_get_int(args[19]);
    mp_int_t left_w = mp_obj_get_int(args[20]);
    mp_int_t middle_w = mp_obj_get_int(args[21]);
    mp_int_t right_w = mp_obj_get_int(args[22]);
    mp_int_t floor_h = mp_obj_get_int(args[23]);
    mp_int_t left_wall_x = mp_obj_get_int(args[24]);
    mp_int_t right_wall_x = mp_obj_get_int(args[25]);
    mp_int_t wall_strip_w = mp_obj_get_int(args[26]);
    mp_int_t min_player_x = mp_obj_get_int(args[27]);
    mp_int_t max_player_x = mp_obj_get_int(args[28]);
    mp_int_t gravity = mp_obj_get_int(args[29]);
    mp_int_t max_fall_speed = mp_obj_get_int(args[30]);
    mp_int_t death_y = mp_obj_get_int(args[31]);
    mp_int_t bow_w = mp_obj_get_int(args[32]);
    mp_int_t bow_h = mp_obj_get_int(args[33]);
    mp_int_t shoot_interval = mp_obj_get_int(args[34]);
    mp_int_t fire_frame = mp_obj_get_int(args[35]);
    mp_int_t shoot_frames = mp_obj_get_int(args[36]);
    mp_int_t frame_hold = mp_obj_get_int(args[37]);
    mp_int_t arrow_speed = mp_obj_get_int(args[38]);
    mp_int_t arrow_w = mp_obj_get_int(args[39]);
    mp_int_t arrow_h = mp_obj_get_int(args[40]);
    mp_int_t cull_margin = mp_obj_get_int(args[41]);
    mp_int_t left_y = mp_obj_get_int(args[42]);
    mp_int_t right_y = mp_obj_get_int(args[43]);
    mp_int_t collect_stride = 0;
    mp_int_t collect_w = 32;
    mp_int_t collect_h = 32;
    mp_int_t collect_local_x = 32;
    mp_int_t collect_local_y = -32;
    mp_int_t collect_total = 5;
    mp_int_t star_stride = 0;
    bool star_enabled = false;
    mp_int_t star_w = 16;
    mp_int_t star_h = 16;
    mp_int_t star_speed = 3;
    mp_int_t star_spawn_frames = 150;
    mp_int_t lever_x = 144;
    mp_int_t lever_w = 32;
    if (n_args == 51 || n_args == 60) {
        mp_get_buffer_raise(args[44], &collect_info, MP_BUFFER_RW);
        collect_stride = mp_obj_get_int(args[45]);
        collect_w = mp_obj_get_int(args[46]);
        collect_h = mp_obj_get_int(args[47]);
        collect_local_x = mp_obj_get_int(args[48]);
        collect_local_y = mp_obj_get_int(args[49]);
        collect_total = mp_obj_get_int(args[50]);
    }
    if (n_args == 60) {
        mp_get_buffer_raise(args[51], &star_info, MP_BUFFER_RW);
        star_stride = mp_obj_get_int(args[52]);
        star_enabled = mp_obj_is_true(args[53]);
        star_w = mp_obj_get_int(args[54]);
        star_h = mp_obj_get_int(args[55]);
        star_speed = mp_obj_get_int(args[56]);
        star_spawn_frames = mp_obj_get_int(args[57]);
        lever_x = mp_obj_get_int(args[58]);
        lever_w = mp_obj_get_int(args[59]);
    }

    if (bow_stride < 24 || arrow_stride < 16 || swap_stride < 28 || result_stride < 16 || bow_count < 0 || arrow_count < 0 || ((n_args == 51 || n_args == 60) && collect_stride < 16) || (n_args == 60 && star_stride < 16)) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid map2 native dims"));
    }
    if (bow_info.len < (size_t)bow_stride * (size_t)bow_count || arrow_info.len < (size_t)arrow_stride * (size_t)arrow_count || swap_info.len < (size_t)swap_stride || result_info.len < (size_t)result_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("map2 native buf too small"));
    }
    if ((n_args == 51 || n_args == 60) && collect_info.len < (size_t)collect_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("map2 collect buf too small"));
    }
    if (n_args == 60 && star_info.len < (size_t)star_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("map2 star buf too small"));
    }
    if (screen_w <= 0 || screen_h <= 0 || player_w <= 0 || player_h <= 0) {
        return mp_const_false;
    }
    if (gravity < 1) {
        gravity = 1;
    }
    if (max_fall_speed < gravity) {
        max_fall_speed = gravity;
    }
    if (bow_w <= 0) {
        bow_w = 32;
    }
    if (bow_h <= 0) {
        bow_h = 32;
    }
    if (arrow_w <= 0) {
        arrow_w = 16;
    }
    if (arrow_h <= 0) {
        arrow_h = 16;
    }
    if (wall_strip_w < 1) {
        wall_strip_w = 1;
    }
    if (left_w < 1 || middle_w < 1 || right_w < 1 || floor_h < 1) {
        return mp_const_false;
    }

    uint8_t *bow_buf = (uint8_t *)bow_info.buf;
    uint8_t *arrow_buf = (uint8_t *)arrow_info.buf;
    uint8_t *swap_buf = (uint8_t *)swap_info.buf;
    uint8_t *result_buf = (uint8_t *)result_info.buf;
    uint8_t *collect_buf = (n_args == 51 || n_args == 60) ? (uint8_t *)collect_info.buf : nullptr;
    uint8_t *star_buf = n_args == 60 ? (uint8_t *)star_info.buf : nullptr;
    memset(result_buf, 0, (size_t)result_stride);
    lgfx_wr_i16(result_buf + 0, player_x);
    lgfx_wr_i16(result_buf + 2, player_y);
    lgfx_wr_i16(result_buf + 6, -1);

    for (int32_t i = 0; i < bow_count; ++i) {
        uint8_t *bow = bow_buf + ((size_t)i * (size_t)bow_stride);
        if (lgfx_rd_i16(bow + 4) <= 0) {
            lgfx_wr_i16(bow + 4, bow_w);
        }
        if (lgfx_rd_i16(bow + 6) <= 0) {
            lgfx_wr_i16(bow + 6, bow_h);
        }
    }

    map2_update_swap(bow_buf, bow_stride, bow_count, arrow_buf, arrow_stride, arrow_count, star_buf, swap_buf, result_buf, &player_x, &player_y, player_w, player_h, btn_b_down, btn_y_down, screen_w, screen_h, floor_x, floor_y, left_w, middle_w, right_w, left_y, right_y, min_player_x, max_player_x);
    lgfx_wr_i16(result_buf + 0, player_x);
    lgfx_wr_i16(result_buf + 2, player_y);

    for (int32_t i = 0; i < bow_count; ++i) {
        uint8_t *bow = bow_buf + ((size_t)i * (size_t)bow_stride);
        map2_update_free_bow_physics(bow, floor_x, floor_y, left_w, middle_w, right_w, floor_h, left_y, right_y, screen_h, gravity, max_fall_speed, death_y, shoot_interval);
        map2_update_bow_actor(bow, arrow_buf, arrow_stride, arrow_count, shoot_interval, fire_frame, shoot_frames, frame_hold, arrow_speed, arrow_w, arrow_h);
    }

    map2_update_arrows(bow_buf, bow_stride, bow_count, arrow_buf, arrow_stride, arrow_count, result_buf, player_x, player_y, player_w, player_h, screen_w, screen_h, floor_x, floor_y, left_w, middle_w, right_w, floor_h, left_wall_x, right_wall_x, wall_strip_w, left_y, right_y, cull_margin);
    if (collect_buf) {
        map2_update_collectible(collect_buf, bow_buf, bow_stride, bow_count, player_x, player_y, player_w, player_h, floor_x, floor_y, left_w, middle_w, left_y, right_y, collect_w, collect_h, collect_local_x, collect_local_y, collect_total);
    }
    if (star_buf && star_enabled) {
        map2_update_star(star_buf, bow_buf, bow_stride, bow_count, result_buf, player_x, player_y, player_w, player_h, screen_h, floor_x, floor_y, left_w, middle_w, right_w, floor_h, left_y, right_y, lever_x, lever_w, star_spawn_frames, star_speed, star_w, star_h);
    }
    map2_check_player_bow_hit(bow_buf, bow_stride, bow_count, result_buf, player_x, player_y, player_w, player_h, screen_h);
    return mp_const_true;
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_map2_elevator_native_obj, 44, 60, lgfx_update_map2_elevator_native);

#endif
