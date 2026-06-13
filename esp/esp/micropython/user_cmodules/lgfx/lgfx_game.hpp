#pragma once

#include <stdint.h>

constexpr int32_t LGFX_OBJECT_RENDER_STRIDE = 12;
constexpr int32_t LGFX_OBJECT_STATE_STRIDE = 20;
constexpr int32_t LGFX_OBJECT_SOLID_STRIDE = 8;
constexpr int32_t LGFX_ENEMY_ROW_STRIDE = 12;
constexpr int32_t LGFX_ENEMY_STATE_STRIDE = 8;
constexpr int32_t LGFX_BULLET_STRIDE = 16;
constexpr int32_t LGFX_MONK_ORB_NATIVE_STRIDE = 16;

constexpr uint16_t LGFX_OBJECT_STATE_FLAG_VISIBLE = 1u;
constexpr uint16_t LGFX_OBJECT_STATE_FLAG_SOLID = 2u;
constexpr uint16_t LGFX_OBJECT_STATE_FLAG_SWAPPABLE = 4u;
constexpr uint16_t LGFX_OBJECT_STATE_FLAG_GRAVITY = 8u;
constexpr uint16_t LGFX_OBJECT_STATE_FLAG_SPECIAL_RENDER = 16u;

static inline int16_t lgfx_rd_i16(const uint8_t *p) {
    return (int16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static inline uint16_t lgfx_rd_u16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static inline void lgfx_wr_i16(uint8_t *p, int32_t v) {
    if (v < -32768) v = -32768;
    if (v > 32767) v = 32767;
    uint16_t uv = (uint16_t)((int16_t)v);
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
}

static inline void lgfx_wr_u16(uint8_t *p, uint32_t v) {
    uint16_t uv = (uint16_t)(v & 0xFFFFu);
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
}

static inline int32_t lgfx_clamp_i32(int32_t v, int32_t lo, int32_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static inline int32_t lgfx_move_toward_i32(int32_t curr_v, int32_t target_v, int32_t speed_px) {
    int32_t step = speed_px < 1 ? 1 : speed_px;
    int32_t delta = target_v - curr_v;
    if (delta > 0) {
        curr_v += delta < step ? delta : step;
    } else if (delta < 0) {
        int32_t mag = -delta;
        curr_v -= mag < step ? mag : step;
    }
    return curr_v;
}