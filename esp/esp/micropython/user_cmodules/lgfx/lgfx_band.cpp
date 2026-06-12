#if !defined(NO_QSTR)

#include <stdint.h>
#include "esp_cache.h"
#include "esp_timer.h"

extern "C" {
#include "py/obj.h"
#include "py/runtime.h"
#include "py/mphal.h"
}

#include "lgfx_shared.hpp"

#ifndef LGFX_MONK_ATTACK_DEBUG_LOG
#define LGFX_MONK_ATTACK_DEBUG_LOG 0
#endif

#if LGFX_MONK_ATTACK_DEBUG_LOG
#define LGFX_MONK_ATTACK_LOGF(...) mp_printf(&mp_plat_print, __VA_ARGS__)
#else
#define LGFX_MONK_ATTACK_LOGF(...) do {} while (0)
#endif


static void copy_far_band(uint8_t *dst, int32_t dst_w, int32_t band_y, int32_t band_h, const uint8_t *far) {
    size_t row_bytes = (size_t)dst_w * 2u;
    for (int32_t y = 0; y < band_h; ++y) {
        memcpy(dst + ((size_t)y * row_bytes), far + (((size_t)(band_y + y) * (size_t)dst_w) * 2u), row_bytes);
    }
}

static inline bool tile_id_is_opaque(uint8_t tid) {
    switch (tid) {
        case 2:
        case 10:
        case 24:
        case 26:
        case 28:
        case 29:
        case 30:
        case 31:
        case 36:
        case 41:
        case 42:
        case 43:
        case 44:
        case 45:
        case 46:
        case 49:
        case 50:
        case 51:
        case 52:
        case 53:
        case 57:
        case 58:
        case 59:
        case 60:
        case 61:
        case 63:
            return true;
        default:
            return false;
    }
}

static void compose_tilemap_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    const uint8_t *tileset,
    size_t tileset_len,
    int32_t tile_size,
    int32_t tileset_w,
    int32_t transparent_key
) {
    if (!tilemap || !tileset || dst_w <= 0 || dst_h <= 0 || map_w <= 0 || map_h <= 0 || tile_size <= 0 || tileset_w <= 0) {
        return;
    }
    size_t tile_bytes = (size_t)tile_size * (size_t)tile_size * 2u;
    size_t tile_count = tile_bytes ? (tileset_len / tile_bytes) : 0u;
    size_t tileset_cols = (size_t)tileset_w / (size_t)tile_size;
    if (tile_count == 0 || tileset_cols == 0) {
        return;
    }

    int32_t start_col = camera_x / tile_size;
    int32_t end_col = (camera_x + dst_w - 1) / tile_size;
    int32_t start_row = band_top / tile_size;
    int32_t end_row = (band_top + dst_h - 1) / tile_size;
    if (start_col < 0) start_col = 0;
    if (start_row < 0) start_row = 0;
    if (end_col >= map_w) end_col = map_w - 1;
    if (end_row >= map_h) end_row = map_h - 1;
    if (end_col < start_col || end_row < start_row) return;

    for (int32_t r = start_row; r <= end_row; ++r) {
        const uint8_t *map_row = tilemap + ((size_t)r * (size_t)map_w);
        for (int32_t c = start_col; c <= end_col; ++c) {
            uint8_t tid = map_row[c];
            if (tid == 0u) continue;
            size_t tile_idx = (size_t)tid - 1u;
            if (tile_idx >= tile_count) continue;

            int32_t dx = (c * tile_size) - camera_x;
            int32_t dy = (r * tile_size) - band_top;
            int32_t src_x0 = 0;
            int32_t src_y0 = 0;
            int32_t vis_w = tile_size;
            int32_t vis_h = tile_size;
            if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
            if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
            if (dx + vis_w > dst_w) vis_w = dst_w - dx;
            if (dy + vis_h > dst_h) vis_h = dst_h - dy;
            if (vis_w <= 0 || vis_h <= 0) continue;

            size_t atlas_col = tile_idx % tileset_cols;
            size_t atlas_row = tile_idx / tileset_cols;
            size_t tile_px_x = atlas_col * (size_t)tile_size;
            size_t tile_px_y = atlas_row * (size_t)tile_size;
            size_t src_row_base = ((tile_px_y + (size_t)src_y0) * (size_t)tileset_w + tile_px_x + (size_t)src_x0) * 2u;
            size_t src_stride = (size_t)tileset_w * 2u;
            size_t copy_bytes = (size_t)vis_w * 2u;
            bool opaque_tile = tile_id_is_opaque(tid);
            for (int32_t y = 0; y < vis_h; ++y) {
                const uint8_t *src_row = tileset + src_row_base + ((size_t)y * src_stride);
                uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
                if (transparent_key < 0 || opaque_tile) {
                    memcpy(dst_row, src_row, copy_bytes);
                } else {
                    for (int32_t x = 0; x < vis_w; ++x) {
                        size_t b = (size_t)x * 2u;
                        uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                        if (px != (uint16_t)transparent_key) {
                            dst_row[b] = src_row[b];
                            dst_row[b + 1] = src_row[b + 1];
                        }
                    }
                }
            }
        }
    }
}

static void compose_atlas_region_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    int16_t wx,
    int16_t wy,
    const uint8_t *atlas,
    int32_t atlas_w,
    int32_t atlas_h,
    int32_t src_x,
    int32_t src_y,
    int32_t src_w,
    int32_t src_h,
    int32_t transparent_key
) {
    if (!atlas || atlas_w <= 0 || atlas_h <= 0 || src_w <= 0 || src_h <= 0) {
        return;
    }
    if (src_x < 0 || src_y < 0 || src_x + src_w > atlas_w || src_y + src_h > atlas_h) {
        return;
    }

    int32_t dx = (int32_t)wx - camera_x;
    int32_t dy = (int32_t)wy - band_top;
    int32_t src_x0 = 0;
    int32_t src_y0 = 0;
    int32_t vis_w = src_w;
    int32_t vis_h = src_h;
    if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
    if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
    if (dx + vis_w > dst_w) vis_w = dst_w - dx;
    if (dy + vis_h > dst_h) vis_h = dst_h - dy;
    if (vis_w <= 0 || vis_h <= 0) {
        return;
    }

    size_t atlas_row_bytes = (size_t)atlas_w * 2u;
    size_t src_row_base = ((size_t)(src_y + src_y0) * (size_t)atlas_w + (size_t)(src_x + src_x0)) * 2u;
    size_t copy_bytes = (size_t)vis_w * 2u;
    for (int32_t y = 0; y < vis_h; ++y) {
        const uint8_t *src_row = atlas + src_row_base + ((size_t)y * atlas_row_bytes);
        uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
        if (transparent_key < 0) {
            memcpy(dst_row, src_row, copy_bytes);
        } else {
            for (int32_t x = 0; x < vis_w; ++x) {
                size_t b = (size_t)x * 2u;
                uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                if (px != (uint16_t)transparent_key) {
                    dst_row[b] = src_row[b];
                    dst_row[b + 1] = src_row[b + 1];
                }
            }
        }
    }
}

static void compose_objects_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *objbuf,
    int32_t obj_stride,
    int32_t object_count,
    const uint8_t *atlas,
    int32_t atlas_w,
    int32_t atlas_h,
    int32_t transparent_key
) {
    if (!objbuf || !atlas || object_count <= 0 || obj_stride < 12 || atlas_w <= 0 || atlas_h <= 0) return;
    size_t atlas_row_bytes = (size_t)atlas_w * 2u;
    for (int32_t i = 0; i < object_count; ++i) {
        const uint8_t *ob = objbuf + ((size_t)i * (size_t)obj_stride);
        int16_t wx = (int16_t)((uint16_t)ob[0] | ((uint16_t)ob[1] << 8));
        int16_t wy = (int16_t)((uint16_t)ob[2] | ((uint16_t)ob[3] << 8));
        int32_t src_x = (uint16_t)ob[4] | ((uint16_t)ob[5] << 8);
        int32_t src_y = (uint16_t)ob[6] | ((uint16_t)ob[7] << 8);
        int32_t src_w = (uint16_t)ob[8] | ((uint16_t)ob[9] << 8);
        int32_t src_h = (uint16_t)ob[10] | ((uint16_t)ob[11] << 8);
        if (src_w <= 0 || src_h <= 0) continue;
        if (src_x < 0 || src_y < 0 || src_x + src_w > atlas_w || src_y + src_h > atlas_h) continue;

        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        int32_t src_x0 = 0;
        int32_t src_y0 = 0;
        int32_t vis_w = src_w;
        int32_t vis_h = src_h;
        if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
        if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
        if (dx + vis_w > dst_w) vis_w = dst_w - dx;
        if (dy + vis_h > dst_h) vis_h = dst_h - dy;
        if (vis_w <= 0 || vis_h <= 0) continue;

        size_t src_row_base = ((size_t)(src_y + src_y0) * (size_t)atlas_w + (size_t)(src_x + src_x0)) * 2u;
        size_t copy_bytes = (size_t)vis_w * 2u;
        for (int32_t y = 0; y < vis_h; ++y) {
            const uint8_t *src_row = atlas + src_row_base + ((size_t)y * atlas_row_bytes);
            uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
            if (transparent_key < 0) {
                memcpy(dst_row, src_row, copy_bytes);
            } else {
                for (int32_t x = 0; x < vis_w; ++x) {
                    size_t b = (size_t)x * 2u;
                    uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                    if (px != (uint16_t)transparent_key) {
                        dst_row[b] = src_row[b];
                        dst_row[b + 1] = src_row[b + 1];
                    }
                }
            }
        }
    }
}

static constexpr int32_t kMonkOrbOrbitSrcX = 16;
static constexpr int32_t kMonkOrbActionSrcX = 32;
static constexpr int32_t kMonkOrbSrcY = 112;
static constexpr int32_t kMonkOrbW = 16;
static constexpr int32_t kMonkOrbH = 16;
static constexpr int32_t kSwapPreviewSrcX = 0;
static constexpr int32_t kSwapPreviewSrcY = 128;
static constexpr int32_t kSwapPreviewW = 32;
static constexpr int32_t kSwapPreviewH = 32;
static constexpr int32_t kMonkOrbRadius = 28;
static constexpr int32_t kMonkOrbPulseRadius = 128;
static constexpr int32_t kMonkOrbPulseExpandFrames = 60;
static constexpr int32_t kMonkOrbPulseHoldFrames = 40;
static constexpr int32_t kMonkOrbPulseShrinkFrames = 60;
static constexpr int32_t kMonkOrbPulseDoubleHoldFrames = 20;
static constexpr int32_t kMonkOrbPulseDoubleMidShrinkFrames = 45;
static constexpr int32_t kMonkOrbPulseDoubleReexpandFrames = 45;
static constexpr int32_t kMonkOrbPulseStaggerDelay = 12;
static constexpr int32_t kMonkOrbPulseStaggerMaxDelay = 24;
static constexpr int32_t kMonkAttackDiveTopY = 0;
static constexpr int32_t kMonkAttackDiveDropY = 160;
static constexpr int32_t kMonkOrbFinalMode = 9;
static constexpr int32_t kMonkOrbFinalPhaseOrbit = 7;
static constexpr int32_t kMonkOrbFinalPhaseLock = 8;
static constexpr int32_t kMonkOrbFinalPhaseRush = 9;
static constexpr int32_t kMonkOrbFinalPhaseReturn = 10;
static constexpr int32_t kMonkOrbFinalPhaseEject = 11;
static constexpr int32_t kMonkOrbFinalPhaseDeath = 12;
static constexpr int32_t kMonkOrbPlayerOrbitMode = 10;
static constexpr int32_t kMonkOrbFinalOrbitRadius = 44;
static constexpr int32_t kMonkOrbPlayerOrbitRadius = 36;
static constexpr int32_t kMonkOrbFinalPrepareFrames = 48;
static constexpr int32_t kMonkOrbFinalDeathFrames = 12;
static constexpr int32_t kMonkOrbFinalDeathAnimFrames = 12;
static constexpr int32_t kMonkOrbFinalRushSpeed = 12;
static constexpr int32_t kMonkOrbFinalReturnSpeed = 12;
static constexpr int32_t kMonkOrbFinalDefaultMonkSpeedQ8 = 512;
static constexpr uint8_t kMonkOrbFinalSwapPending = 1;

static constexpr int32_t kEnemyStateShoot = 2;
static constexpr int32_t kEnemyStateDeath = 3;
static constexpr int32_t kBowDeathFrameCount = 5;
static constexpr uint8_t kMonkHoverStateFinalLocked = 0xFE;
static constexpr int32_t kMonkOrbFinalTableSize = 60;
static constexpr int32_t kMonkOrbFinalScale = 1024;
static const int16_t kMonkOrbFinalCos[kMonkOrbFinalTableSize] = {
    1024, 1018, 1002, 974, 935, 887, 828, 761, 685, 602,
    512, 416, 316, 213, 107, 0, -107, -213, -316, -416,
    -512, -602, -685, -761, -828, -887, -935, -974, -1002, -1018,
    -1024, -1018, -1002, -974, -935, -887, -828, -761, -685, -602,
    -512, -416, -316, -213, -107, 0, 107, 213, 316, 416,
    512, 602, 685, 761, 828, 887, 935, 974, 1002, 1018,
};
static const int16_t kMonkOrbFinalSin[kMonkOrbFinalTableSize] = {
    0, 107, 213, 316, 416, 512, 602, 685, 761, 828,
    887, 935, 974, 1002, 1018, 1024, 1018, 1002, 974, 935,
    887, 828, 761, 685, 602, 512, 416, 316, 213, 107,
    0, -107, -213, -316, -416, -512, -602, -685, -761, -828,
    -887, -935, -974, -1002, -1018, -1024, -1018, -1002, -974, -935,
    -887, -828, -761, -685, -602, -512, -416, -316, -213, -107,
};

static inline bool monk_orb_mode_uses_action_sprite(int32_t mode) {
    return mode == 2 || mode == 4 || mode == 5 || mode == kMonkOrbFinalMode;
}

static inline bool monk_orb_mode_is_pickable(int32_t mode) {
    return mode != 0xFF && mode != 3 && mode != 7 && mode != 8 && mode != kMonkOrbPlayerOrbitMode;
}

static inline int32_t lgfx_band_abs_i32(int32_t v) {
    return v < 0 ? -v : v;
}

static void compose_monk_orb_sprite_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    int32_t wx,
    int32_t wy,
    int32_t orb_mode,
    const uint8_t *orb_atlas,
    int32_t orb_atlas_w,
    int32_t orb_atlas_h,
    int32_t transparent_key
) {
    if (!orb_atlas || orb_atlas_w <= 0 || orb_atlas_h <= 0) {
        return;
    }
    compose_atlas_region_band(
        dst,
        dst_w,
        dst_h,
        camera_x,
        band_top,
        (int16_t)wx,
        (int16_t)wy,
        orb_atlas,
        orb_atlas_w,
        orb_atlas_h,
        monk_orb_mode_uses_action_sprite(orb_mode) ? kMonkOrbActionSrcX : kMonkOrbOrbitSrcX,
        kMonkOrbSrcY,
        kMonkOrbW,
        kMonkOrbH,
        transparent_key
    );
}

static void compose_enemy_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *enemy_desc,
    int32_t enemy_stride,
    int32_t enemy_count,
    const uint8_t *enemy_sheet,
    int32_t enemy_sheet_w,
    int32_t enemy_sheet_h,
    const uint8_t *enemy_monk_sheet,
    int32_t enemy_monk_frame_w,
    int32_t enemy_monk_frame_h,
    int32_t enemy_monk_frame_count,
    int32_t enemy_monk_frame_hold,
    const uint8_t *enemy_monk_orb_atlas,
    int32_t enemy_monk_orb_atlas_w,
    int32_t enemy_monk_orb_atlas_h,
    int32_t enemy_key,
    int32_t enemy_frame_hold
) {
    if (!enemy_desc || enemy_count <= 0 || enemy_stride < 10) {
        return;
    }
    (void)enemy_monk_orb_atlas;
    (void)enemy_monk_orb_atlas_w;
    (void)enemy_monk_orb_atlas_h;
    const int32_t bow_frame_w = 32;
    const int32_t bow_frame_h = 32;
    bool bow_ready = enemy_sheet && enemy_sheet_w >= (10 * bow_frame_w) && enemy_sheet_h >= (3 * bow_frame_h);
    bool monk_ready = enemy_monk_sheet && enemy_monk_frame_w > 0 && enemy_monk_frame_h > 0 && enemy_monk_frame_count > 0;
    if (!bow_ready && !monk_ready) {
        return;
    }
    if (enemy_frame_hold < 1) {
        enemy_frame_hold = 1;
    }
    if (enemy_monk_frame_hold < 1) {
        enemy_monk_frame_hold = 1;
    }

    for (int32_t i = 0; i < enemy_count; ++i) {
        const uint8_t *eb = enemy_desc + ((size_t)i * (size_t)enemy_stride);
        int16_t wx = (int16_t)((uint16_t)eb[0] | ((uint16_t)eb[1] << 8));
        int16_t wy = (int16_t)((uint16_t)eb[2] | ((uint16_t)eb[3] << 8));
        int32_t anim_counter = (uint16_t)eb[4] | ((uint16_t)eb[5] << 8);
        int32_t enemy_state = (int32_t)eb[6];
        bool face_right = eb[7] != 0;
        int32_t enemy_type = (int32_t)eb[8];

        if (enemy_type == 1) {
            if (!monk_ready) {
                continue;
            }
            int32_t dx = (int32_t)wx - camera_x;
            int32_t dy = (int32_t)wy - band_top;
            if (dx >= dst_w || (dx + enemy_monk_frame_w) <= 0 || dy >= dst_h || (dy + enemy_monk_frame_h) <= 0) {
                continue;
            }
            bool monk_death = enemy_state == kMonkOrbFinalPhaseDeath;
            int32_t monk_frame_idx = (anim_counter / enemy_monk_frame_hold) % enemy_monk_frame_count;
            if (monk_death) {
                int32_t death_anim_frames = kMonkOrbFinalDeathAnimFrames;
                if (death_anim_frames < enemy_monk_frame_count) {
                    death_anim_frames = enemy_monk_frame_count;
                }
                int32_t death_step = anim_counter;
                if (death_step < 0) death_step = 0;
                if (death_step >= death_anim_frames) death_step = death_anim_frames - 1;
                monk_frame_idx = (death_step * enemy_monk_frame_count) / death_anim_frames;
                if (monk_frame_idx < 0) monk_frame_idx = 0;
                if (monk_frame_idx >= enemy_monk_frame_count) monk_frame_idx = enemy_monk_frame_count - 1;
            }
            int32_t src_x = monk_frame_idx * enemy_monk_frame_w;
            int32_t src_y = monk_death ? enemy_monk_frame_h : 0;
            compose_atlas_region_band(
                dst,
                dst_w,
                dst_h,
                camera_x,
                band_top,
                wx,
                wy,
                enemy_monk_sheet,
                enemy_monk_frame_w * enemy_monk_frame_count,
                enemy_monk_frame_h * (monk_death ? 2 : 1),
                src_x,
                src_y,
                enemy_monk_frame_w,
                enemy_monk_frame_h,
                enemy_key
            );
            continue;
        }

        if (!bow_ready) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + bow_frame_w) <= 0 || dy >= dst_h || (dy + bow_frame_h) <= 0) {
            continue;
        }

        int32_t frame_idx = anim_counter / enemy_frame_hold;
        int32_t src_x = 0;
        int32_t src_y = bow_frame_h * 2;
        if (enemy_state == kEnemyStateShoot) {
            if (frame_idx > 9) {
                frame_idx = 9;
            }
            src_x = frame_idx * bow_frame_w;
            src_y = face_right ? 0 : bow_frame_h;
        } else if (enemy_state == kEnemyStateDeath) {
            if (enemy_sheet_h < (4 * bow_frame_h)) {
                continue;
            }
            if (frame_idx >= kBowDeathFrameCount) {
                frame_idx = kBowDeathFrameCount - 1;
            }
            src_x = (face_right ? frame_idx : (kBowDeathFrameCount + frame_idx)) * bow_frame_w;
            src_y = bow_frame_h * 3;
        } else {
            frame_idx %= 5;
            src_x = (face_right ? frame_idx : (5 + frame_idx)) * bow_frame_w;
        }

        compose_atlas_region_band(
            dst,
            dst_w,
            dst_h,
            camera_x,
            band_top,
            wx,
            wy,
            enemy_sheet,
            enemy_sheet_w,
            enemy_sheet_h,
            src_x,
            src_y,
            bow_frame_w,
            bow_frame_h,
            enemy_key
        );
    }
}

static void compose_sprite_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t dst_x,
    int32_t dst_y,
    const uint8_t *src,
    int32_t src_w,
    int32_t src_h,
    int32_t transparent_key
) {
    if (!src || dst_w <= 0 || dst_h <= 0 || src_w <= 0 || src_h <= 0) return;
    if (dst_x >= dst_w || dst_y >= dst_h || (dst_x + src_w) <= 0 || (dst_y + src_h) <= 0) return;
    int32_t src_x0 = 0;
    int32_t src_y0 = 0;
    int32_t dx = dst_x;
    int32_t dy = dst_y;
    int32_t vis_w = src_w;
    int32_t vis_h = src_h;
    if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
    if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
    if (dx + vis_w > dst_w) vis_w = dst_w - dx;
    if (dy + vis_h > dst_h) vis_h = dst_h - dy;
    if (vis_w <= 0 || vis_h <= 0) return;

    size_t copy_bytes = (size_t)vis_w * 2u;
    for (int32_t y = 0; y < vis_h; ++y) {
        const uint8_t *src_row = src + ((((size_t)(src_y0 + y) * (size_t)src_w) + (size_t)src_x0) * 2u);
        uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
        if (transparent_key < 0) {
            memcpy(dst_row, src_row, copy_bytes);
        } else {
            for (int32_t x = 0; x < vis_w; ++x) {
                size_t b = (size_t)x * 2u;
                uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                if (px != (uint16_t)transparent_key) {
                    dst_row[b] = src_row[b];
                    dst_row[b + 1] = src_row[b + 1];
                }
            }
        }
    }
}

static void compose_repeating_vertical_strip_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t band_top,
    int32_t dst_x,
    const uint8_t *src,
    int32_t src_w,
    int32_t src_h,
    int32_t src_x,
    int32_t strip_w,
    int32_t scroll_y,
    int32_t transparent_key
) {
    if (!src || dst_w <= 0 || dst_h <= 0 || src_w <= 0 || src_h <= 0 || strip_w <= 0) return;
    if (src_x < 0 || src_x + strip_w > src_w) return;
    if (dst_x >= dst_w || (dst_x + strip_w) <= 0) return;
    int32_t src_x0 = 0;
    int32_t dx = dst_x;
    int32_t vis_w = strip_w;
    if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
    if (dx + vis_w > dst_w) vis_w = dst_w - dx;
    if (vis_w <= 0) return;

    for (int32_t y = 0; y < dst_h; ++y) {
        int32_t sy = (band_top + y - scroll_y) % src_h;
        if (sy < 0) sy += src_h;
        const uint8_t *src_row = src + ((((size_t)sy * (size_t)src_w) + (size_t)(src_x + src_x0)) * 2u);
        uint8_t *dst_row = dst + ((((size_t)y * (size_t)dst_w) + (size_t)dx) * 2u);
        if (transparent_key < 0) {
            memcpy(dst_row, src_row, (size_t)vis_w * 2u);
        } else {
            for (int32_t x = 0; x < vis_w; ++x) {
                size_t b = (size_t)x * 2u;
                uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                if (px != (uint16_t)transparent_key) {
                    dst_row[b] = src_row[b];
                    dst_row[b + 1] = src_row[b + 1];
                }
            }
        }
    }
}

static void compose_elevator_scene_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t band_y,
    const uint8_t *far,
    const uint8_t *wall,
    int32_t wall_w,
    int32_t wall_h,
    const uint8_t *door,
    int32_t door_w,
    int32_t door_h,
    const uint8_t *floor,
    int32_t floor_w,
    int32_t floor_h,
    const uint8_t *object_atlas,
    int32_t object_atlas_w,
    int32_t object_atlas_h,
    int32_t lever_x,
    int32_t lever_y,
    int32_t lever_w,
    int32_t lever_h,
    int32_t lever_src_x,
    int32_t lever_src_y,
    int32_t floor_x,
    int32_t floor_y,
    int32_t floor_left_w,
    int32_t floor_middle_w,
    int32_t floor_left_y,
    int32_t floor_right_y,
    const uint8_t *sprite,
    int32_t sprite_w,
    int32_t sprite_h,
    int32_t sprite_x,
    int32_t sprite_y,
    int32_t sprite_key,
    int32_t wall_scroll_y,
    int32_t door_y,
    int32_t door_enabled,
    int32_t transparent_key,
    uint32_t *band_bg_us,
    uint32_t *band_tilemap_us,
    uint32_t *band_player_us
) {
    int64_t t0 = esp_timer_get_time();
    copy_far_band(dst, dst_w, band_y, dst_h, far);
    int64_t t1 = esp_timer_get_time();
    compose_repeating_vertical_strip_band(dst, dst_w, dst_h, band_y, 0, wall, wall_w, wall_h, 0, 32, wall_scroll_y, -1);
    compose_repeating_vertical_strip_band(dst, dst_w, dst_h, band_y, dst_w - 32, wall, wall_w, wall_h, 32, 32, wall_scroll_y, -1);
    if (door_enabled) {
        compose_sprite_band(dst, dst_w, dst_h, 32, door_y - band_y, door, door_w, door_h, transparent_key);
    }
    int32_t floor_right_w = floor_w - floor_left_w - floor_middle_w;
    if (floor_left_w > 0 && floor_middle_w > 0 && floor_right_w > 0) {
        compose_atlas_region_band(dst, dst_w, dst_h, 0, band_y, (int16_t)floor_x, (int16_t)floor_left_y, floor, floor_w, floor_h, 0, 0, floor_left_w, floor_h, -1);
        compose_atlas_region_band(dst, dst_w, dst_h, 0, band_y, (int16_t)(floor_x + floor_left_w), (int16_t)floor_y, floor, floor_w, floor_h, floor_left_w, 0, floor_middle_w, floor_h, -1);
        compose_atlas_region_band(dst, dst_w, dst_h, 0, band_y, (int16_t)(floor_x + floor_left_w + floor_middle_w), (int16_t)floor_right_y, floor, floor_w, floor_h, floor_left_w + floor_middle_w, 0, floor_right_w, floor_h, -1);
    } else {
        compose_sprite_band(dst, dst_w, dst_h, floor_x, floor_y - band_y, floor, floor_w, floor_h, -1);
    }
    compose_atlas_region_band(dst, dst_w, dst_h, 0, band_y, (int16_t)lever_x, (int16_t)lever_y, object_atlas, object_atlas_w, object_atlas_h, lever_src_x, lever_src_y, lever_w, lever_h, transparent_key);
    int64_t t2 = esp_timer_get_time();
    compose_sprite_band(dst, dst_w, dst_h, sprite_x, sprite_y - band_y, sprite, sprite_w, sprite_h, sprite_key);
    int64_t t3 = esp_timer_get_time();
    *band_bg_us += (uint32_t)(t1 - t0);
    *band_tilemap_us += (uint32_t)(t2 - t1);
    *band_player_us += (uint32_t)(t3 - t2);
}

static void compose_special_objects_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *special_desc,
    int32_t special_stride,
    int32_t special_count,
    const uint8_t *respawn_sheet,
    int32_t respawn_frame_w,
    int32_t respawn_frame_h,
    int32_t respawn_frame_count,
    const uint8_t *anchor_sheet,
    int32_t anchor_frame_w,
    int32_t anchor_frame_h,
    int32_t anchor_frame_count,
    const uint8_t *orb_atlas,
    int32_t orb_atlas_w,
    int32_t orb_atlas_h,
    int32_t special_key
) {
    if (!special_desc || special_count <= 0 || special_stride < 8) {
        return;
    }
    for (int32_t i = 0; i < special_count; ++i) {
        const uint8_t *sb = special_desc + ((size_t)i * (size_t)special_stride);
        int16_t wx = (int16_t)((uint16_t)sb[0] | ((uint16_t)sb[1] << 8));
        int16_t wy = (int16_t)((uint16_t)sb[2] | ((uint16_t)sb[3] << 8));
        int32_t kind = (int32_t)sb[4];
        int32_t frame_index = (int32_t)sb[5];
        int32_t aux0 = (int32_t)sb[6];
        int32_t aux1 = (int32_t)sb[7];
        const uint8_t *sheet = nullptr;
        int32_t frame_w = 0;
        int32_t frame_h = 0;
        int32_t frame_count = 0;
        if (kind == 0) {
            sheet = respawn_sheet;
            frame_w = respawn_frame_w;
            frame_h = respawn_frame_h;
            frame_count = respawn_frame_count;
        } else if (kind == 1) {
            sheet = anchor_sheet;
            frame_w = anchor_frame_w;
            frame_h = anchor_frame_h;
            frame_count = anchor_frame_count;
        } else if (kind == 2) {
            frame_w = kMonkOrbW;
            frame_h = kMonkOrbH;
            if (!orb_atlas || orb_atlas_w <= 0 || orb_atlas_h <= 0) {
                continue;
            }
            int32_t dx = (int32_t)wx - camera_x;
            int32_t dy = (int32_t)wy - band_top;
            if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
                continue;
            }
            compose_monk_orb_sprite_band(
                dst,
                dst_w,
                dst_h,
                camera_x,
                band_top,
                wx,
                wy,
                aux0,
                orb_atlas,
                orb_atlas_w,
                orb_atlas_h,
                special_key
            );
            continue;
        } else if (kind == 3) {
            int32_t sx = (int32_t)wx;
            int32_t sy = (int32_t)wy;
            int32_t ex = sx + (int32_t)((int8_t)frame_index);
            int32_t ey = sy + (int32_t)((int8_t)aux0);
            int32_t thickness = aux1 < 1 ? 1 : aux1;
            if (thickness > 6) thickness = 6;
            int32_t min_x = sx < ex ? sx : ex;
            int32_t max_x = sx > ex ? sx : ex;
            int32_t min_y = sy < ey ? sy : ey;
            int32_t max_y = sy > ey ? sy : ey;
            min_x -= thickness;
            max_x += thickness;
            min_y -= thickness;
            max_y += thickness;
            if (max_x < camera_x || min_x >= (camera_x + dst_w) || max_y < band_top || min_y >= (band_top + dst_h)) {
                continue;
            }
            int32_t steps = lgfx_band_abs_i32(ex - sx);
            int32_t dy_abs = lgfx_band_abs_i32(ey - sy);
            if (dy_abs > steps) steps = dy_abs;
            if (steps < 1) steps = 1;
            int32_t half = thickness / 2;
            for (int32_t step = 0; step <= steps; ++step) {
                int32_t px = sx + (((ex - sx) * step) / steps) - camera_x;
                int32_t py = sy + (((ey - sy) * step) / steps) - band_top;
                for (int32_t ty = 0; ty < thickness; ++ty) {
                    int32_t yy = py + ty - half;
                    if (yy < 0 || yy >= dst_h) continue;
                    for (int32_t tx = 0; tx < thickness; ++tx) {
                        int32_t xx = px + tx - half;
                        if (xx < 0 || xx >= dst_w) continue;
                        size_t off = (((size_t)yy * (size_t)dst_w) + (size_t)xx) * 2u;
                        dst[off] = 0u;
                        dst[off + 1] = 0u;
                    }
                }
            }
            continue;
        } else if (kind == 4) {
            continue;
        } else {
            continue;
        }
        if (!sheet || frame_w <= 0 || frame_h <= 0 || frame_count <= 0) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
            continue;
        }
        int32_t src_frame = frame_index;
        if (src_frame < 0) {
            src_frame = 0;
        }
        if (src_frame >= frame_count) {
            src_frame = frame_count - 1;
        }
        compose_atlas_region_band(
            dst,
            dst_w,
            dst_h,
            camera_x,
            band_top,
            wx,
            wy,
            sheet,
            frame_w * frame_count,
            frame_h,
            src_frame * frame_w,
            0,
            frame_w,
            frame_h,
            special_key
        );
    }
}

static void compose_swap_preview_underlay_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *special_desc,
    int32_t special_stride,
    int32_t special_count,
    const uint8_t *obj_atlas,
    int32_t obj_atlas_w,
    int32_t obj_atlas_h,
    int32_t object_key
) {
    if (!special_desc || special_count <= 0 || special_stride < 8 || !obj_atlas || obj_atlas_w <= 0 || obj_atlas_h <= 0) {
        return;
    }
    if ((kSwapPreviewSrcX + kSwapPreviewW) > obj_atlas_w || (kSwapPreviewSrcY + kSwapPreviewH) > obj_atlas_h) {
        return;
    }
    for (int32_t i = 0; i < special_count; ++i) {
        const uint8_t *sb = special_desc + ((size_t)i * (size_t)special_stride);
        if ((int32_t)sb[4] != 4) {
            continue;
        }
        int16_t wx = (int16_t)((uint16_t)sb[0] | ((uint16_t)sb[1] << 8));
        int16_t wy = (int16_t)((uint16_t)sb[2] | ((uint16_t)sb[3] << 8));
        int32_t target_w = (int32_t)sb[5];
        int32_t target_h = (int32_t)sb[6];
        if (target_w <= 0 || target_h <= 0) {
            continue;
        }
        int32_t draw_x = (int32_t)wx + (target_w / 2) - (kSwapPreviewW / 2);
        int32_t draw_y = (int32_t)wy + (target_h / 2) - (kSwapPreviewH / 2);
        compose_atlas_region_band(
            dst,
            dst_w,
            dst_h,
            camera_x,
            band_top,
            (int16_t)draw_x,
            (int16_t)draw_y,
            obj_atlas,
            obj_atlas_w,
            obj_atlas_h,
            kSwapPreviewSrcX,
            kSwapPreviewSrcY,
            kSwapPreviewW,
            kSwapPreviewH,
            object_key
        );
    }
}

static void compose_overlay_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *overlay_desc,
    int32_t overlay_stride,
    int32_t overlay_count,
    mp_obj_t overlay_frames_obj,
    int32_t overlay_key
) {
    if (!overlay_desc || overlay_count <= 0 || overlay_stride < 10) {
        return;
    }

    size_t frame_obj_count = 0;
    mp_obj_t *frame_objs = nullptr;
    mp_obj_get_array(overlay_frames_obj, &frame_obj_count, &frame_objs);
    if (frame_obj_count == 0 || frame_objs == nullptr) {
        return;
    }

    for (int32_t i = 0; i < overlay_count; ++i) {
        const uint8_t *ob = overlay_desc + ((size_t)i * (size_t)overlay_stride);
        int16_t wx = (int16_t)((uint16_t)ob[0] | ((uint16_t)ob[1] << 8));
        int16_t wy = (int16_t)((uint16_t)ob[2] | ((uint16_t)ob[3] << 8));
        int32_t frame_w = (uint16_t)ob[4] | ((uint16_t)ob[5] << 8);
        int32_t frame_h = (uint16_t)ob[6] | ((uint16_t)ob[7] << 8);
        int32_t frame_idx = (uint16_t)ob[8] | ((uint16_t)ob[9] << 8);
        if (frame_w <= 0 || frame_h <= 0 || frame_idx < 0 || (size_t)frame_idx >= frame_obj_count) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
            continue;
        }

        mp_buffer_info_t frame_info;
        mp_get_buffer_raise(frame_objs[frame_idx], &frame_info, MP_BUFFER_READ);
        size_t expected_len = (size_t)frame_w * (size_t)frame_h * 2u;
        if (frame_info.len < expected_len) {
            continue;
        }
        compose_sprite_band(
            dst,
            dst_w,
            dst_h,
            (int32_t)wx - camera_x,
            (int32_t)wy - band_top,
            (const uint8_t *)frame_info.buf,
            frame_w,
            frame_h,
            overlay_key
        );
    }
}

static void compose_scene_band(
    uint8_t *dst,
    int32_t screen_w,
    int32_t band_y,
    int32_t band_h,
    const uint8_t *far,
    int32_t camera_x,
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    const uint8_t *tileset,
    size_t tileset_len,
    int32_t tile_size,
    int32_t tileset_w,
    int32_t tile_key,
    const uint8_t *objbuf,
    int32_t obj_stride,
    int32_t object_count,
    const uint8_t *obj_atlas,
    int32_t obj_atlas_w,
    int32_t obj_atlas_h,
    int32_t object_key,
    const uint8_t *sprite,
    int32_t sprite_w,
    int32_t sprite_h,
    int32_t sprite_x,
    int32_t sprite_y,
    int32_t sprite_key,
    const uint8_t *overlay_desc,
    int32_t overlay_stride,
    int32_t overlay_count,
    mp_obj_t overlay_frames_obj,
    const uint8_t *special_desc,
    int32_t special_stride,
    int32_t special_count,
    const uint8_t *respawn_sheet,
    int32_t respawn_frame_w,
    int32_t respawn_frame_h,
    int32_t respawn_frame_count,
    const uint8_t *anchor_sheet,
    int32_t anchor_frame_w,
    int32_t anchor_frame_h,
    int32_t anchor_frame_count,
    int32_t overlay_key,
    const uint8_t *enemy_desc,
    int32_t enemy_stride,
    int32_t enemy_count,
    const uint8_t *enemy_sheet,
    int32_t enemy_sheet_w,
    int32_t enemy_sheet_h,
    const uint8_t *enemy_monk_sheet,
    int32_t enemy_monk_frame_w,
    int32_t enemy_monk_frame_h,
    int32_t enemy_monk_frame_count,
    int32_t enemy_monk_frame_hold,
    const uint8_t *enemy_monk_orb_atlas,
    int32_t enemy_monk_orb_atlas_w,
    int32_t enemy_monk_orb_atlas_h,
    int32_t enemy_key,
    int32_t enemy_frame_hold,
    bool disable_far,
    uint32_t *band_bg_us,
    uint32_t *band_tilemap_us,
    uint32_t *band_object_us,
    uint32_t *band_special_us,
    uint32_t *band_enemy_us,
    uint32_t *band_player_us
) {
    int64_t t0 = esp_timer_get_time();
    if (disable_far) {
        memset(dst, 0, (size_t)screen_w * (size_t)band_h * 2u);
    } else {
        copy_far_band(dst, screen_w, band_y, band_h, far);
    }
    int64_t t1 = esp_timer_get_time();
    compose_tilemap_band(dst, screen_w, band_h, camera_x, band_y, tilemap, map_w, map_h, tileset, tileset_len, tile_size, tileset_w, tile_key);
    int64_t t2 = esp_timer_get_time();
    compose_swap_preview_underlay_band(dst, screen_w, band_h, camera_x, band_y, special_desc, special_stride, special_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key);
    compose_objects_band(dst, screen_w, band_h, camera_x, band_y, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key);
    int64_t t3 = esp_timer_get_time();
    compose_enemy_band(dst, screen_w, band_h, camera_x, band_y, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold);
    int64_t t4 = esp_timer_get_time();
    compose_special_objects_band(dst, screen_w, band_h, camera_x, band_y, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, overlay_key);
    int64_t t5 = esp_timer_get_time();
    compose_overlay_band(dst, screen_w, band_h, camera_x, band_y, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, overlay_key);
    int64_t t6 = esp_timer_get_time();
    compose_sprite_band(dst, screen_w, band_h, sprite_x, sprite_y - band_y, sprite, sprite_w, sprite_h, sprite_key);
    int64_t t7 = esp_timer_get_time();
    *band_bg_us += (uint32_t)(t1 - t0);
    *band_tilemap_us += (uint32_t)(t2 - t1);
    *band_object_us += (uint32_t)(t3 - t2);
    *band_enemy_us += (uint32_t)(t4 - t3);
    *band_special_us += (uint32_t)((t5 - t4) + (t6 - t5));
    *band_player_us += (uint32_t)(t7 - t6);
}

static int64_t submit_band_start(
    uint8_t *buf,
    int32_t screen_w,
    int32_t band_y,
    int32_t band_h,
    bool *prev_swap,
    uint32_t *kick_us,
    uint32_t *sync_us,
    uint32_t *start_us,
    uint32_t *push_us
) {
    size_t len = (size_t)screen_w * (size_t)band_h * 2u;
    int64_t t0 = esp_timer_get_time();
    esp_err_t sync_ret = esp_cache_msync((void *)buf, len, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
    int64_t t1 = esp_timer_get_time();
    if (sync_ret != ESP_OK) {
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
    }
    *prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(false);
    int64_t t2 = esp_timer_get_time();
    lcd.pushImageDMA(0, band_y, screen_w, band_h, (const uint16_t *)buf);
    int64_t t3 = esp_timer_get_time();
    *sync_us += (uint32_t)(t1 - t0);
    *start_us += (uint32_t)(t2 - t1);
    *push_us += (uint32_t)(t3 - t2);
    *kick_us += (uint32_t)(t3 - t0);
    return t2;
}

static int64_t submit_band_wait(bool prev_swap, uint32_t *wait_us, uint32_t *wait_dma_us, uint32_t *end_us) {
    int64_t t0 = esp_timer_get_time();
    lcd.waitDMA();
    int64_t t1 = esp_timer_get_time();
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();
    int64_t t2 = esp_timer_get_time();
    *wait_dma_us += (uint32_t)(t1 - t0);
    *end_us += (uint32_t)(t2 - t1);
    *wait_us += (uint32_t)(t2 - t0);
    return t1;
}

typedef struct {
    bool active;
    bool prev_swap;
    int64_t wait_t0;
    int64_t dma_t0;
} lgfx_tail_wait_state_t;

static lgfx_tail_wait_state_t g_tail_wait_state = {false, false, 0, 0};

extern "C" {

mp_obj_t lgfx_band_pipeline_tail_wait(void) {
    if (!g_tail_wait_state.active) {
        mp_obj_t out[5] = {
            mp_obj_new_int(0),
            mp_obj_new_int(0),
            mp_obj_new_int(0),
            mp_obj_new_int(0),
            mp_obj_new_int(0),
        };
        return mp_obj_new_tuple(5, out);
    }
    int64_t t_enter = esp_timer_get_time();
    lcd.waitDMA();
    int64_t t_dma = esp_timer_get_time();
    lcd.setSwapBytes(g_tail_wait_state.prev_swap);
    lcd.endWrite();
    int64_t t_done = esp_timer_get_time();
    uint32_t total_wait_us = (uint32_t)(t_done - g_tail_wait_state.wait_t0);
    uint32_t residual_wait_us = (uint32_t)(t_done - t_enter);
    uint32_t residual_dma_wait_us = (uint32_t)(t_dma - t_enter);
    uint32_t end_us = (uint32_t)(t_done - t_dma);
    uint32_t tail_dma_elapsed_us = 0;
    if (g_tail_wait_state.dma_t0 > 0) {
        tail_dma_elapsed_us = (uint32_t)(t_dma - g_tail_wait_state.dma_t0);
    }
    g_tail_wait_state.active = false;
    mp_obj_t out[5] = {
        mp_obj_new_int_from_uint(total_wait_us),
        mp_obj_new_int_from_uint(residual_wait_us),
        mp_obj_new_int_from_uint(residual_dma_wait_us),
        mp_obj_new_int_from_uint(end_us),
        mp_obj_new_int_from_uint(tail_dma_elapsed_us),
    };
    return mp_obj_new_tuple(5, out);
}

static mp_obj_t lgfx_band_submit_probe_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 4) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 4 args"));
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[0], &bufinfo, MP_BUFFER_READ);
    mp_int_t w = mp_obj_get_int(args[1]);
    mp_int_t h = mp_obj_get_int(args[2]);
    mp_int_t band_h = mp_obj_get_int(args[3]);
    if (w <= 0 || h <= 0 || band_h <= 0 || band_h > h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t full_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf too small"));
    }

    const uint8_t *base = (const uint8_t *)bufinfo.buf;
    uint32_t total_kick_us = 0;
    uint32_t total_wait_us = 0;
    uint32_t band_count = 0;
    int64_t all_t0 = esp_timer_get_time();

    mp_printf(&mp_plat_print, "BAND_SUBMIT_PROBE_START w=%d h=%d band_h=%d\n", (int)w, (int)h, (int)band_h);

    int32_t y = 0;
    while (y < h) {
        int32_t bh = (int32_t)band_h;
        if (y + bh > h) {
            bh = h - y;
        }
        size_t band_len = (size_t)w * (size_t)bh * 2u;
        const uint16_t *pixels = (const uint16_t *)(base + ((size_t)y * (size_t)w * 2u));

        bool prev_swap = lcd.getSwapBytes();
        int64_t t0 = esp_timer_get_time();
        esp_err_t sync_ret = esp_cache_msync(
            (void *)pixels,
            band_len,
            ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
        );
        if (sync_ret != ESP_OK) {
            mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
        }
        lcd.startWrite();
        lcd.setSwapBytes(false);
        lcd.pushImageDMA(0, y, (int32_t)w, bh, pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.waitDMA();
        int64_t t2 = esp_timer_get_time();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();

        uint32_t kick_us = (uint32_t)(t1 - t0);
        uint32_t wait_us = (uint32_t)(t2 - t1);
        total_kick_us += kick_us;
        total_wait_us += wait_us;
        mp_printf(
            &mp_plat_print,
            "BAND_SUBMIT_PROBE band=%u y=%d h=%d kick_us=%u wait_us=%u total_us=%u\n",
            (unsigned)band_count,
            (int)y,
            (int)bh,
            (unsigned)kick_us,
            (unsigned)wait_us,
            (unsigned)(kick_us + wait_us)
        );

        ++band_count;
        y += bh;
    }

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_printf(
        &mp_plat_print,
        "BAND_SUBMIT_PROBE_TOTAL bands=%u kick_us=%u wait_us=%u total_us=%u\n",
        (unsigned)band_count,
        (unsigned)total_kick_us,
        (unsigned)total_wait_us,
        (unsigned)total_us
    );

    mp_obj_t out[4] = {
        mp_obj_new_int_from_uint(band_count),
        mp_obj_new_int_from_uint(total_kick_us),
        mp_obj_new_int_from_uint(total_wait_us),
        mp_obj_new_int_from_uint(total_us),
    };
    return mp_obj_new_tuple(4, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_band_submit_probe_rgb565_obj, 4, 4, lgfx_band_submit_probe_rgb565);


static mp_obj_t lgfx_render_scene_bands_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 28 && n_args != 33 && n_args != 34 && n_args != 41 && n_args != 42 && n_args != 45 && n_args != 47 && n_args != 50 && n_args != 58 && n_args != 61 && n_args != 62) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 28, 33, 34, 41, 42, 45, 47, 50, 58, 61 or 62 args"));
    }
    if (g_tail_wait_state.active) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("tail wait pending"));
    }

    mp_buffer_info_t band_a_info, band_b_info, far_info, tilemap_info, tileset_info, obj_info, obj_atlas_info, sprite_info;
    mp_get_buffer_raise(args[0], &band_a_info, MP_BUFFER_RW);
    mp_get_buffer_raise(args[1], &band_b_info, MP_BUFFER_RW);
    int32_t screen_w = (int32_t)mp_obj_get_int(args[2]);
    int32_t screen_h = (int32_t)mp_obj_get_int(args[3]);
    int32_t band_h_cfg = (int32_t)mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &far_info, MP_BUFFER_READ);
    int32_t camera_x = (int32_t)mp_obj_get_int(args[6]);
    mp_get_buffer_raise(args[7], &tilemap_info, MP_BUFFER_READ);
    int32_t map_w = (int32_t)mp_obj_get_int(args[8]);
    int32_t map_h = (int32_t)mp_obj_get_int(args[9]);
    mp_get_buffer_raise(args[10], &tileset_info, MP_BUFFER_READ);
    int32_t tile_size = (int32_t)mp_obj_get_int(args[11]);
    int32_t tileset_w = (int32_t)mp_obj_get_int(args[12]);
    int32_t tile_key = (int32_t)mp_obj_get_int(args[13]);
    mp_get_buffer_raise(args[14], &obj_info, MP_BUFFER_READ);
    int32_t obj_stride = (int32_t)mp_obj_get_int(args[15]);
    mp_get_buffer_raise(args[16], &obj_atlas_info, MP_BUFFER_READ);
    int32_t obj_atlas_w = (int32_t)mp_obj_get_int(args[17]);
    int32_t obj_atlas_h = (int32_t)mp_obj_get_int(args[18]);
    int32_t object_key = (int32_t)mp_obj_get_int(args[19]);
    int32_t object_count = (int32_t)mp_obj_get_int(args[20]);
    mp_get_buffer_raise(args[21], &sprite_info, MP_BUFFER_READ);
    int32_t sprite_w = (int32_t)mp_obj_get_int(args[22]);
    int32_t sprite_h = (int32_t)mp_obj_get_int(args[23]);
    int32_t sprite_x = (int32_t)mp_obj_get_int(args[24]);
    int32_t sprite_y = (int32_t)mp_obj_get_int(args[25]);
    int32_t sprite_key = (int32_t)mp_obj_get_int(args[26]);
    mp_buffer_info_t overlay_info;
    overlay_info.buf = nullptr;
    overlay_info.len = 0;
    int32_t overlay_stride = 0;
    int32_t overlay_count = 0;
    mp_obj_t overlay_frames_obj = mp_const_empty_tuple;
    mp_buffer_info_t special_desc_info;
    special_desc_info.buf = nullptr;
    special_desc_info.len = 0;
    int32_t special_stride = 0;
    int32_t special_count = 0;
    mp_buffer_info_t respawn_sheet_info;
    respawn_sheet_info.buf = nullptr;
    respawn_sheet_info.len = 0;
    int32_t respawn_frame_w = 0;
    int32_t respawn_frame_h = 0;
    int32_t respawn_frame_count = 0;
    mp_buffer_info_t anchor_sheet_info;
    anchor_sheet_info.buf = nullptr;
    anchor_sheet_info.len = 0;
    int32_t anchor_frame_w = 0;
    int32_t anchor_frame_h = 0;
    int32_t anchor_frame_count = 0;
    int32_t overlay_key = -1;
    mp_buffer_info_t enemy_desc_info;
    enemy_desc_info.buf = nullptr;
    enemy_desc_info.len = 0;
    int32_t enemy_stride = 0;
    int32_t enemy_count = 0;
    mp_buffer_info_t enemy_sheet_info;
    enemy_sheet_info.buf = nullptr;
    enemy_sheet_info.len = 0;
    int32_t enemy_sheet_w = 0;
    int32_t enemy_sheet_h = 0;
    int32_t enemy_key = -1;
    int32_t enemy_frame_hold = 4;
    mp_buffer_info_t enemy_monk_sheet_info;
    enemy_monk_sheet_info.buf = nullptr;
    enemy_monk_sheet_info.len = 0;
    int32_t enemy_monk_frame_w = 0;
    int32_t enemy_monk_frame_h = 0;
    int32_t enemy_monk_frame_count = 0;
    int32_t enemy_monk_frame_hold = 1;
    mp_buffer_info_t enemy_monk_orb_atlas_info;
    enemy_monk_orb_atlas_info.buf = nullptr;
    enemy_monk_orb_atlas_info.len = 0;
    int32_t enemy_monk_orb_atlas_w = 0;
    int32_t enemy_monk_orb_atlas_h = 0;
    int32_t probe_flags = 0;
    bool verbose = false;
    if (n_args == 61 || n_args == 62) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[44]);
        enemy_count = (int32_t)mp_obj_get_int(args[45]);
        mp_get_buffer_raise(args[46], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[47]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[48]);
        mp_get_buffer_raise(args[49], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[50]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[51]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[52]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[53]);
        mp_get_buffer_raise(args[54], &enemy_monk_orb_atlas_info, MP_BUFFER_READ);
        enemy_monk_orb_atlas_w = (int32_t)mp_obj_get_int(args[55]);
        enemy_monk_orb_atlas_h = (int32_t)mp_obj_get_int(args[56]);
        enemy_key = (int32_t)mp_obj_get_int(args[57]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[58]);
        probe_flags = (int32_t)mp_obj_get_int(args[59]);
        verbose = mp_obj_is_true(args[60]);
    } else if (n_args == 58) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[44]);
        enemy_count = (int32_t)mp_obj_get_int(args[45]);
        mp_get_buffer_raise(args[46], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[47]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[48]);
        mp_get_buffer_raise(args[49], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[50]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[51]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[52]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[53]);
        enemy_key = (int32_t)mp_obj_get_int(args[54]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[55]);
        probe_flags = (int32_t)mp_obj_get_int(args[56]);
        verbose = mp_obj_is_true(args[57]);
    } else if (n_args == 50) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[39]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[40]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[41]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_monk_orb_atlas_info, MP_BUFFER_READ);
        enemy_monk_orb_atlas_w = (int32_t)mp_obj_get_int(args[44]);
        enemy_monk_orb_atlas_h = (int32_t)mp_obj_get_int(args[45]);
        enemy_key = (int32_t)mp_obj_get_int(args[46]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[47]);
        probe_flags = (int32_t)mp_obj_get_int(args[48]);
        verbose = mp_obj_is_true(args[49]);
    } else if (n_args == 47) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[39]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[40]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[41]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[42]);
        enemy_key = (int32_t)mp_obj_get_int(args[43]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[44]);
        probe_flags = (int32_t)mp_obj_get_int(args[45]);
        verbose = mp_obj_is_true(args[46]);
    } else if (n_args == 42) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        enemy_key = (int32_t)mp_obj_get_int(args[38]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[39]);
        probe_flags = (int32_t)mp_obj_get_int(args[40]);
        verbose = mp_obj_is_true(args[41]);
    } else if (n_args == 41) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        enemy_key = (int32_t)mp_obj_get_int(args[38]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[39]);
        verbose = mp_obj_is_true(args[40]);
    } else if (n_args == 45) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        probe_flags = (int32_t)mp_obj_get_int(args[43]);
        verbose = mp_obj_is_true(args[44]);
    } else if (n_args == 34) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        probe_flags = (int32_t)mp_obj_get_int(args[32]);
        verbose = mp_obj_is_true(args[33]);
    } else if (n_args == 33) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        verbose = mp_obj_is_true(args[32]);
    } else {
        verbose = mp_obj_is_true(args[27]);
    }
    bool disable_far = (probe_flags & 0x1) != 0;
    bool defer_final_wait = false;
    if (n_args == 62) {
        defer_final_wait = mp_obj_is_true(args[61]);
    }

    if (screen_w <= 0 || screen_h <= 0 || band_h_cfg <= 0 || band_h_cfg > screen_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    size_t max_band_len = (size_t)screen_w * (size_t)band_h_cfg * 2u;
    size_t full_len = (size_t)screen_w * (size_t)screen_h * 2u;
    if (band_a_info.len < max_band_len || band_b_info.len < max_band_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("band buf too small"));
    }
    if (far_info.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("far buf too small"));
    }
    if (tilemap_info.len < (size_t)map_w * (size_t)map_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
    }
    if (sprite_info.len < (size_t)sprite_w * (size_t)sprite_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("sprite buf too small"));
    }
    if (overlay_count > 0) {
        if (overlay_stride < 10 || overlay_info.len < (size_t)overlay_count * (size_t)overlay_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("overlay buf too small"));
        }
    }
    if (special_count > 0) {
        if (special_stride < 8 || special_desc_info.len < (size_t)special_count * (size_t)special_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("special buf too small"));
        }
    }
    if (respawn_sheet_info.buf != nullptr && respawn_frame_w > 0 && respawn_frame_h > 0 && respawn_frame_count > 0) {
        if (respawn_sheet_info.len < (size_t)respawn_frame_w * (size_t)respawn_frame_h * (size_t)respawn_frame_count * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("respawn sheet too small"));
        }
    }
    if (anchor_sheet_info.buf != nullptr && anchor_frame_w > 0 && anchor_frame_h > 0 && anchor_frame_count > 0) {
        if (anchor_sheet_info.len < (size_t)anchor_frame_w * (size_t)anchor_frame_h * (size_t)anchor_frame_count * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("anchor sheet too small"));
        }
    }
    if (enemy_count > 0) {
        if (enemy_stride < 10 || enemy_desc_info.len < (size_t)enemy_count * (size_t)enemy_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("enemy desc too small"));
        }
        if (enemy_sheet_info.buf != nullptr && enemy_sheet_w > 0 && enemy_sheet_h > 0) {
            if (enemy_sheet_info.len < (size_t)enemy_sheet_w * (size_t)enemy_sheet_h * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy sheet too small"));
            }
        }
        if (enemy_monk_sheet_info.buf != nullptr && enemy_monk_frame_w > 0 && enemy_monk_frame_h > 0 && enemy_monk_frame_count > 0) {
            if (enemy_monk_sheet_info.len < (size_t)enemy_monk_frame_w * (size_t)enemy_monk_frame_h * (size_t)enemy_monk_frame_count * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy monk sheet too small"));
            }
        }
        if (enemy_monk_orb_atlas_info.buf != nullptr && enemy_monk_orb_atlas_w > 0 && enemy_monk_orb_atlas_h > 0) {
            if (enemy_monk_orb_atlas_info.len < (size_t)enemy_monk_orb_atlas_w * (size_t)enemy_monk_orb_atlas_h * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy monk orb atlas too small"));
            }
        }
    }
    if (object_count > 0) {
        if (obj_stride < 12 || obj_info.len < (size_t)object_count * (size_t)obj_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("object buf too small"));
        }
        if (obj_atlas_info.len < (size_t)obj_atlas_w * (size_t)obj_atlas_h * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("object atlas too small"));
        }
    }

    uint8_t *band_a = (uint8_t *)band_a_info.buf;
    uint8_t *band_b = (uint8_t *)band_b_info.buf;
    const uint8_t *far = (const uint8_t *)far_info.buf;
    const uint8_t *tilemap = (const uint8_t *)tilemap_info.buf;
    const uint8_t *tileset = (const uint8_t *)tileset_info.buf;
    const uint8_t *objbuf = (const uint8_t *)obj_info.buf;
    const uint8_t *obj_atlas = (const uint8_t *)obj_atlas_info.buf;
    const uint8_t *sprite = (const uint8_t *)sprite_info.buf;
    const uint8_t *overlay_desc = (const uint8_t *)overlay_info.buf;
    const uint8_t *special_desc = (const uint8_t *)special_desc_info.buf;
    const uint8_t *respawn_sheet = (const uint8_t *)respawn_sheet_info.buf;
    const uint8_t *anchor_sheet = (const uint8_t *)anchor_sheet_info.buf;
    const uint8_t *enemy_desc = (const uint8_t *)enemy_desc_info.buf;
    const uint8_t *enemy_sheet = (const uint8_t *)enemy_sheet_info.buf;
    const uint8_t *enemy_monk_sheet = (const uint8_t *)enemy_monk_sheet_info.buf;
    const uint8_t *enemy_monk_orb_atlas = (const uint8_t *)enemy_monk_orb_atlas_info.buf;

    static const uint32_t kProfileBands = 6;
    uint32_t compose_us = 0;
    uint32_t band_bg_us = 0;
    uint32_t band_tilemap_us = 0;
    uint32_t band_object_us = 0;
    uint32_t band_special_us = 0;
    uint32_t band_enemy_us = 0;
    uint32_t band_player_us = 0;
    uint32_t band_compose_each[kProfileBands] = {0};
    uint32_t band_wait_each[kProfileBands] = {0};
    uint32_t kick_us = 0;
    uint32_t wait_us = 0;
    uint32_t sync_us = 0;
    uint32_t start_us = 0;
    uint32_t push_us = 0;
    uint32_t wait_dma_us = 0;
    uint32_t end_us = 0;
    uint32_t dma_elapsed_us = 0;
    int64_t dma_t0 = 0;
    uint32_t bands = 0;
    int64_t all_t0 = esp_timer_get_time();

    int32_t y = 0;
    int32_t bh = band_h_cfg;
    if (y + bh > screen_h) bh = screen_h - y;
    int64_t ct0 = esp_timer_get_time();
    compose_scene_band(band_a, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, overlay_key, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold, disable_far, &band_bg_us, &band_tilemap_us, &band_object_us, &band_special_us, &band_enemy_us, &band_player_us);
    uint32_t compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
    compose_us += compose_delta;
    band_compose_each[0] = compose_delta;

    bool prev_swap = false;
    dma_t0 = submit_band_start(band_a, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
    if (verbose) {
        mp_printf(&mp_plat_print, "BAND_PIPE band=0 y=%d h=%d\n", (int)y, (int)bh);
    }
    bands = 1;
    y += bh;

    uint8_t *next_buf = band_b;
    while (y < screen_h) {
        bh = band_h_cfg;
        if (y + bh > screen_h) bh = screen_h - y;
        ct0 = esp_timer_get_time();
        compose_scene_band(next_buf, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, overlay_key, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold, disable_far, &band_bg_us, &band_tilemap_us, &band_object_us, &band_special_us, &band_enemy_us, &band_player_us);
        compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
        compose_us += compose_delta;
        if (bands < kProfileBands) {
            band_compose_each[bands] = compose_delta;
        }
        int64_t wt0 = esp_timer_get_time();
        int64_t dma_done_t = submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
        dma_elapsed_us += (uint32_t)(dma_done_t - dma_t0);
        uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
        if ((bands - 1) < kProfileBands) {
            band_wait_each[bands - 1] = wait_delta;
        }
        dma_t0 = submit_band_start(next_buf, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
        if (verbose) {
            mp_printf(&mp_plat_print, "BAND_PIPE band=%u y=%d h=%d\n", (unsigned)bands, (int)y, (int)bh);
        }
        ++bands;
        y += bh;
        next_buf = (next_buf == band_a) ? band_b : band_a;
    }
    if (defer_final_wait) {
        g_tail_wait_state.active = true;
        g_tail_wait_state.prev_swap = prev_swap;
        g_tail_wait_state.wait_t0 = esp_timer_get_time();
        g_tail_wait_state.dma_t0 = dma_t0;
    } else {
        int64_t wt0 = esp_timer_get_time();
        int64_t dma_done_t = submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
        dma_elapsed_us += (uint32_t)(dma_done_t - dma_t0);
        uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
        if ((bands - 1) < kProfileBands) {
            band_wait_each[bands - 1] = wait_delta;
        }
    }

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_obj_t out[29] = {
        mp_obj_new_int_from_uint(bands),
        mp_obj_new_int_from_uint(compose_us),
        mp_obj_new_int_from_uint(kick_us),
        mp_obj_new_int_from_uint(wait_us),
        mp_obj_new_int_from_uint(sync_us),
        mp_obj_new_int_from_uint(start_us),
        mp_obj_new_int_from_uint(push_us),
        mp_obj_new_int_from_uint(wait_dma_us),
        mp_obj_new_int_from_uint(end_us),
        mp_obj_new_int_from_uint(total_us),
        mp_obj_new_int_from_uint(band_bg_us),
        mp_obj_new_int_from_uint(band_tilemap_us),
        mp_obj_new_int_from_uint(band_object_us),
        mp_obj_new_int_from_uint(band_special_us),
        mp_obj_new_int_from_uint(band_enemy_us),
        mp_obj_new_int_from_uint(band_player_us),
        mp_obj_new_int_from_uint(band_compose_each[0]),
        mp_obj_new_int_from_uint(band_compose_each[1]),
        mp_obj_new_int_from_uint(band_compose_each[2]),
        mp_obj_new_int_from_uint(band_compose_each[3]),
        mp_obj_new_int_from_uint(band_compose_each[4]),
        mp_obj_new_int_from_uint(band_compose_each[5]),
        mp_obj_new_int_from_uint(band_wait_each[0]),
        mp_obj_new_int_from_uint(band_wait_each[1]),
        mp_obj_new_int_from_uint(band_wait_each[2]),
        mp_obj_new_int_from_uint(band_wait_each[3]),
        mp_obj_new_int_from_uint(band_wait_each[4]),
        mp_obj_new_int_from_uint(band_wait_each[5]),
        mp_obj_new_int_from_uint(dma_elapsed_us),
    };
    return mp_obj_new_tuple(29, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_render_scene_bands_rgb565_obj, 28, 62, lgfx_render_scene_bands_rgb565);

static mp_obj_t lgfx_render_elevator_scene_bands_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 26 && n_args != 35 && n_args != 41) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 26, 35 or 41 args"));
    }
    if (g_tail_wait_state.active) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("tail wait pending"));
    }

    mp_buffer_info_t band_a_info, band_b_info, far_info, wall_info, door_info, floor_info, object_atlas_info, sprite_info;
    mp_get_buffer_raise(args[0], &band_a_info, MP_BUFFER_RW);
    mp_get_buffer_raise(args[1], &band_b_info, MP_BUFFER_RW);
    int32_t screen_w = (int32_t)mp_obj_get_int(args[2]);
    int32_t screen_h = (int32_t)mp_obj_get_int(args[3]);
    int32_t band_h_cfg = (int32_t)mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &far_info, MP_BUFFER_READ);
    mp_get_buffer_raise(args[6], &wall_info, MP_BUFFER_READ);
    int32_t wall_w = (int32_t)mp_obj_get_int(args[7]);
    int32_t wall_h = (int32_t)mp_obj_get_int(args[8]);
    mp_get_buffer_raise(args[9], &door_info, MP_BUFFER_READ);
    int32_t door_w = (int32_t)mp_obj_get_int(args[10]);
    int32_t door_h = (int32_t)mp_obj_get_int(args[11]);
    mp_get_buffer_raise(args[12], &floor_info, MP_BUFFER_READ);
    int32_t floor_w = (int32_t)mp_obj_get_int(args[13]);
    int32_t floor_h = (int32_t)mp_obj_get_int(args[14]);
    bool has_lever = n_args == 35 || n_args == 41;
    bool has_floor_segments = n_args == 41;
    int32_t object_atlas_w = 0;
    int32_t object_atlas_h = 0;
    int32_t lever_x = 0;
    int32_t lever_y = 0;
    int32_t lever_w = 0;
    int32_t lever_h = 0;
    int32_t lever_src_x = 0;
    int32_t lever_src_y = 0;
    int32_t floor_x = 32;
    int32_t floor_y = 208;
    int32_t floor_left_w = 0;
    int32_t floor_middle_w = 0;
    int32_t floor_left_y = 208;
    int32_t floor_right_y = 208;
    int32_t sprite_arg = 15;
    if (has_lever) {
        mp_get_buffer_raise(args[15], &object_atlas_info, MP_BUFFER_READ);
        object_atlas_w = (int32_t)mp_obj_get_int(args[16]);
        object_atlas_h = (int32_t)mp_obj_get_int(args[17]);
        lever_x = (int32_t)mp_obj_get_int(args[18]);
        lever_y = (int32_t)mp_obj_get_int(args[19]);
        lever_w = (int32_t)mp_obj_get_int(args[20]);
        lever_h = (int32_t)mp_obj_get_int(args[21]);
        lever_src_x = (int32_t)mp_obj_get_int(args[22]);
        lever_src_y = (int32_t)mp_obj_get_int(args[23]);
        if (has_floor_segments) {
            floor_x = (int32_t)mp_obj_get_int(args[24]);
            floor_y = (int32_t)mp_obj_get_int(args[25]);
            floor_left_w = (int32_t)mp_obj_get_int(args[26]);
            floor_middle_w = (int32_t)mp_obj_get_int(args[27]);
            floor_left_y = (int32_t)mp_obj_get_int(args[28]);
            floor_right_y = (int32_t)mp_obj_get_int(args[29]);
            sprite_arg = 30;
        } else {
            floor_x = 32;
            floor_y = 208;
            floor_left_y = floor_y;
            floor_right_y = floor_y;
            sprite_arg = 24;
        }
    }
    mp_get_buffer_raise(args[sprite_arg], &sprite_info, MP_BUFFER_READ);
    int32_t sprite_w = (int32_t)mp_obj_get_int(args[sprite_arg + 1]);
    int32_t sprite_h = (int32_t)mp_obj_get_int(args[sprite_arg + 2]);
    int32_t sprite_x = (int32_t)mp_obj_get_int(args[sprite_arg + 3]);
    int32_t sprite_y = (int32_t)mp_obj_get_int(args[sprite_arg + 4]);
    int32_t sprite_key = (int32_t)mp_obj_get_int(args[sprite_arg + 5]);
    int32_t wall_scroll_y = (int32_t)mp_obj_get_int(args[sprite_arg + 6]);
    int32_t door_y = (int32_t)mp_obj_get_int(args[sprite_arg + 7]);
    int32_t door_enabled = mp_obj_is_true(args[sprite_arg + 8]) ? 1 : 0;
    int32_t transparent_key = (int32_t)mp_obj_get_int(args[sprite_arg + 9]);
    bool verbose = mp_obj_is_true(args[sprite_arg + 10]);

    if (screen_w <= 0 || screen_h <= 0 || band_h_cfg <= 0 || band_h_cfg > screen_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    size_t max_band_len = (size_t)screen_w * (size_t)band_h_cfg * 2u;
    size_t full_len = (size_t)screen_w * (size_t)screen_h * 2u;
    if (band_a_info.len < max_band_len || band_b_info.len < max_band_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("band buf too small"));
    }
    if (far_info.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("far buf too small"));
    }
    if (wall_w < 64 || wall_h <= 0 || wall_info.len < (size_t)wall_w * (size_t)wall_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("wall buf too small"));
    }
    if (door_w <= 0 || door_h <= 0 || door_info.len < (size_t)door_w * (size_t)door_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("door buf too small"));
    }
    if (floor_w <= 0 || floor_h <= 0 || floor_info.len < (size_t)floor_w * (size_t)floor_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("floor buf too small"));
    }
    if (has_lever) {
        if (object_atlas_w <= 0 || object_atlas_h <= 0 || object_atlas_info.len < (size_t)object_atlas_w * (size_t)object_atlas_h * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("object atlas buf too small"));
        }
    }
    if (sprite_info.len < (size_t)sprite_w * (size_t)sprite_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("sprite buf too small"));
    }

    uint8_t *band_a = (uint8_t *)band_a_info.buf;
    uint8_t *band_b = (uint8_t *)band_b_info.buf;
    const uint8_t *far = (const uint8_t *)far_info.buf;
    const uint8_t *wall = (const uint8_t *)wall_info.buf;
    const uint8_t *door = (const uint8_t *)door_info.buf;
    const uint8_t *floor = (const uint8_t *)floor_info.buf;
    const uint8_t *object_atlas = has_lever ? (const uint8_t *)object_atlas_info.buf : nullptr;
    const uint8_t *sprite = (const uint8_t *)sprite_info.buf;

    static const uint32_t kProfileBands = 6;
    uint32_t compose_us = 0;
    uint32_t band_bg_us = 0;
    uint32_t band_tilemap_us = 0;
    uint32_t band_object_us = 0;
    uint32_t band_special_us = 0;
    uint32_t band_enemy_us = 0;
    uint32_t band_player_us = 0;
    uint32_t band_compose_each[kProfileBands] = {0};
    uint32_t band_wait_each[kProfileBands] = {0};
    uint32_t kick_us = 0;
    uint32_t wait_us = 0;
    uint32_t sync_us = 0;
    uint32_t start_us = 0;
    uint32_t push_us = 0;
    uint32_t wait_dma_us = 0;
    uint32_t end_us = 0;
    uint32_t dma_elapsed_us = 0;
    int64_t dma_t0 = 0;
    uint32_t bands = 0;
    int64_t all_t0 = esp_timer_get_time();

    int32_t y = 0;
    int32_t bh = band_h_cfg;
    if (y + bh > screen_h) bh = screen_h - y;
    int64_t ct0 = esp_timer_get_time();
    compose_elevator_scene_band(band_a, screen_w, bh, y, far, wall, wall_w, wall_h, door, door_w, door_h, floor, floor_w, floor_h, object_atlas, object_atlas_w, object_atlas_h, lever_x, lever_y, lever_w, lever_h, lever_src_x, lever_src_y, floor_x, floor_y, floor_left_w, floor_middle_w, floor_left_y, floor_right_y, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, wall_scroll_y, door_y, door_enabled, transparent_key, &band_bg_us, &band_tilemap_us, &band_player_us);
    uint32_t compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
    compose_us += compose_delta;
    band_compose_each[0] = compose_delta;

    bool prev_swap = false;
    dma_t0 = submit_band_start(band_a, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
    if (verbose) {
        mp_printf(&mp_plat_print, "ELEVATOR_PIPE band=0 y=%d h=%d\n", (int)y, (int)bh);
    }
    bands = 1;
    y += bh;

    uint8_t *next_buf = band_b;
    while (y < screen_h) {
        bh = band_h_cfg;
        if (y + bh > screen_h) bh = screen_h - y;
        ct0 = esp_timer_get_time();
        compose_elevator_scene_band(next_buf, screen_w, bh, y, far, wall, wall_w, wall_h, door, door_w, door_h, floor, floor_w, floor_h, object_atlas, object_atlas_w, object_atlas_h, lever_x, lever_y, lever_w, lever_h, lever_src_x, lever_src_y, floor_x, floor_y, floor_left_w, floor_middle_w, floor_left_y, floor_right_y, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, wall_scroll_y, door_y, door_enabled, transparent_key, &band_bg_us, &band_tilemap_us, &band_player_us);
        compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
        compose_us += compose_delta;
        if (bands < kProfileBands) {
            band_compose_each[bands] = compose_delta;
        }
        int64_t wt0 = esp_timer_get_time();
        int64_t dma_done_t = submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
        dma_elapsed_us += (uint32_t)(dma_done_t - dma_t0);
        uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
        if ((bands - 1) < kProfileBands) {
            band_wait_each[bands - 1] = wait_delta;
        }
        dma_t0 = submit_band_start(next_buf, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
        if (verbose) {
            mp_printf(&mp_plat_print, "ELEVATOR_PIPE band=%u y=%d h=%d\n", (unsigned)bands, (int)y, (int)bh);
        }
        ++bands;
        y += bh;
        next_buf = (next_buf == band_a) ? band_b : band_a;
    }
    int64_t wt0 = esp_timer_get_time();
    int64_t dma_done_t = submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
    dma_elapsed_us += (uint32_t)(dma_done_t - dma_t0);
    uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
    if ((bands - 1) < kProfileBands) {
        band_wait_each[bands - 1] = wait_delta;
    }

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_obj_t out[29] = {
        mp_obj_new_int_from_uint(bands),
        mp_obj_new_int_from_uint(compose_us),
        mp_obj_new_int_from_uint(kick_us),
        mp_obj_new_int_from_uint(wait_us),
        mp_obj_new_int_from_uint(sync_us),
        mp_obj_new_int_from_uint(start_us),
        mp_obj_new_int_from_uint(push_us),
        mp_obj_new_int_from_uint(wait_dma_us),
        mp_obj_new_int_from_uint(end_us),
        mp_obj_new_int_from_uint(total_us),
        mp_obj_new_int_from_uint(band_bg_us),
        mp_obj_new_int_from_uint(band_tilemap_us),
        mp_obj_new_int_from_uint(band_object_us),
        mp_obj_new_int_from_uint(band_special_us),
        mp_obj_new_int_from_uint(band_enemy_us),
        mp_obj_new_int_from_uint(band_player_us),
        mp_obj_new_int_from_uint(band_compose_each[0]),
        mp_obj_new_int_from_uint(band_compose_each[1]),
        mp_obj_new_int_from_uint(band_compose_each[2]),
        mp_obj_new_int_from_uint(band_compose_each[3]),
        mp_obj_new_int_from_uint(band_compose_each[4]),
        mp_obj_new_int_from_uint(band_compose_each[5]),
        mp_obj_new_int_from_uint(band_wait_each[0]),
        mp_obj_new_int_from_uint(band_wait_each[1]),
        mp_obj_new_int_from_uint(band_wait_each[2]),
        mp_obj_new_int_from_uint(band_wait_each[3]),
        mp_obj_new_int_from_uint(band_wait_each[4]),
        mp_obj_new_int_from_uint(band_wait_each[5]),
        mp_obj_new_int_from_uint(dma_elapsed_us),
    };
    return mp_obj_new_tuple(29, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_render_elevator_scene_bands_rgb565_obj, 26, 41, lgfx_render_elevator_scene_bands_rgb565);

static int16_t lgfx_band_rd_i16(const uint8_t *p) {
    uint16_t v = (uint16_t)p[0] | ((uint16_t)p[1] << 8);
    return (int16_t)v;
}

static void lgfx_band_wr_i16(uint8_t *p, int32_t v) {
    if (v < -32768) v = -32768;
    if (v > 32767) v = 32767;
    uint16_t uv = (uint16_t)((int16_t)v);
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
}

static int32_t lgfx_band_visible_target_distance2(
    int32_t wx,
    int32_t wy,
    int32_t ow,
    int32_t oh,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t camera_x,
    int32_t band_top,
    int32_t view_w,
    int32_t view_h
) {
    int32_t sx0 = wx - camera_x;
    int32_t sy0 = wy - band_top;
    int32_t sx1 = sx0 + ow;
    int32_t sy1 = sy0 + oh;
    int32_t cx0 = sx0 < 0 ? 0 : sx0;
    int32_t cy0 = sy0 < 0 ? 0 : sy0;
    int32_t cx1 = sx1 > view_w ? view_w : sx1;
    int32_t cy1 = sy1 > view_h ? view_h : sy1;
    if (cx1 <= cx0 || cy1 <= cy0) {
        return -1;
    }
    int32_t visible_w = cx1 - cx0;
    int32_t visible_h = cy1 - cy0;
    int32_t visible_area = visible_w * visible_h;
    if (visible_w < 10 || visible_h < 10 || visible_area < 128) {
        return -1;
    }
    int32_t px = (player_x - camera_x) + (player_w / 2);
    int32_t py = (player_y - band_top) + (player_h / 2);
    int32_t ox = (cx0 + cx1) / 2;
    int32_t oy = (cy0 + cy1) / 2;
    int32_t dx = ox - px;
    int32_t dy = oy - py;
    return (dx * dx) + (dy * dy);
}

static inline int32_t lgfx_band_rd_i32(const uint8_t *p) {
    uint32_t uv = (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    return (int32_t)uv;
}

static inline void lgfx_band_wr_i32(uint8_t *p, int32_t v) {
    uint32_t uv = (uint32_t)v;
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
    p[2] = (uint8_t)((uv >> 16) & 0xFFu);
    p[3] = (uint8_t)((uv >> 24) & 0xFFu);
}

static inline bool lgfx_swap_preview_candidate_better(bool pick_far, int32_t d2, int32_t best_d2) {
    return best_d2 < 0 || (pick_far ? (d2 > best_d2) : (d2 < best_d2));
}

static inline void lgfx_swap_preview_consider(
    bool pick_far,
    int32_t kind,
    int32_t index,
    int32_t slot,
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h,
    int32_t d2,
    int32_t *best_kind,
    int32_t *best_index,
    int32_t *best_slot,
    int32_t *best_x,
    int32_t *best_y,
    int32_t *best_w,
    int32_t *best_h,
    int32_t *best_d2
) {
    if (d2 < 0 || !lgfx_swap_preview_candidate_better(pick_far, d2, *best_d2)) {
        return;
    }
    *best_kind = kind;
    *best_index = index;
    *best_slot = slot;
    *best_x = x;
    *best_y = y;
    *best_w = w;
    *best_h = h;
    *best_d2 = d2;
}

static inline bool lgfx_swap_preview_same_target(int32_t kind, int32_t index, int32_t slot, int32_t other_kind, int32_t other_index, int32_t other_slot) {
    return kind == other_kind && index == other_index && slot == other_slot;
}

static inline void lgfx_swap_preview_write_state(uint8_t *state, bool active, bool valid, bool pick_far, int32_t kind, int32_t index, int32_t slot, int32_t x, int32_t y, int32_t w, int32_t h, int32_t d2) {
    state[0] = active ? 1u : 0u;
    state[1] = valid ? 1u : 0u;
    state[2] = pick_far ? 1u : 0u;
    state[3] = (uint8_t)(kind & 0xFF);
    lgfx_band_wr_i16(state + 4, index);
    lgfx_band_wr_i16(state + 6, slot);
    lgfx_band_wr_i16(state + 8, x);
    lgfx_band_wr_i16(state + 10, y);
    lgfx_band_wr_i16(state + 12, w);
    lgfx_band_wr_i16(state + 14, h);
    lgfx_band_wr_i32(state + 16, d2);
    uint16_t age = (uint16_t)state[20] | ((uint16_t)state[21] << 8);
    if (valid) {
        if (age < 0xFFFFu) age += 1u;
    } else {
        age = 0u;
    }
    state[20] = (uint8_t)(age & 0xFFu);
    state[21] = (uint8_t)((age >> 8) & 0xFFu);
    state[22] = 0u;
    state[23] = 0u;
}

static mp_obj_t lgfx_update_swap_preview_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 23) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 23 args"));
    }
    mp_buffer_info_t state_info;
    mp_buffer_info_t object_info;
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t bullet_info;
    mp_buffer_info_t monk_orbs_info;
    mp_get_buffer_raise(args[0], &state_info, MP_BUFFER_RW);
    mp_get_buffer_raise(args[1], &object_info, MP_BUFFER_READ);
    mp_int_t object_stride = mp_obj_get_int(args[2]);
    mp_int_t object_count = mp_obj_get_int(args[3]);
    mp_get_buffer_raise(args[4], &enemy_rows_info, MP_BUFFER_READ);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[5]);
    mp_int_t enemy_count = mp_obj_get_int(args[6]);
    mp_get_buffer_raise(args[7], &bullet_info, MP_BUFFER_READ);
    mp_int_t bullet_stride = mp_obj_get_int(args[8]);
    mp_int_t bullet_count = mp_obj_get_int(args[9]);
    mp_get_buffer_raise(args[10], &monk_orbs_info, MP_BUFFER_READ);
    mp_int_t orb_stride = mp_obj_get_int(args[11]);
    mp_int_t orb_count = mp_obj_get_int(args[12]);
    mp_int_t player_x = mp_obj_get_int(args[13]);
    mp_int_t player_y = mp_obj_get_int(args[14]);
    mp_int_t player_w = mp_obj_get_int(args[15]);
    mp_int_t player_h = mp_obj_get_int(args[16]);
    bool pick_far = mp_obj_is_true(args[17]);
    mp_int_t camera_x = mp_obj_get_int(args[18]);
    mp_int_t band_top = mp_obj_get_int(args[19]);
    mp_int_t view_w = mp_obj_get_int(args[20]);
    mp_int_t view_h = mp_obj_get_int(args[21]);
    mp_int_t hysteresis_px = mp_obj_get_int(args[22]);

    if (state_info.len < 24u) {
        mp_raise_ValueError(MP_ERROR_TEXT("swap preview state too small"));
    }
    if (object_count < 0 || enemy_count < 0 || bullet_count < 0 || orb_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid swap preview counts"));
    }
    if (object_count > 0 && (object_stride < 10 || object_info.len < (size_t)object_count * (size_t)object_stride)) {
        mp_raise_ValueError(MP_ERROR_TEXT("swap object buf too small"));
    }
    if (enemy_count > 0 && (enemy_row_stride < 12 || enemy_rows_info.len < (size_t)enemy_count * (size_t)enemy_row_stride)) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (bullet_count > 0 && (bullet_stride < 16 || bullet_info.len < (size_t)bullet_count * (size_t)bullet_stride)) {
        mp_raise_ValueError(MP_ERROR_TEXT("bullet buf too small"));
    }
    if (orb_count > 0 && (orb_stride < 16 || monk_orbs_info.len < (size_t)orb_count * (size_t)orb_stride)) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb buf too small"));
    }
    uint8_t *state = (uint8_t *)state_info.buf;
    const uint8_t *objects = (const uint8_t *)object_info.buf;
    const uint8_t *enemy_rows = (const uint8_t *)enemy_rows_info.buf;
    const uint8_t *bullets = (const uint8_t *)bullet_info.buf;
    const uint8_t *orbs = (const uint8_t *)monk_orbs_info.buf;

    int32_t curr_kind = state[1] ? (int32_t)state[3] : 0;
    int32_t curr_index = state[1] ? lgfx_band_rd_i16(state + 4) : -1;
    int32_t curr_slot = state[1] ? lgfx_band_rd_i16(state + 6) : -1;
    bool current_same_mode = state[1] && ((state[2] != 0u) == pick_far);
    int32_t current_kind = 0;
    int32_t current_index = -1;
    int32_t current_slot = -1;
    int32_t current_x = 0;
    int32_t current_y = 0;
    int32_t current_w = 0;
    int32_t current_h = 0;
    int32_t current_d2 = -1;

    int32_t best_kind = 0;
    int32_t best_index = -1;
    int32_t best_slot = -1;
    int32_t best_x = 0;
    int32_t best_y = 0;
    int32_t best_w = 0;
    int32_t best_h = 0;
    int32_t best_d2 = -1;

    for (int32_t i = 0; i < object_count; ++i) {
        const uint8_t *row = objects + ((size_t)i * (size_t)object_stride);
        if (!row[8] || !row[9]) continue;
        int32_t x = lgfx_band_rd_i16(row + 0);
        int32_t y = lgfx_band_rd_i16(row + 2);
        int32_t w = lgfx_band_rd_i16(row + 4);
        int32_t h = lgfx_band_rd_i16(row + 6);
        int32_t d2 = lgfx_band_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h);
        if (d2 < 0) continue;
        if (current_same_mode && lgfx_swap_preview_same_target(1, i, -1, curr_kind, curr_index, curr_slot)) {
            current_kind = 1; current_index = i; current_slot = -1; current_x = x; current_y = y; current_w = w; current_h = h; current_d2 = d2;
        }
        lgfx_swap_preview_consider(pick_far, 1, i, -1, x, y, w, h, d2, &best_kind, &best_index, &best_slot, &best_x, &best_y, &best_w, &best_h, &best_d2);
    }
    for (int32_t i = 0; i < enemy_count; ++i) {
        const uint8_t *row = enemy_rows + ((size_t)i * (size_t)enemy_row_stride);
        if (!row[8] || !row[9] || row[11]) continue;
        int32_t x = lgfx_band_rd_i16(row + 0);
        int32_t y = lgfx_band_rd_i16(row + 2);
        int32_t w = lgfx_band_rd_i16(row + 4);
        int32_t h = lgfx_band_rd_i16(row + 6);
        int32_t d2 = lgfx_band_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h);
        if (d2 < 0) continue;
        if (current_same_mode && lgfx_swap_preview_same_target(2, i, -1, curr_kind, curr_index, curr_slot)) {
            current_kind = 2; current_index = i; current_slot = -1; current_x = x; current_y = y; current_w = w; current_h = h; current_d2 = d2;
        }
        lgfx_swap_preview_consider(pick_far, 2, i, -1, x, y, w, h, d2, &best_kind, &best_index, &best_slot, &best_x, &best_y, &best_w, &best_h, &best_d2);
    }
    for (int32_t i = 0; i < bullet_count; ++i) {
        const uint8_t *row = bullets + ((size_t)i * (size_t)bullet_stride);
        if (lgfx_band_rd_i16(row + 12) == 0) continue;
        int32_t x = lgfx_band_rd_i16(row + 0);
        int32_t y = lgfx_band_rd_i16(row + 2);
        int32_t w = lgfx_band_rd_i16(row + 8);
        int32_t h = lgfx_band_rd_i16(row + 10);
        int32_t d2 = lgfx_band_visible_target_distance2(x, y, w, h, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h);
        if (d2 < 0) continue;
        if (current_same_mode && lgfx_swap_preview_same_target(3, i, -1, curr_kind, curr_index, curr_slot)) {
            current_kind = 3; current_index = i; current_slot = -1; current_x = x; current_y = y; current_w = w; current_h = h; current_d2 = d2;
        }
        lgfx_swap_preview_consider(pick_far, 3, i, -1, x, y, w, h, d2, &best_kind, &best_index, &best_slot, &best_x, &best_y, &best_w, &best_h, &best_d2);
    }
    int32_t enemy_limit = enemy_count;
    int32_t orb_enemy_limit = orb_count / 5;
    if (enemy_limit > orb_enemy_limit) enemy_limit = orb_enemy_limit;
    for (int32_t ei = 0; ei < enemy_limit; ++ei) {
        const uint8_t *row = enemy_rows + ((size_t)ei * (size_t)enemy_row_stride);
        if (!row[8] || !row[9]) continue;
        for (int32_t si = 0; si < 5; ++si) {
            int32_t oi = (ei * 5) + si;
            if (oi < 0 || oi >= orb_count) continue;
            const uint8_t *orb = orbs + ((size_t)oi * (size_t)orb_stride);
            uint8_t mode = orb[0];
            if (!monk_orb_mode_is_pickable((int32_t)mode)) continue;
            int32_t x = lgfx_band_rd_i16(orb + 10);
            int32_t y = lgfx_band_rd_i16(orb + 12);
            int32_t d2 = lgfx_band_visible_target_distance2(x, y, kMonkOrbW, kMonkOrbH, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h);
            if (d2 < 0) continue;
            if (current_same_mode && lgfx_swap_preview_same_target(4, ei, si, curr_kind, curr_index, curr_slot)) {
                current_kind = 4; current_index = ei; current_slot = si; current_x = x - 1; current_y = y - 1; current_w = kMonkOrbW + 2; current_h = kMonkOrbH + 2; current_d2 = d2;
            }
            lgfx_swap_preview_consider(pick_far, 4, ei, si, x - 1, y - 1, kMonkOrbW + 2, kMonkOrbH + 2, d2, &best_kind, &best_index, &best_slot, &best_x, &best_y, &best_w, &best_h, &best_d2);
        }
    }

    if (current_kind != 0) {
        int32_t hysteresis_d2 = (int32_t)hysteresis_px * (int32_t)hysteresis_px;
        bool switch_target = false;
        if (best_kind != 0 && !lgfx_swap_preview_same_target(best_kind, best_index, best_slot, current_kind, current_index, current_slot)) {
            switch_target = pick_far ? (best_d2 > current_d2 + hysteresis_d2) : (best_d2 + hysteresis_d2 < current_d2);
        }
        if (!switch_target) {
            lgfx_swap_preview_write_state(state, true, true, pick_far, current_kind, current_index, current_slot, current_x, current_y, current_w, current_h, current_d2);
            return mp_obj_new_int(current_kind);
        }
    }
    if (best_kind != 0) {
        lgfx_swap_preview_write_state(state, true, true, pick_far, best_kind, best_index, best_slot, best_x, best_y, best_w, best_h, best_d2);
        return mp_obj_new_int(best_kind);
    }
    lgfx_swap_preview_write_state(state, true, false, pick_far, 0, -1, -1, 0, 0, 0, 0, -1);
    return MP_OBJ_NEW_SMALL_INT(0);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_swap_preview_native_obj, 23, 23, lgfx_update_swap_preview_native);

static mp_obj_t lgfx_pick_swappable_monk_orb_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 17) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 17 args"));
    }
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t monk_orbs_info;
    mp_get_buffer_raise(args[0], &enemy_rows_info, MP_BUFFER_READ);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[1]);
    mp_int_t enemy_count = mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &monk_orbs_info, MP_BUFFER_READ);
    mp_int_t orb_stride = mp_obj_get_int(args[4]);
    mp_int_t orb_count = mp_obj_get_int(args[5]);
    mp_int_t player_x = mp_obj_get_int(args[6]);
    mp_int_t player_y = mp_obj_get_int(args[7]);
    mp_int_t player_w = mp_obj_get_int(args[8]);
    mp_int_t player_h = mp_obj_get_int(args[9]);
    bool pick_far = mp_obj_is_true(args[10]);
    mp_int_t camera_x = mp_obj_get_int(args[11]);
    mp_int_t band_top = mp_obj_get_int(args[12]);
    mp_int_t view_w = mp_obj_get_int(args[13]);
    mp_int_t view_h = mp_obj_get_int(args[14]);
    mp_int_t prefer_enemy_i = mp_obj_get_int(args[15]);
    mp_int_t current_best_d2 = mp_obj_get_int(args[16]);
    if (enemy_row_stride < 12 || orb_stride < 16 || enemy_count < 0 || orb_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid monk orb pick dims"));
    }
    if (enemy_rows_info.len < (size_t)enemy_count * (size_t)enemy_row_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (monk_orbs_info.len < (size_t)orb_count * (size_t)orb_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb buf too small"));
    }
    const uint8_t *enemy_rows = (const uint8_t *)enemy_rows_info.buf;
    const uint8_t *orbs = (const uint8_t *)monk_orbs_info.buf;
    int32_t best_enemy_i = -1;
    int32_t best_slot_i = -1;
    int32_t best_d2 = current_best_d2;
    int32_t enemy_limit = enemy_count;
    int32_t orb_enemy_limit = orb_count / 5;
    if (enemy_limit > orb_enemy_limit) {
        enemy_limit = orb_enemy_limit;
    }
    for (int32_t ei = 0; ei < enemy_limit; ++ei) {
        const uint8_t *row = enemy_rows + ((size_t)ei * (size_t)enemy_row_stride);
        if (!row[8] || !row[9]) {
            continue;
        }
        for (int32_t si = 0; si < 5; ++si) {
            int32_t oi = (ei * 5) + si;
            if (oi < 0 || oi >= orb_count) {
                continue;
            }
            const uint8_t *orb = orbs + ((size_t)oi * (size_t)orb_stride);
            uint8_t mode = orb[0];
            if (!monk_orb_mode_is_pickable((int32_t)mode)) {
                continue;
            }
            int32_t orb_x = lgfx_band_rd_i16(orb + 10);
            int32_t orb_y = lgfx_band_rd_i16(orb + 12);
            int32_t d2 = lgfx_band_visible_target_distance2(orb_x, orb_y, kMonkOrbW, kMonkOrbH, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h);
            if (d2 < 0) {
                continue;
            }
            bool prefer_over_enemy = (prefer_enemy_i >= 0 && ei == prefer_enemy_i);
            if (best_enemy_i < 0 || prefer_over_enemy || best_d2 < 0 || (pick_far && d2 > best_d2) || (!pick_far && d2 < best_d2)) {
                best_enemy_i = ei;
                best_slot_i = si;
                best_d2 = d2;
            }
        }
    }
    mp_obj_t out[3] = {
        mp_obj_new_int(best_enemy_i),
        mp_obj_new_int(best_slot_i),
        mp_obj_new_int(best_d2),
    };
    return mp_obj_new_tuple(3, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_pick_swappable_monk_orb_native_obj, 17, 17, lgfx_pick_swappable_monk_orb_native);

static inline int32_t lgfx_attack_abs_i32(int32_t v) {
    return v < 0 ? -v : v;
}

static inline int32_t lgfx_attack_isqrt_i32(int32_t v) {
    if (v <= 0) {
        return 0;
    }
    uint32_t value = (uint32_t)v;
    uint32_t result = 0;
    uint32_t bit = 1u << 30;
    while (bit > value) {
        bit >>= 2;
    }
    while (bit != 0u) {
        if (value >= result + bit) {
            value -= result + bit;
            result = (result >> 1) + bit;
        } else {
            result >>= 1;
        }
        bit >>= 2;
    }
    return (int32_t)result;
}

static inline int32_t lgfx_attack_move_toward_i32(int32_t curr_v, int32_t target_v, int32_t speed_px) {
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

static inline int32_t lgfx_attack_dir_i32(uint8_t dir_byte, int32_t fallback_dir) {
    int32_t dir = (int32_t)(int8_t)dir_byte;
    if (dir > 0) {
        return 1;
    }
    if (dir < 0) {
        return -1;
    }
    return fallback_dir >= 0 ? 1 : -1;
}

static inline int32_t lgfx_attack_move_dir_to_limit_i32(int32_t curr_v, int32_t target_v, int32_t dir, int32_t speed_px) {
    int32_t step = speed_px < 1 ? 1 : speed_px;
    if (dir > 0) {
        if (curr_v >= target_v) {
            return curr_v;
        }
        int32_t next_v = curr_v + step;
        return next_v > target_v ? target_v : next_v;
    }
    if (curr_v <= target_v) {
        return curr_v;
    }
    int32_t next_v = curr_v - step;
    return next_v < target_v ? target_v : next_v;
}

static inline bool lgfx_attack_reached_dir_i32(int32_t curr_v, int32_t target_v, int32_t dir) {
    return dir > 0 ? (curr_v >= target_v) : (curr_v <= target_v);
}

static inline void lgfx_attack_set_scripted_orb(uint8_t *orb, int32_t slot_i, int32_t x, int32_t y) {
    orb[0] = 4u;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = 1u;
    lgfx_band_wr_i16(orb + 4, x);
    lgfx_band_wr_i16(orb + 6, y);
    lgfx_band_wr_i16(orb + 8, kMonkOrbRadius);
    lgfx_band_wr_i16(orb + 10, x);
    lgfx_band_wr_i16(orb + 12, y);
}

static inline void lgfx_attack_set_detached_orb(uint8_t *orb, int32_t slot_i, int32_t x, int32_t y) {
    orb[0] = 1u;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = 1u;
    lgfx_band_wr_i16(orb + 4, x);
    lgfx_band_wr_i16(orb + 6, y);
    lgfx_band_wr_i16(orb + 8, kMonkOrbRadius);
    lgfx_band_wr_i16(orb + 10, x);
    lgfx_band_wr_i16(orb + 12, y);
}

static inline void lgfx_attack_set_orbit_orb(uint8_t *orb, int32_t slot_i) {
    orb[0] = 0u;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = 1u;
    lgfx_band_wr_i16(orb + 8, kMonkOrbRadius);
}

static inline void lgfx_attack_set_final_orb(uint8_t *orb, int32_t slot_i, int32_t x, int32_t y) {
    orb[0] = (uint8_t)kMonkOrbFinalMode;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = 1u;
    lgfx_band_wr_i16(orb + 4, x);
    lgfx_band_wr_i16(orb + 6, y);
    lgfx_band_wr_i16(orb + 8, kMonkOrbFinalOrbitRadius);
    lgfx_band_wr_i16(orb + 10, x);
    lgfx_band_wr_i16(orb + 12, y);
}

static inline void lgfx_attack_set_player_orbit_orb(uint8_t *orb, int32_t slot_i, int32_t x, int32_t y, int32_t angle_step) {
    orb[0] = (uint8_t)kMonkOrbPlayerOrbitMode;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = (uint8_t)(angle_step & 0xFF);
    lgfx_band_wr_i16(orb + 4, x);
    lgfx_band_wr_i16(orb + 6, y);
    lgfx_band_wr_i16(orb + 8, kMonkOrbPlayerOrbitRadius);
    lgfx_band_wr_i16(orb + 10, x);
    lgfx_band_wr_i16(orb + 12, y);
}

static inline bool lgfx_final_orb_hits_monk(uint8_t *row, int32_t orb_x, int32_t orb_y) {
    int32_t monk_x = lgfx_band_rd_i16(row + 0);
    int32_t monk_y = lgfx_band_rd_i16(row + 2);
    int32_t monk_w = lgfx_band_rd_i16(row + 4);
    int32_t monk_h = lgfx_band_rd_i16(row + 6);
    if (monk_w < 1) monk_w = 32;
    if (monk_h < 1) monk_h = 48;
    return orb_x < (monk_x + monk_w)
        && (orb_x + kMonkOrbW) > monk_x
        && orb_y < (monk_y + monk_h)
        && (orb_y + kMonkOrbH) > monk_y;
}

static inline bool lgfx_final_orb_swept_hits_monk(uint8_t *row, int32_t from_x, int32_t from_y, int32_t to_x, int32_t to_y) {
    if (lgfx_final_orb_hits_monk(row, to_x, to_y)) {
        return true;
    }
    if (lgfx_final_orb_hits_monk(row, from_x, from_y)) {
        return false;
    }
    int32_t dx = to_x - from_x;
    int32_t dy = to_y - from_y;
    int32_t steps = lgfx_band_abs_i32(dx);
    int32_t y_steps = lgfx_band_abs_i32(dy);
    if (y_steps > steps) {
        steps = y_steps;
    }
    steps = (steps + 7) / 8;
    if (steps < 2) {
        return false;
    }
    for (int32_t step = 1; step < steps; ++step) {
        int32_t x = from_x + ((dx * step) / steps);
        int32_t y = from_y + ((dy * step) / steps);
        if (lgfx_final_orb_hits_monk(row, x, y)) {
            return true;
        }
    }
    return false;
}

static inline void lgfx_final_pos_from_center_for_radius(
    int32_t center_x,
    int32_t center_y,
    int32_t angle_step,
    int32_t radius_px,
    int32_t *orb_x,
    int32_t *orb_y
) {
    int32_t idx = angle_step % kMonkOrbFinalTableSize;
    if (idx < 0) {
        idx += kMonkOrbFinalTableSize;
    }
    if (radius_px < 0) {
        radius_px = 0;
    }
    int32_t cx = center_x + ((kMonkOrbFinalCos[idx] * radius_px) / kMonkOrbFinalScale);
    int32_t cy = center_y - ((kMonkOrbFinalSin[idx] * radius_px) / kMonkOrbFinalScale);
    *orb_x = cx - (kMonkOrbW / 2);
    *orb_y = cy - (kMonkOrbH / 2);
}

static inline int32_t lgfx_final_angle_for_center(
    int32_t center_x,
    int32_t center_y,
    int32_t orb_x,
    int32_t orb_y
) {
    int32_t rel_x = (orb_x + (kMonkOrbW / 2)) - center_x;
    int32_t rel_y = center_y - (orb_y + (kMonkOrbH / 2));
    int32_t best_idx = 0;
    int32_t best_dot = -2147483647;
    for (int32_t idx = 0; idx < kMonkOrbFinalTableSize; ++idx) {
        int32_t dot = (rel_x * kMonkOrbFinalCos[idx]) + (rel_y * kMonkOrbFinalSin[idx]);
        if (idx == 0 || dot > best_dot) {
            best_dot = dot;
            best_idx = idx;
        }
    }
    return best_idx;
}

static inline int32_t lgfx_final_angle_for_pos(
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h,
    int32_t orb_x,
    int32_t orb_y
) {
    return lgfx_final_angle_for_center(player_x + (player_w / 2), player_y + (player_h / 2), orb_x, orb_y);
}

static inline int32_t lgfx_final_random_angle_step(int32_t enemy_i, int32_t slot_i, int32_t total_step, int32_t orb_x, int32_t orb_y) {
    uint32_t seed = (uint32_t)esp_timer_get_time();
    seed ^= ((uint32_t)(enemy_i + 1) * 1103515245u);
    seed ^= ((uint32_t)(slot_i + 17) * 2654435761u);
    seed ^= ((uint32_t)(orb_x & 0xFFFF) << 16) ^ (uint32_t)(orb_y & 0xFFFF);
    seed ^= (uint32_t)(total_step * 2246822519u);
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return (int32_t)(seed % (uint32_t)kMonkOrbFinalTableSize);
}

static inline int32_t lgfx_final_step_toward(int32_t value, int32_t target, int32_t step) {
    if (value < target) {
        int32_t next = value + step;
        return next > target ? target : next;
    }
    if (value > target) {
        int32_t next = value - step;
        return next < target ? target : next;
    }
    return value;
}

static inline void lgfx_final_write_monk_pos(uint8_t *row, int32_t wx, int32_t wy) {
    lgfx_band_wr_i16(row + 0, wx);
    lgfx_band_wr_i16(row + 2, wy);
}

static inline int32_t lgfx_final_speed_px_from_hover(uint8_t *hover) {
    int32_t speed_q8 = hover != nullptr ? lgfx_band_rd_i16(hover + 9) : kMonkOrbFinalDefaultMonkSpeedQ8;
    if (speed_q8 <= 0) speed_q8 = kMonkOrbFinalDefaultMonkSpeedQ8;
    int32_t speed_px = (speed_q8 + 128) / 256;
    return speed_px < 1 ? 1 : speed_px;
}

static inline void lgfx_final_lock_monk_waypoint(uint8_t *row, uint8_t *hover, int32_t center_x, int32_t center_y) {
    if (hover == nullptr) {
        return;
    }
    int32_t ow = lgfx_band_rd_i16(row + 4);
    int32_t oh = lgfx_band_rd_i16(row + 6);
    if (ow < 1) ow = 32;
    if (oh < 1) oh = 48;
    int32_t target_x = center_x - (ow / 2);
    int32_t target_y = center_y - (oh / 2);
    lgfx_band_wr_i16(hover + 0, target_x);
    lgfx_band_wr_i16(hover + 2, target_y);
    lgfx_band_wr_i16(hover + 4, target_y);
    hover[8] = kMonkHoverStateFinalLocked;
}

static inline bool lgfx_final_move_linear(int32_t *x, int32_t *y, int32_t target_x, int32_t target_y, int32_t speed_px) {
    if (speed_px < 1) speed_px = 1;
    int32_t dx = target_x - *x;
    int32_t dy = target_y - *y;
    int32_t dist_sq = (dx * dx) + (dy * dy);
    int32_t dist = lgfx_attack_isqrt_i32(dist_sq);
    if (dist <= speed_px || dist <= 0) {
        *x = target_x;
        *y = target_y;
        return true;
    }
    int32_t step_x = (dx * speed_px) / dist;
    int32_t step_y = (dy * speed_px) / dist;
    if (step_x == 0 && dx != 0) step_x = dx > 0 ? 1 : -1;
    if (step_y == 0 && dy != 0) step_y = dy > 0 ? 1 : -1;
    *x += step_x;
    *y += step_y;
    return false;
}

static inline void lgfx_final_update_player_orbit_orb(
    uint8_t *orb,
    int32_t slot_i,
    int32_t player_x,
    int32_t player_y,
    int32_t player_w,
    int32_t player_h
) {
    int32_t angle_step = ((int32_t)orb[3] + 1) % kMonkOrbFinalTableSize;
    int32_t center_x = player_x + (player_w / 2);
    int32_t center_y = player_y + (player_h / 2);
    int32_t target_x = 0;
    int32_t target_y = 0;
    lgfx_final_pos_from_center_for_radius(center_x, center_y, angle_step, kMonkOrbPlayerOrbitRadius, &target_x, &target_y);
    lgfx_attack_set_player_orbit_orb(orb, slot_i, target_x, target_y, angle_step);
}

static inline void lgfx_final_lock_monk_pos(uint8_t *row, uint8_t *hover, int32_t wx, int32_t wy, int32_t center_x, int32_t center_y) {
    lgfx_final_write_monk_pos(row, wx, wy);
    if (hover != nullptr) {
        lgfx_final_lock_monk_waypoint(row, hover, center_x, center_y);
    }
}

static inline bool lgfx_final_glide_monk(
    uint8_t *row,
    uint8_t *hover,
    uint8_t *atk,
    int32_t target_center_x,
    int32_t target_center_y,
    int32_t *center_x,
    int32_t *center_y
) {
    int32_t ow = lgfx_band_rd_i16(row + 4);
    int32_t oh = lgfx_band_rd_i16(row + 6);
    if (ow < 1) ow = 32;
    if (oh < 1) oh = 48;
    int32_t target_x = target_center_x - (ow / 2);
    int32_t target_y = target_center_y - (oh / 2);
    int32_t curr_x = lgfx_band_rd_i16(row + 0);
    int32_t curr_y = lgfx_band_rd_i16(row + 2);
    int32_t start_x = curr_x;
    int32_t start_y = curr_y;
    uint16_t glide_frame = 0;
    if (atk != nullptr) {
        start_x = lgfx_band_rd_i16(atk + 26);
        start_y = lgfx_band_rd_i16(atk + 28);
        glide_frame = (uint16_t)atk[30] | ((uint16_t)atk[31] << 8);
    }
    int32_t dx = target_x - start_x;
    int32_t dy = target_y - start_y;
    int32_t dist = lgfx_attack_isqrt_i32((dx * dx) + (dy * dy));
    int32_t next_x = target_x;
    int32_t next_y = target_y;
    if (dist > 0) {
        if (glide_frame < 0xFFFFu) glide_frame = (uint16_t)(glide_frame + 1u);
        int32_t speed_q8 = hover != nullptr ? lgfx_band_rd_i16(hover + 9) : kMonkOrbFinalDefaultMonkSpeedQ8;
        if (speed_q8 <= 0) speed_q8 = kMonkOrbFinalDefaultMonkSpeedQ8;
        int64_t progress_q8 = (int64_t)glide_frame * (int64_t)speed_q8;
        int64_t dist_q8 = (int64_t)dist * 256LL;
        if (progress_q8 < dist_q8) {
            next_x = start_x + (int32_t)(((int64_t)dx * progress_q8) / dist_q8);
            next_y = start_y + (int32_t)(((int64_t)dy * progress_q8) / dist_q8);
        }
    }
    if (atk != nullptr) {
        atk[30] = (uint8_t)(glide_frame & 0xFFu);
        atk[31] = (uint8_t)((glide_frame >> 8) & 0xFFu);
    }
    lgfx_final_lock_monk_pos(row, hover, next_x, next_y, target_center_x, target_center_y);
    *center_x = next_x + (ow / 2);
    *center_y = next_y + (oh / 2);
    return next_x == target_x && next_y == target_y;
}

static inline void lgfx_final_set_monk_center(uint8_t *row, uint8_t *hover, int32_t center_x, int32_t center_y) {
    int32_t ow = lgfx_band_rd_i16(row + 4);
    int32_t oh = lgfx_band_rd_i16(row + 6);
    if (ow < 1) ow = 32;
    if (oh < 1) oh = 48;
    lgfx_final_lock_monk_pos(row, hover, center_x - (ow / 2), center_y - (oh / 2), center_x, center_y);
}

static inline void lgfx_band_wr_u32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static inline uint32_t lgfx_band_rd_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline void lgfx_final_velocity_for_angle(int32_t angle_step, int32_t speed_px, int32_t *vx, int32_t *vy) {
    int32_t idx = angle_step % kMonkOrbFinalTableSize;
    if (idx < 0) idx += kMonkOrbFinalTableSize;
    if (speed_px < 2) speed_px = kMonkOrbFinalRushSpeed;
    int32_t out_vx = (kMonkOrbFinalCos[idx] * speed_px) / kMonkOrbFinalScale;
    int32_t out_vy = -(kMonkOrbFinalSin[idx] * speed_px) / kMonkOrbFinalScale;
    if (out_vx == 0 && kMonkOrbFinalCos[idx] != 0) out_vx = kMonkOrbFinalCos[idx] > 0 ? 1 : -1;
    if (out_vy == 0 && kMonkOrbFinalSin[idx] != 0) out_vy = kMonkOrbFinalSin[idx] > 0 ? -1 : 1;
    if (out_vx == 0 && out_vy == 0) out_vx = speed_px;
    *vx = out_vx;
    *vy = out_vy;
}

static inline void lgfx_final_step_bounce(
    int32_t *x,
    int32_t *y,
    int32_t *vx,
    int32_t *vy,
    int32_t left,
    int32_t top,
    int32_t right,
    int32_t bottom
) {
    int32_t nx = *x + *vx;
    int32_t ny = *y + *vy;
    if (nx < left) {
        nx = left + (left - nx);
        *vx = -*vx;
    } else if (nx > right) {
        nx = right - (nx - right);
        *vx = -*vx;
    }
    if (ny < top) {
        ny = top + (top - ny);
        *vy = -*vy;
    } else if (ny > bottom) {
        ny = bottom - (ny - bottom);
        *vy = -*vy;
    }
    *x = nx;
    *y = ny;
}

static inline bool lgfx_final_scan_orbs(
    uint8_t *orbs,
    int32_t orb_stride,
    int32_t enemy_i,
    int32_t per_enemy_orbs,
    int32_t active_slot,
    bool allow_final_modes,
    int32_t *slot_out
) {
    int32_t candidate_count = 0;
    int32_t lost_count = 0;
    int32_t candidate_slot = -1;
    for (int32_t si = 0; si < per_enemy_orbs; ++si) {
        uint8_t *orb = orbs + ((size_t)((enemy_i * per_enemy_orbs) + si) * (size_t)orb_stride);
        uint8_t mode = orb[0];
        bool candidate = mode == 0u;
        if (allow_final_modes && si == active_slot && (mode == (uint8_t)kMonkOrbFinalMode || mode == 4u)) {
            candidate = true;
        }
        if (candidate) {
            candidate_count += 1;
            candidate_slot = si;
        } else if (mode == 8u) {
            lost_count += 1;
        } else {
            return false;
        }
    }
    if (candidate_count == 1 && lost_count == 4) {
        *slot_out = candidate_slot;
        return true;
    }
    return false;
}

static inline void lgfx_final_reset_attack(uint8_t *atk, bool has_dive_fields) {
    atk[0] = 0u;
    atk[2] = 0xFFu;
    atk[3] = 0xFFu;
    atk[12] = 0u;
    atk[13] = 0u;
    if (has_dive_fields) {
        atk[16] = 0xFFu;
        atk[17] = 0u;
    }
}

static inline void lgfx_final_release_monk_waypoint(uint8_t *hover) {
    if (hover != nullptr && hover[8] == kMonkHoverStateFinalLocked) {
        hover[8] = 1u;
    }
}

static inline int32_t lgfx_pulse_radius_for_step(int32_t start_radius, int32_t target_radius, int32_t step, int32_t total) {
    if (total <= 0) {
        return target_radius;
    }
    if (step < 0) step = 0;
    if (step > total) step = total;
    return start_radius + (((target_radius - start_radius) * step) / total);
}

static inline void lgfx_pulse_set_orb_radius(uint8_t *orb, int32_t slot_i, uint8_t mode, int32_t radius_px) {
    if (radius_px < kMonkOrbRadius) radius_px = kMonkOrbRadius;
    if (radius_px > kMonkOrbPulseRadius) radius_px = kMonkOrbPulseRadius;
    orb[0] = mode;
    orb[1] = (uint8_t)(slot_i & 0xFF);
    orb[2] = 0u;
    orb[3] = 1u;
    lgfx_band_wr_i16(orb + 8, radius_px);
}

static inline int32_t lgfx_pulse_stagger_delay_for_order(int32_t order) {
    if (order < 0) {
        order = 0;
    }
    int32_t delay = order * kMonkOrbPulseStaggerDelay;
    return delay > kMonkOrbPulseStaggerMaxDelay ? kMonkOrbPulseStaggerMaxDelay : delay;
}

static inline int32_t lgfx_pulse_order_for_slot_mask(uint8_t slot_mask, int32_t slot_i) {
    if (slot_i < 0 || slot_i >= 8 || ((slot_mask >> slot_i) & 0x01u) == 0u) {
        return 0;
    }
    int32_t order = 0;
    for (int32_t si = 0; si < slot_i; ++si) {
        if (((slot_mask >> si) & 0x01u) != 0u) {
            order += 1;
        }
    }
    return order;
}

static inline uint8_t lgfx_pulse_mode_for_step(int32_t step, int32_t *radius_px) {
    if (step < 0) {
        *radius_px = kMonkOrbRadius;
        return 6u;
    }
    if (step < kMonkOrbPulseExpandFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbRadius, kMonkOrbPulseRadius, step, kMonkOrbPulseExpandFrames);
        return 5u;
    }
    step -= kMonkOrbPulseExpandFrames;
    if (step < kMonkOrbPulseHoldFrames) {
        *radius_px = kMonkOrbPulseRadius;
        return 6u;
    }
    step -= kMonkOrbPulseHoldFrames;
    if (step < kMonkOrbPulseShrinkFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbPulseRadius, kMonkOrbRadius, step, kMonkOrbPulseShrinkFrames);
        return 5u;
    }
    *radius_px = kMonkOrbRadius;
    return 0u;
}

static inline int32_t lgfx_pulse_double_total_frames() {
    return kMonkOrbPulseExpandFrames
        + kMonkOrbPulseDoubleHoldFrames
        + kMonkOrbPulseDoubleMidShrinkFrames
        + kMonkOrbPulseDoubleReexpandFrames
        + kMonkOrbPulseDoubleHoldFrames
        + kMonkOrbPulseShrinkFrames;
}

static inline int32_t lgfx_pulse_double_final_shrink_start() {
    return kMonkOrbPulseExpandFrames
        + kMonkOrbPulseDoubleHoldFrames
        + kMonkOrbPulseDoubleMidShrinkFrames
        + kMonkOrbPulseDoubleReexpandFrames
        + kMonkOrbPulseDoubleHoldFrames;
}

static inline uint8_t lgfx_pulse_double_mode_for_step(int32_t step, int32_t *radius_px) {
    if (step < 0) {
        *radius_px = kMonkOrbRadius;
        return 6u;
    }
    if (step < kMonkOrbPulseExpandFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbRadius, kMonkOrbPulseRadius, step, kMonkOrbPulseExpandFrames);
        return 5u;
    }
    step -= kMonkOrbPulseExpandFrames;
    if (step < kMonkOrbPulseDoubleHoldFrames) {
        *radius_px = kMonkOrbPulseRadius;
        return 5u;
    }
    step -= kMonkOrbPulseDoubleHoldFrames;
    if (step < kMonkOrbPulseDoubleMidShrinkFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbPulseRadius, kMonkOrbRadius, step, kMonkOrbPulseDoubleMidShrinkFrames);
        return 5u;
    }
    step -= kMonkOrbPulseDoubleMidShrinkFrames;
    if (step < kMonkOrbPulseDoubleReexpandFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbRadius, kMonkOrbPulseRadius, step, kMonkOrbPulseDoubleReexpandFrames);
        return 5u;
    }
    step -= kMonkOrbPulseDoubleReexpandFrames;
    if (step < kMonkOrbPulseDoubleHoldFrames) {
        *radius_px = kMonkOrbPulseRadius;
        return 5u;
    }
    step -= kMonkOrbPulseDoubleHoldFrames;
    if (step < kMonkOrbPulseShrinkFrames) {
        *radius_px = lgfx_pulse_radius_for_step(kMonkOrbPulseRadius, kMonkOrbRadius, step, kMonkOrbPulseShrinkFrames);
        return 5u;
    }
    *radius_px = kMonkOrbRadius;
    return 0u;
}

static mp_obj_t lgfx_update_monk_attack_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 14 && n_args != 16 && n_args != 18 && n_args != 21) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 14, 16, 18 or 21 args"));
    }

    mp_buffer_info_t attack_info;
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t monk_hover_info;
    mp_buffer_info_t monk_orbs_info;
    mp_get_buffer_raise(args[0], &attack_info, MP_BUFFER_RW);
    mp_int_t attack_stride = mp_obj_get_int(args[1]);
    mp_int_t attack_count = mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &enemy_rows_info, MP_BUFFER_RW);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[4]);
    mp_int_t enemy_count = mp_obj_get_int(args[5]);
    mp_get_buffer_raise(args[6], &monk_hover_info, MP_BUFFER_RW);
    mp_int_t monk_hover_stride = mp_obj_get_int(args[7]);
    mp_int_t monk_hover_count = mp_obj_get_int(args[8]);
    mp_get_buffer_raise(args[9], &monk_orbs_info, MP_BUFFER_RW);
    mp_int_t orb_stride = mp_obj_get_int(args[10]);
    mp_int_t orb_count = mp_obj_get_int(args[11]);
    bool attack_enabled = mp_obj_is_true(args[12]);
    mp_int_t speed_px = mp_obj_get_int(args[13]);
    mp_int_t player_x = 0;
    mp_int_t player_y = 0;
    mp_int_t player_w = kMonkOrbW;
    mp_int_t player_h = kMonkOrbH;
    mp_int_t camera_x_arg = 0;
    mp_int_t view_w_arg = 320;
    mp_int_t view_h_arg = 240;
    if (n_args >= 16) {
        player_x = mp_obj_get_int(args[14]);
        player_w = mp_obj_get_int(args[15]);
        if (player_w < 1) {
            player_w = kMonkOrbW;
        }
    }
    if (n_args >= 18) {
        player_y = mp_obj_get_int(args[16]);
        player_h = mp_obj_get_int(args[17]);
        if (player_h < 1) {
            player_h = kMonkOrbH;
        }
    }
    if (n_args >= 21) {
        camera_x_arg = mp_obj_get_int(args[18]);
        view_w_arg = mp_obj_get_int(args[19]);
        view_h_arg = mp_obj_get_int(args[20]);
        if (view_w_arg < 64) view_w_arg = 320;
        if (view_h_arg < 64) view_h_arg = 240;
    }

    if (attack_stride < 16 || enemy_row_stride < 12 || monk_hover_stride < 9 || orb_stride < 16 || attack_count < 0 || enemy_count < 0 || monk_hover_count < 0 || orb_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid monk attack dims"));
    }
    if (attack_info.len < (size_t)attack_stride * (size_t)attack_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk attack buf too small"));
    }
    if (enemy_rows_info.len < (size_t)enemy_row_stride * (size_t)enemy_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (monk_hover_info.len < (size_t)monk_hover_stride * (size_t)monk_hover_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk hover buf too small"));
    }
    if (monk_orbs_info.len < (size_t)orb_stride * (size_t)orb_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb buf too small"));
    }
    if (speed_px < 1) {
        speed_px = 6;
    }
    (void)player_x;
    (void)player_y;
    (void)player_w;
    (void)player_h;

    uint8_t *attack = (uint8_t *)attack_info.buf;
    uint8_t *enemy_rows = (uint8_t *)enemy_rows_info.buf;
    uint8_t *monk_hover = (uint8_t *)monk_hover_info.buf;
    uint8_t *orbs = (uint8_t *)monk_orbs_info.buf;
    const uint8_t moving_cd = 0xFFu;
    const int32_t per_enemy_orbs = 5;
    const int32_t left_x = 1600;
    const int32_t right_x = 1904;
    const int32_t left_y = 160;
    const int32_t right_y = 144;
    int32_t changed = 0;
    int32_t limit = attack_count;
    if (limit > enemy_count) limit = enemy_count;
    if (limit > monk_hover_count) limit = monk_hover_count;
    int32_t orb_enemy_limit = orb_count / per_enemy_orbs;
    if (limit > orb_enemy_limit) limit = orb_enemy_limit;

    for (int32_t ei = 0; ei < limit; ++ei) {
        uint8_t *atk = attack + ((size_t)ei * (size_t)attack_stride);
        uint8_t *row = enemy_rows + ((size_t)ei * (size_t)enemy_row_stride);
        uint8_t *hover = monk_hover + ((size_t)ei * (size_t)monk_hover_stride);
        uint8_t phase = atk[0];
        uint8_t prev_cd = atk[1];
        uint8_t current_cd = hover[8];
        int32_t slot_left = (int32_t)(int8_t)atk[2];
        int32_t slot_right = (int32_t)(int8_t)atk[3];
        int32_t pulse_step = (int32_t)atk[2] | ((int32_t)atk[13] << 8);
        int32_t pulse_attack_index = (int32_t)atk[15];
        bool has_dive_fields = attack_stride >= 24;
        int32_t slot_dive = has_dive_fields ? (int32_t)(int8_t)atk[16] : -1;
        uint8_t dive_phase = has_dive_fields ? atk[17] : 0u;
        bool dive_active = has_dive_fields && dive_phase != 0u && slot_dive >= 0 && slot_dive < per_enemy_orbs;
        int32_t dive_target_x = (int32_t)player_x + ((int32_t)player_w / 2) - (kMonkOrbW / 2);

        if (!row[8] || !row[11]) {
            int32_t final_slot = (int32_t)(int8_t)atk[2];
            if (phase == (uint8_t)kMonkOrbFinalPhaseDeath && final_slot >= 0 && final_slot < per_enemy_orbs) {
                uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
                if (orb[0] == (uint8_t)kMonkOrbPlayerOrbitMode) {
                    lgfx_final_update_player_orbit_orb(orb, final_slot, (int32_t)player_x, (int32_t)player_y, (int32_t)player_w, (int32_t)player_h);
                    atk[1] = current_cd;
                    changed += 1;
                    continue;
                }
            }
            if (phase >= 4u && phase <= 6u) {
                for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                    if (orb[0] == 5u || orb[0] == 6u) lgfx_attack_set_orbit_orb(orb, si);
                }
            } else if (phase >= (uint8_t)kMonkOrbFinalPhaseOrbit && phase <= (uint8_t)kMonkOrbFinalPhaseDeath) {
                int32_t final_slot = (int32_t)(int8_t)atk[2];
                if (final_slot >= 0 && final_slot < per_enemy_orbs) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
                    if (orb[0] == (uint8_t)kMonkOrbFinalMode || orb[0] == 4u || orb[0] == (uint8_t)kMonkOrbPlayerOrbitMode) lgfx_attack_set_orbit_orb(orb, final_slot);
                }
            }
            atk[0] = 0u;
            lgfx_final_release_monk_waypoint(hover);
            atk[1] = current_cd;
            atk[2] = 0xFFu;
            atk[3] = 0xFFu;
            atk[12] = 0u;
            atk[13] = 0u;
            if (has_dive_fields) {
                atk[16] = 0xFFu;
                atk[17] = 0u;
            }
            continue;
        }

        if (!attack_enabled) {
            if (phase != 0u) {
                if (phase >= 4u && phase <= 6u) {
                    for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                        uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                        if (orb[0] == 5u || orb[0] == 6u) lgfx_attack_set_orbit_orb(orb, si);
                    }
                } else if (phase >= (uint8_t)kMonkOrbFinalPhaseOrbit && phase <= (uint8_t)kMonkOrbFinalPhaseDeath) {
                    int32_t final_slot = (int32_t)(int8_t)atk[2];
                    if (final_slot >= 0 && final_slot < per_enemy_orbs) {
                        uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
                        if (orb[0] == (uint8_t)kMonkOrbFinalMode || orb[0] == 4u || orb[0] == (uint8_t)kMonkOrbPlayerOrbitMode) lgfx_attack_set_orbit_orb(orb, final_slot);
                    }
                }
                if (slot_left >= 0 && slot_left < per_enemy_orbs) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_left) * (size_t)orb_stride);
                    if (orb[0] == 4u) lgfx_attack_set_detached_orb(orb, slot_left, lgfx_band_rd_i16(orb + 10), lgfx_band_rd_i16(orb + 12));
                }
                if (slot_right >= 0 && slot_right < per_enemy_orbs) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_right) * (size_t)orb_stride);
                    if (orb[0] == 4u) lgfx_attack_set_detached_orb(orb, slot_right, lgfx_band_rd_i16(orb + 10), lgfx_band_rd_i16(orb + 12));
                }
                if (dive_active) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_dive) * (size_t)orb_stride);
                    if (orb[0] == 4u) lgfx_attack_set_detached_orb(orb, slot_dive, lgfx_band_rd_i16(orb + 10), lgfx_band_rd_i16(orb + 12));
                }
            }
            atk[0] = 0u;
            lgfx_final_release_monk_waypoint(hover);
            atk[1] = current_cd;
            atk[2] = 0xFFu;
            atk[3] = 0xFFu;
            atk[12] = 0u;
            atk[13] = 0u;
            if (has_dive_fields) {
                atk[16] = 0xFFu;
                atk[17] = 0u;
            }
            continue;
        }

        if (phase >= (uint8_t)kMonkOrbFinalPhaseOrbit && phase <= (uint8_t)kMonkOrbFinalPhaseDeath) {
            int32_t final_slot = (int32_t)(int8_t)atk[2];
            int32_t checked_slot = -1;
            bool final_death_phase = phase == (uint8_t)kMonkOrbFinalPhaseDeath;
            bool final_ready = final_slot >= 0 && final_slot < per_enemy_orbs && n_args >= 18;
            if (final_ready && !final_death_phase) {
                final_ready = lgfx_final_scan_orbs(orbs, (int32_t)orb_stride, ei, per_enemy_orbs, final_slot, true, &checked_slot)
                    && checked_slot == final_slot;
            }
            if (final_ready && final_death_phase) {
                for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                    uint8_t mode = orb[0];
                    if (si == final_slot) {
                        final_ready = mode == (uint8_t)kMonkOrbPlayerOrbitMode || mode == (uint8_t)kMonkOrbFinalMode || mode == 4u;
                    } else if (mode != 8u) {
                        final_ready = false;
                    }
                }
            }
            if (!final_ready) {
                if (final_slot >= 0 && final_slot < per_enemy_orbs) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
                    if (orb[0] == (uint8_t)kMonkOrbFinalMode || orb[0] == 4u || orb[0] == (uint8_t)kMonkOrbPlayerOrbitMode) {
                        lgfx_attack_set_orbit_orb(orb, final_slot);
                    }
                }
                lgfx_final_reset_attack(atk, has_dive_fields);
                lgfx_final_release_monk_waypoint(hover);
                atk[1] = current_cd;
                LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_CANCEL enemy=%d slot=%d\n", (int)ei, (int)final_slot);
                changed += 1;
                continue;
            }

            uint8_t *final_orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
            int32_t total_step = (int32_t)atk[12] | ((int32_t)atk[13] << 8);
            int32_t local_step = (int32_t)atk[14];
            int32_t angle_step = (int32_t)atk[3];
            if (angle_step < 0 || angle_step >= kMonkOrbFinalTableSize) {
                angle_step = 0;
            }
            int32_t monk_center_x = 0;
            int32_t monk_center_y = 0;
            int32_t waypoint_x = attack_stride >= 32 ? lgfx_band_rd_i16(atk + 18) : ((int32_t)camera_x_arg + ((int32_t)view_w_arg / 2));
            int32_t waypoint_y = attack_stride >= 32 ? lgfx_band_rd_i16(atk + 20) : ((int32_t)view_h_arg / 2);
            if (waypoint_y < 0) waypoint_y = 0;
            int32_t view_left = (int32_t)camera_x_arg;
            int32_t view_top = 0;
            int32_t view_right = view_left + (int32_t)view_w_arg - kMonkOrbW;
            int32_t view_bottom = (int32_t)view_h_arg - kMonkOrbH;
            if (view_right < view_left) view_right = view_left;
            if (view_bottom < view_top) view_bottom = view_top;
            bool monk_centered = false;
            if (phase == (uint8_t)kMonkOrbFinalPhaseDeath) {
                lgfx_final_lock_monk_waypoint((uint8_t *)row, hover, waypoint_x, waypoint_y);
                monk_center_x = waypoint_x;
                monk_center_y = waypoint_y;
                monk_centered = true;
            } else if (phase == (uint8_t)kMonkOrbFinalPhaseOrbit) {
                monk_centered = lgfx_final_glide_monk((uint8_t *)row, hover, attack_stride >= 32 ? atk : nullptr, waypoint_x, waypoint_y, &monk_center_x, &monk_center_y);
            } else {
                lgfx_final_set_monk_center((uint8_t *)row, hover, waypoint_x, waypoint_y);
                monk_center_x = waypoint_x;
                monk_center_y = waypoint_y;
                monk_centered = true;
            }
            int32_t ox = lgfx_band_rd_i16(final_orb + 10);
            int32_t oy = lgfx_band_rd_i16(final_orb + 12);
            int32_t start_x = lgfx_band_rd_i16(atk + 4);
            int32_t start_y = lgfx_band_rd_i16(atk + 6);
            int32_t path_vx = lgfx_band_rd_i16(atk + 8);
            int32_t path_vy = lgfx_band_rd_i16(atk + 10);
            uint32_t next_rush_start_ms = 0u;
            if (!final_death_phase && final_orb[2] == kMonkOrbFinalSwapPending) {
                final_orb[2] = 0u;
                if ((phase == (uint8_t)kMonkOrbFinalPhaseRush || phase == (uint8_t)kMonkOrbFinalPhaseEject) && (path_vx != 0 || path_vy != 0)) {
                    phase = (uint8_t)kMonkOrbFinalPhaseEject;
                    start_x = ox;
                    start_y = oy;
                    local_step = 0;
                    total_step = 0;
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_SWAP_EJECT enemy=%d slot=%d vx=%d vy=%d\n", (int)ei, (int)final_slot, (int)path_vx, (int)path_vy);
                } else {
                    angle_step = lgfx_final_angle_for_center(monk_center_x, monk_center_y, ox, oy);
                    phase = (uint8_t)kMonkOrbFinalPhaseOrbit;
                    local_step = 0;
                    total_step = 0;
                }
            }
            uint8_t next_phase = phase;
            int32_t next_total_step = total_step;
            int32_t next_local_step = local_step;
            int32_t next_angle_step = angle_step;
            int32_t next_start_x = start_x;
            int32_t next_start_y = start_y;
            int32_t next_vx = path_vx;
            int32_t next_vy = path_vy;

            if (phase == (uint8_t)kMonkOrbFinalPhaseOrbit) {
                lgfx_final_pos_from_center_for_radius(monk_center_x, monk_center_y, angle_step, kMonkOrbFinalOrbitRadius, &ox, &oy);
                lgfx_attack_set_final_orb(final_orb, final_slot, ox, oy);
                next_total_step += 1;
                next_local_step += 1;
                next_angle_step = (angle_step + 1) % kMonkOrbFinalTableSize;
                if (monk_centered) {
                    int32_t chosen_angle = lgfx_final_random_angle_step((int32_t)ei, final_slot, total_step, ox, oy);
                    lgfx_final_velocity_for_angle(chosen_angle, kMonkOrbFinalRushSpeed, &next_vx, &next_vy);
                    next_angle_step = chosen_angle;
                    next_start_x = ox;
                    next_start_y = oy;
                    next_phase = (uint8_t)kMonkOrbFinalPhaseRush;
                    next_total_step = 0;
                    next_local_step = 0;
                    lgfx_attack_set_scripted_orb(final_orb, final_slot, ox, oy);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_RANDOM_RUSH enemy=%d slot=%d vx=%d vy=%d\n", (int)ei, (int)final_slot, (int)next_vx, (int)next_vy);
                }
            } else if (phase == (uint8_t)kMonkOrbFinalPhaseRush) {
                if (path_vx == 0 && path_vy == 0) {
                    int32_t chosen_angle = lgfx_final_random_angle_step((int32_t)ei, final_slot, total_step, ox, oy);
                    lgfx_final_velocity_for_angle(chosen_angle, kMonkOrbFinalRushSpeed, &next_vx, &next_vy);
                    next_angle_step = chosen_angle;
                    path_vx = next_vx;
                    path_vy = next_vy;
                }
                lgfx_final_step_bounce(&ox, &oy, &path_vx, &path_vy, view_left, view_top, view_right, view_bottom);
                next_vx = path_vx;
                next_vy = path_vy;
                next_start_x = ox;
                next_start_y = oy;
                lgfx_attack_set_scripted_orb(final_orb, final_slot, ox, oy);
                next_total_step += 1;
                next_local_step += 1;
            } else if (phase == (uint8_t)kMonkOrbFinalPhaseEject) {
                int32_t prev_ox = ox;
                int32_t prev_oy = oy;
                if (path_vx == 0 && path_vy == 0) {
                    int32_t chosen_angle = lgfx_final_random_angle_step((int32_t)ei, final_slot, total_step, ox, oy);
                    lgfx_final_velocity_for_angle(chosen_angle, kMonkOrbFinalRushSpeed, &next_vx, &next_vy);
                    next_angle_step = chosen_angle;
                    path_vx = next_vx;
                    path_vy = next_vy;
                }
                lgfx_final_step_bounce(&ox, &oy, &path_vx, &path_vy, view_left, view_top, view_right, view_bottom);
                lgfx_attack_set_scripted_orb(final_orb, final_slot, ox, oy);
                next_start_x = ox;
                next_start_y = oy;
                next_vx = path_vx;
                next_vy = path_vy;
                next_total_step += 1;
                next_local_step += 1;
                if (lgfx_final_orb_swept_hits_monk((uint8_t *)row, prev_ox, prev_oy, ox, oy)) {
                    next_phase = (uint8_t)kMonkOrbFinalPhaseDeath;
                    next_total_step = 0;
                    next_local_step = 0;
                    next_start_x = ox;
                    next_start_y = oy;
                    next_vx = 0;
                    next_vy = 0;
                    next_rush_start_ms = 0u;
                    row[9] = 0u;
                    int32_t player_orbit_angle = lgfx_final_angle_for_pos(
                        (int32_t)player_x,
                        (int32_t)player_y,
                        (int32_t)player_w,
                        (int32_t)player_h,
                        ox,
                        oy
                    );
                    next_angle_step = player_orbit_angle;
                    int32_t player_center_x = (int32_t)player_x + ((int32_t)player_w / 2);
                    int32_t player_center_y = (int32_t)player_y + ((int32_t)player_h / 2);
                    lgfx_final_pos_from_center_for_radius(player_center_x, player_center_y, player_orbit_angle, kMonkOrbPlayerOrbitRadius, &ox, &oy);
                    lgfx_attack_set_player_orbit_orb(final_orb, final_slot, ox, oy, player_orbit_angle);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_DEATH enemy=%d slot=%d x=%d y=%d\n", (int)ei, (int)final_slot, (int)ox, (int)oy);
                }
            } else if (phase == (uint8_t)kMonkOrbFinalPhaseDeath) {
                lgfx_final_update_player_orbit_orb(final_orb, final_slot, (int32_t)player_x, (int32_t)player_y, (int32_t)player_w, (int32_t)player_h);
                next_total_step += 1;
                next_local_step += 1;
                if (next_local_step >= kMonkOrbFinalDeathFrames) {
                    row[8] = 0u;
                    row[9] = 0u;
                    lgfx_final_release_monk_waypoint(hover);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_DEATH_DONE enemy=%d slot=%d\n", (int)ei, (int)final_slot);
                }
            }

            atk[0] = next_phase;
            atk[2] = (uint8_t)final_slot;
            atk[3] = (uint8_t)(next_angle_step & 0xFF);
            lgfx_band_wr_i16(atk + 4, next_start_x);
            lgfx_band_wr_i16(atk + 6, next_start_y);
            lgfx_band_wr_i16(atk + 8, next_vx);
            lgfx_band_wr_i16(atk + 10, next_vy);
            atk[12] = (uint8_t)(next_total_step & 0xFF);
            atk[13] = (uint8_t)((next_total_step >> 8) & 0xFF);
            atk[14] = (uint8_t)(next_local_step & 0xFF);
            atk[1] = current_cd;
            if (attack_stride >= 32) {
                lgfx_band_wr_i16(atk + 18, waypoint_x);
                lgfx_band_wr_i16(atk + 20, waypoint_y);
                lgfx_band_wr_u32(atk + 22, next_rush_start_ms);
            }
            changed += 1;
            continue;
        }

        if (phase == 0u && !dive_active && n_args >= 18) {
            int32_t final_slot = -1;
            if (lgfx_final_scan_orbs(orbs, (int32_t)orb_stride, ei, per_enemy_orbs, -1, false, &final_slot)) {
                uint8_t *final_orb = orbs + ((size_t)((ei * per_enemy_orbs) + final_slot) * (size_t)orb_stride);
                int32_t monk_center_x = 0;
                int32_t monk_center_y = 0;
                monk_center_x = (int32_t)camera_x_arg + ((int32_t)view_w_arg / 2);
                monk_center_y = (int32_t)view_h_arg / 2;
                int32_t curr_x = lgfx_band_rd_i16(final_orb + 10);
                int32_t curr_y = lgfx_band_rd_i16(final_orb + 12);
                int32_t ow = lgfx_band_rd_i16(row + 4);
                int32_t oh = lgfx_band_rd_i16(row + 6);
                if (ow < 1) ow = 32;
                if (oh < 1) oh = 48;
                int32_t curr_monk_center_x = lgfx_band_rd_i16(row + 0) + (ow / 2);
                int32_t curr_monk_center_y = lgfx_band_rd_i16(row + 2) + (oh / 2);
                int32_t angle_step = lgfx_final_angle_for_center(curr_monk_center_x, curr_monk_center_y, curr_x, curr_y);
                lgfx_final_pos_from_center_for_radius(curr_monk_center_x, curr_monk_center_y, angle_step, kMonkOrbFinalOrbitRadius, &curr_x, &curr_y);
                atk[0] = (uint8_t)kMonkOrbFinalPhaseOrbit;
                atk[2] = (uint8_t)final_slot;
                atk[3] = (uint8_t)(angle_step & 0xFF);
                lgfx_band_wr_i16(atk + 4, 0);
                lgfx_band_wr_i16(atk + 6, 0);
                lgfx_band_wr_i16(atk + 8, 0);
                lgfx_band_wr_i16(atk + 10, 0);
                atk[12] = 0u;
                atk[13] = 0u;
                atk[14] = 0u;
                if (has_dive_fields) {
                    atk[16] = 0xFFu;
                    atk[17] = 0u;
                }
                if (attack_stride >= 32) {
                    lgfx_band_wr_i16(atk + 18, monk_center_x);
                    lgfx_band_wr_i16(atk + 20, monk_center_y);
                    lgfx_band_wr_u32(atk + 22, 0u);
                    lgfx_band_wr_i16(atk + 26, lgfx_band_rd_i16(row + 0));
                    lgfx_band_wr_i16(atk + 28, lgfx_band_rd_i16(row + 2));
                    atk[30] = 0u;
                    atk[31] = 0u;
                }
                lgfx_final_lock_monk_waypoint((uint8_t *)row, hover, monk_center_x, monk_center_y);
                lgfx_attack_set_final_orb(final_orb, final_slot, curr_x, curr_y);
                atk[1] = current_cd;
                LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_FINAL_START enemy=%d slot=%d x=%d y=%d\n", (int)ei, (int)final_slot, (int)curr_x, (int)curr_y);
                changed += 1;
                continue;
            }
        }

        if (phase == 0u && !dive_active && prev_cd == moving_cd && current_cd > 0u && current_cd != moving_cd) {
            uint8_t cadence = atk[14];
            atk[14] = (uint8_t)((cadence + 1u) & 0x01u);
            if ((cadence & 0x01u) != 0u) {
                LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_SKIP enemy=%d cadence=%d\n", (int)ei, (int)cadence);
                atk[1] = current_cd;
                continue;
            }
            if (pulse_attack_index != 0) {
                int32_t pulse_orbit_count = 0;
                int32_t pulse_lost_count = 0;
                bool has_blocking_orb = false;
                for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                    uint8_t orb_mode = orb[0];
                    if (orb_mode == 0u) {
                        pulse_orbit_count += 1;
                    } else if (orb_mode == 8u) {
                        pulse_lost_count += 1;
                    } else {
                        has_blocking_orb = true;
                    }
                }
                bool can_pulse = pulse_orbit_count >= 3 && !has_blocking_orb;
                if (can_pulse) {
                    bool stagger_pulse = pulse_orbit_count == 3 && pulse_lost_count == 2;
                    uint8_t pulse_slot_mask = 0u;
                    atk[15] = 0u;
                    atk[0] = 4u;
                    atk[2] = 0u;
                    atk[12] = stagger_pulse ? 3u : 0u;
                    atk[13] = 0u;
                    int32_t pulse_order = 0;
                    for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                        uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                        if (orb[0] == 0u) {
                            if (stagger_pulse) {
                                pulse_slot_mask = (uint8_t)(pulse_slot_mask | (uint8_t)(1u << si));
                            }
                            uint8_t pulse_mode = stagger_pulse && pulse_order > 0 ? 6u : 5u;
                            lgfx_pulse_set_orb_radius(orb, si, pulse_mode, kMonkOrbRadius);
                            pulse_order += 1;
                        }
                    }
                    atk[3] = stagger_pulse ? pulse_slot_mask : 0xFFu;
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_START enemy=%d active=%d lost=%d stagger=%d double=%d mask=%d radius=%d target=%d expand=%d hold=%d shrink=%d\n",
                        (int)ei,
                        (int)pulse_orbit_count,
                        (int)pulse_lost_count,
                        stagger_pulse ? 1 : 0,
                        stagger_pulse ? 1 : 0,
                        (int)pulse_slot_mask,
                        (int)kMonkOrbRadius,
                        (int)kMonkOrbPulseRadius,
                        (int)kMonkOrbPulseExpandFrames,
                        (int)kMonkOrbPulseHoldFrames,
                        (int)kMonkOrbPulseShrinkFrames);
                    phase = 4u;
                    slot_left = -1;
                    slot_right = -1;
                    changed += 1;
                } else if (!has_blocking_orb && pulse_lost_count > 0) {
                    atk[15] = 0u;
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_SKIP enemy=%d reason=too_few_orbs active=%d lost=%d\n", (int)ei, (int)pulse_orbit_count, (int)pulse_lost_count);
                } else {
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_SKIP enemy=%d reason=orbs_not_ready active=%d lost=%d\n", (int)ei, (int)pulse_orbit_count, (int)pulse_lost_count);
                    atk[1] = current_cd;
                    continue;
                }
            }
            if (phase != 0u) {
                atk[1] = current_cd;
                continue;
            }
            int32_t best_left_slot = -1;
            int32_t best_right_slot = -1;
            int32_t best_left_x = 0;
            int32_t best_right_x = 0;
            int32_t type1_orbit_count = 0;
            int32_t type1_lost_count = 0;
            bool type1_has_blocking_orb = false;
            for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                uint8_t orb_mode = orb[0];
                if (orb_mode == 8u) {
                    type1_lost_count += 1;
                    continue;
                }
                if (orb_mode != 0u) {
                    type1_has_blocking_orb = true;
                    continue;
                }
                type1_orbit_count += 1;
                int32_t x = lgfx_band_rd_i16(orb + 10);
                if (best_left_slot < 0 || x < best_left_x) {
                    best_left_slot = si;
                    best_left_x = x;
                }
                if (best_right_slot < 0 || x > best_right_x) {
                    best_right_slot = si;
                    best_right_x = x;
                }
            }
            if (best_left_slot >= 0 && best_right_slot >= 0 && best_left_slot != best_right_slot) {
                int32_t best_dive_slot = -1;
                int32_t best_dive_dist = 0;
                bool enable_type1_dive = has_dive_fields && n_args >= 16 && type1_orbit_count == 3 && type1_lost_count == 2 && !type1_has_blocking_orb;
                if (enable_type1_dive) {
                    for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                        if (si == best_left_slot || si == best_right_slot) {
                            continue;
                        }
                        uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                        if (orb[0] != 0u) {
                            continue;
                        }
                        int32_t x = lgfx_band_rd_i16(orb + 10);
                        int32_t dist = lgfx_attack_abs_i32(x - dive_target_x);
                        if (best_dive_slot < 0 || dist < best_dive_dist) {
                            best_dive_slot = si;
                            best_dive_dist = dist;
                        }
                    }
                }
                uint8_t *left_orb = orbs + ((size_t)((ei * per_enemy_orbs) + best_left_slot) * (size_t)orb_stride);
                uint8_t *right_orb = orbs + ((size_t)((ei * per_enemy_orbs) + best_right_slot) * (size_t)orb_stride);
                int32_t ly = lgfx_band_rd_i16(left_orb + 12);
                int32_t ry = lgfx_band_rd_i16(right_orb + 12);
                atk[0] = 1u;
                atk[2] = (uint8_t)best_left_slot;
                atk[3] = (uint8_t)best_right_slot;
                atk[12] = (uint8_t)(int8_t)-1;
                atk[13] = (uint8_t)(int8_t)1;
                lgfx_band_wr_i16(atk + 4, left_x);
                lgfx_band_wr_i16(atk + 6, right_x);
                lgfx_band_wr_i16(atk + 8, ly);
                lgfx_band_wr_i16(atk + 10, ry);
                lgfx_attack_set_scripted_orb(left_orb, best_left_slot, lgfx_band_rd_i16(left_orb + 10), ly);
                lgfx_attack_set_scripted_orb(right_orb, best_right_slot, lgfx_band_rd_i16(right_orb + 10), ry);
                if (best_dive_slot >= 0) {
                    uint8_t *dive_orb = orbs + ((size_t)((ei * per_enemy_orbs) + best_dive_slot) * (size_t)orb_stride);
                    int32_t dx = lgfx_band_rd_i16(dive_orb + 10);
                    int32_t dy = lgfx_band_rd_i16(dive_orb + 12);
                    atk[16] = (uint8_t)best_dive_slot;
                    atk[17] = 1u;
                    lgfx_band_wr_i16(atk + 18, dive_target_x);
                    lgfx_band_wr_i16(atk + 20, kMonkAttackDiveDropY);
                    lgfx_band_wr_i16(atk + 22, kMonkAttackDiveTopY);
                    lgfx_attack_set_scripted_orb(dive_orb, best_dive_slot, dx, dy);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_START3 enemy=%d left_slot=%d right_slot=%d dive_slot=%d lx=%d ly=%d rx=%d ry=%d dx=%d dy=%d\n",
                        (int)ei,
                        (int)best_left_slot,
                        (int)best_right_slot,
                        (int)best_dive_slot,
                        (int)lgfx_band_rd_i16(left_orb + 10),
                        (int)ly,
                        (int)lgfx_band_rd_i16(right_orb + 10),
                        (int)ry,
                        (int)dx,
                        (int)dy);
                } else if (has_dive_fields) {
                    atk[16] = 0xFFu;
                    atk[17] = 0u;
                }
                if (has_dive_fields && !enable_type1_dive) {
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_START2 enemy=%d orbit=%d lost=%d blocking=%d\n", (int)ei, (int)type1_orbit_count, (int)type1_lost_count, type1_has_blocking_orb ? 1 : 0);
                }
                LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_START enemy=%d left_slot=%d right_slot=%d lx=%d ly=%d rx=%d ry=%d\n",
                    (int)ei,
                    (int)best_left_slot,
                    (int)best_right_slot,
                    (int)lgfx_band_rd_i16(left_orb + 10),
                    (int)ly,
                    (int)lgfx_band_rd_i16(right_orb + 10),
                    (int)ry);
                phase = 1u;
                slot_left = best_left_slot;
                slot_right = best_right_slot;
                atk[15] = 1u;
                changed += 1;
            }
        }

        if (dive_active) {
            uint8_t *dive_orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_dive) * (size_t)orb_stride);
            bool active = dive_orb[0] == 4u;
            if (!active) {
                atk[16] = 0xFFu;
                atk[17] = 0u;
                dive_active = false;
                changed += 1;
            } else {
                int32_t dx = lgfx_band_rd_i16(dive_orb + 10);
                int32_t dy = lgfx_band_rd_i16(dive_orb + 12);
                if (dive_phase == 1u) {
                    dy = lgfx_attack_move_toward_i32(dy, kMonkAttackDiveTopY, speed_px);
                    lgfx_attack_set_scripted_orb(dive_orb, slot_dive, dx, dy);
                    if (dy == kMonkAttackDiveTopY) {
                        atk[17] = 2u;
                        lgfx_band_wr_i16(atk + 18, dive_target_x);
                        LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_DIVE_PHASE enemy=%d phase=track slot=%d tx=%d\n", (int)ei, (int)slot_dive, (int)dive_target_x);
                    }
                    changed += 1;
                } else if (dive_phase == 2u) {
                    lgfx_band_wr_i16(atk + 18, dive_target_x);
                    dx = lgfx_attack_move_toward_i32(dx, dive_target_x, speed_px);
                    lgfx_attack_set_scripted_orb(dive_orb, slot_dive, dx, dy);
                    if (lgfx_attack_abs_i32(dx - dive_target_x) == 0) {
                        atk[17] = 3u;
                        lgfx_band_wr_i16(atk + 20, kMonkAttackDiveDropY);
                        LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_DIVE_PHASE enemy=%d phase=drop slot=%d y=%d\n", (int)ei, (int)slot_dive, (int)kMonkAttackDiveDropY);
                    }
                    changed += 1;
                } else if (dive_phase == 3u) {
                    int32_t target_y = lgfx_band_rd_i16(atk + 20);
                    dy = lgfx_attack_move_toward_i32(dy, target_y, speed_px);
                    lgfx_attack_set_scripted_orb(dive_orb, slot_dive, dx, dy);
                    if (dy == target_y) {
                        lgfx_attack_set_detached_orb(dive_orb, slot_dive, dx, dy);
                        atk[16] = 0xFFu;
                        atk[17] = 0u;
                        LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_DIVE_DONE enemy=%d slot=%d x=%d y=%d\n", (int)ei, (int)slot_dive, (int)dx, (int)dy);
                    }
                    changed += 1;
                } else {
                    atk[16] = 0xFFu;
                    atk[17] = 0u;
                    changed += 1;
                }
            }
        }

        if (phase >= 4u && phase <= 6u) {
            int32_t pulse_active_count = 0;
            for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                if (orb[0] == 5u || orb[0] == 6u) {
                    pulse_active_count += 1;
                }
            }
            if (pulse_active_count <= 0) {
                atk[0] = 0u;
                atk[2] = 0xFFu;
                atk[3] = 0xFFu;
                atk[12] = 0u;
                atk[13] = 0u;
                LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_EMPTY enemy=%d\n", (int)ei);
                changed += 1;
            } else {
                bool double_pulse = atk[12] == 3u;
                uint8_t pulse_slot_mask = double_pulse ? atk[3] : 0u;
                bool stagger_pulse = double_pulse && pulse_slot_mask != 0u;
                int32_t total_step = (int32_t)pulse_step + 1;
                int32_t total_duration = kMonkOrbPulseExpandFrames + kMonkOrbPulseHoldFrames + kMonkOrbPulseShrinkFrames;
                if (double_pulse) {
                    total_duration = lgfx_pulse_double_total_frames() + kMonkOrbPulseStaggerMaxDelay;
                }
                for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                    uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                    if (orb[0] == 5u || orb[0] == 6u) {
                        int32_t local_step = total_step;
                        if (stagger_pulse) {
                            int32_t pulse_order = lgfx_pulse_order_for_slot_mask(pulse_slot_mask, si);
                            local_step -= lgfx_pulse_stagger_delay_for_order(pulse_order);
                        }
                        int32_t radius_px = kMonkOrbRadius;
                        uint8_t mode = double_pulse ? lgfx_pulse_double_mode_for_step(local_step, &radius_px) : lgfx_pulse_mode_for_step(local_step, &radius_px);
                        if (mode == 0u) {
                            mode = double_pulse ? 5u : 6u;
                        }
                        lgfx_pulse_set_orb_radius(orb, si, mode, radius_px);
                    }
                }
                uint8_t next_phase = 4u;
                int32_t shrink_start = double_pulse ? lgfx_pulse_double_final_shrink_start() : (kMonkOrbPulseExpandFrames + kMonkOrbPulseHoldFrames);
                if (total_step >= shrink_start) {
                    next_phase = 6u;
                } else if (total_step >= kMonkOrbPulseExpandFrames) {
                    next_phase = 5u;
                }
                if (next_phase != phase) {
#if LGFX_MONK_ATTACK_DEBUG_LOG
                    const char *phase_name = next_phase == 5u ? "hold" : "shrink";
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_PHASE enemy=%d phase=%s stagger=%d double=%d\n", (int)ei, phase_name, stagger_pulse ? 1 : 0, double_pulse ? 1 : 0);
#endif
                }
                if (total_step >= total_duration) {
                    for (int32_t si = 0; si < per_enemy_orbs; ++si) {
                        uint8_t *orb = orbs + ((size_t)((ei * per_enemy_orbs) + si) * (size_t)orb_stride);
                        if (orb[0] == 5u || orb[0] == 6u) lgfx_attack_set_orbit_orb(orb, si);
                    }
                    atk[0] = 0u;
                    atk[2] = 0xFFu;
                    atk[3] = 0xFFu;
                    atk[12] = 0u;
                    atk[13] = 0u;
                    if (has_dive_fields) {
                        atk[16] = 0xFFu;
                        atk[17] = 0u;
                    }
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PULSE_DONE enemy=%d stagger=%d double=%d\n", (int)ei, stagger_pulse ? 1 : 0, double_pulse ? 1 : 0);
                } else {
                    atk[0] = next_phase;
                    atk[2] = (uint8_t)(total_step & 0xFF);
                    atk[13] = (uint8_t)((total_step >> 8) & 0xFF);
                }
                changed += 1;
            }
        }

        if (phase != 0u && slot_left >= 0 && slot_left < per_enemy_orbs && slot_right >= 0 && slot_right < per_enemy_orbs) {
            uint8_t *left_orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_left) * (size_t)orb_stride);
            uint8_t *right_orb = orbs + ((size_t)((ei * per_enemy_orbs) + slot_right) * (size_t)orb_stride);
            bool left_active = left_orb[0] == 4u;
            bool right_active = right_orb[0] == 4u;
            if (!left_active && !right_active) {
                atk[0] = 0u;
                atk[2] = 0xFFu;
                atk[3] = 0xFFu;
                atk[12] = 0u;
                atk[13] = 0u;
                atk[1] = current_cd;
                changed += 1;
                if (!dive_active) {
                    continue;
                }
            }
            int32_t lx = lgfx_band_rd_i16(left_orb + 10);
            int32_t ly = lgfx_band_rd_i16(left_orb + 12);
            int32_t rx = lgfx_band_rd_i16(right_orb + 10);
            int32_t ry = lgfx_band_rd_i16(right_orb + 12);
            int32_t target_lx = lgfx_band_rd_i16(atk + 4);
            int32_t target_rx = lgfx_band_rd_i16(atk + 6);
            int32_t target_ly = lgfx_band_rd_i16(atk + 8);
            int32_t target_ry = lgfx_band_rd_i16(atk + 10);

            if (phase == 1u) {
                int32_t left_dir = lgfx_attack_dir_i32(atk[12], -1);
                int32_t right_dir = lgfx_attack_dir_i32(atk[13], 1);
                if (left_active) {
                    lx = lgfx_attack_move_dir_to_limit_i32(lx, target_lx, left_dir, speed_px);
                    lgfx_attack_set_scripted_orb(left_orb, slot_left, lx, ly);
                }
                if (right_active) {
                    rx = lgfx_attack_move_dir_to_limit_i32(rx, target_rx, right_dir, speed_px);
                    lgfx_attack_set_scripted_orb(right_orb, slot_right, rx, ry);
                }
                bool left_reached = !left_active || lgfx_attack_reached_dir_i32(lx, target_lx, left_dir);
                bool right_reached = !right_active || lgfx_attack_reached_dir_i32(rx, target_rx, right_dir);
                if (left_reached && right_reached) {
                    atk[0] = 2u;
                    lgfx_band_wr_i16(atk + 8, left_y);
                    lgfx_band_wr_i16(atk + 10, right_y);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PHASE enemy=%d phase=drop left_slot=%d right_slot=%d\n",
                        (int)ei,
                        (int)slot_left,
                        (int)slot_right);
                }
                changed += 1;
            } else if (phase == 2u) {
                if (left_active) {
                    ly = lgfx_attack_move_toward_i32(ly, target_ly, speed_px);
                    lgfx_attack_set_scripted_orb(left_orb, slot_left, lx, ly);
                }
                if (right_active) {
                    ry = lgfx_attack_move_toward_i32(ry, target_ry, speed_px);
                    lgfx_attack_set_scripted_orb(right_orb, slot_right, rx, ry);
                }
                bool left_reached = !left_active || lgfx_attack_abs_i32(ly - target_ly) == 0;
                bool right_reached = !right_active || lgfx_attack_abs_i32(ry - target_ry) == 0;
                if (left_reached && right_reached) {
                    atk[0] = 3u;
                    atk[12] = (uint8_t)(int8_t)1;
                    atk[13] = (uint8_t)(int8_t)-1;
                    lgfx_band_wr_i16(atk + 4, right_x);
                    lgfx_band_wr_i16(atk + 6, left_x);
                    LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_PHASE enemy=%d phase=sweep left_slot=%d right_slot=%d\n",
                        (int)ei,
                        (int)slot_left,
                        (int)slot_right);
                }
                changed += 1;
            } else if (phase == 3u) {
                int32_t left_dir = lgfx_attack_dir_i32(atk[12], 1);
                int32_t right_dir = lgfx_attack_dir_i32(atk[13], -1);
                if (left_active) {
                    lx = lgfx_attack_move_dir_to_limit_i32(lx, target_lx, left_dir, speed_px);
                    lgfx_attack_set_scripted_orb(left_orb, slot_left, lx, ly);
                }
                if (right_active) {
                    rx = lgfx_attack_move_dir_to_limit_i32(rx, target_rx, right_dir, speed_px);
                    lgfx_attack_set_scripted_orb(right_orb, slot_right, rx, ry);
                }
                bool left_reached = !left_active || lgfx_attack_reached_dir_i32(lx, target_lx, left_dir);
                bool right_reached = !right_active || lgfx_attack_reached_dir_i32(rx, target_rx, right_dir);
                if (left_reached && right_reached) {
                    if (left_active) lgfx_attack_set_detached_orb(left_orb, slot_left, lx, ly);
                    if (right_active) lgfx_attack_set_detached_orb(right_orb, slot_right, rx, ry);
                    atk[0] = 0u;
                    atk[2] = 0xFFu;
                    atk[3] = 0xFFu;
                    atk[12] = 0u;
                    atk[13] = 0u;
                    if (dive_active) {
                        LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_DONE_WAIT_DIVE enemy=%d left_slot=%d right_slot=%d dive_slot=%d\n",
                            (int)ei,
                            (int)slot_left,
                            (int)slot_right,
                            (int)slot_dive);
                    } else {
                        LGFX_MONK_ATTACK_LOGF("MONK_ATTACK_NATIVE_DONE enemy=%d left_slot=%d right_slot=%d\n",
                            (int)ei,
                            (int)slot_left,
                            (int)slot_right);
                    }
                }
                changed += 1;
            }
        }
        atk[1] = current_cd;
    }
    return mp_obj_new_int(changed);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_monk_attack_native_obj, 14, 21, lgfx_update_monk_attack_native);

} // extern "C"

#endif // !defined(NO_QSTR)
