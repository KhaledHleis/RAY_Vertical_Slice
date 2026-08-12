// CRT shader for LOVE 2D
// Curvature + scanlines + RGB phosphor mask + corner falloff + gamma.
// Nothing here depends on canvas size: scanlines and mask are keyed to
// screen_coords, so they stay pixel-locked whatever resolution you render at.
//
// Tune by editing the constants below. Set a strength to 0.0 to disable it.

// --- geometry -------------------------------------------------------------
const float CURVATURE      = 5.0;   // higher = flatter. ~4 strong, ~8 subtle, 0 handled below
const float CORNER_SIZE    = 0.015; // rounded corner radius
const float CORNER_SMOOTH  = 200.0; // higher = harder corner edge

// --- scanlines ------------------------------------------------------------
const float SCANLINE_PERIOD   = 3.0;  // one dark line every N physical pixels
const float SCANLINE_STRENGTH = 0.35; // 0 = off, 1 = fully black lines

// --- phosphor mask --------------------------------------------------------
const float MASK_STRENGTH = 0.25; // 0 = off. RGB triads, 3px wide

// --- colour ---------------------------------------------------------------
const float CRT_GAMMA     = 2.4;
const float MONITOR_GAMMA = 2.2;
const float SATURATION    = 1.0;  // 1 = unchanged, 0 = greyscale
const float BRIGHTNESS    = 1.25; // compensates for scanline+mask darkening

// Barrel distortion. Takes 0..1 uv, returns curved 0..1 uv.
vec2 curve(vec2 uv) {
    uv = uv * 2.0 - 1.0;
    vec2 offset = abs(uv.yx) / vec2(CURVATURE);
    uv += uv * offset * offset;
    return uv * 0.5 + 0.5;
}

// Rounded-corner falloff. Returns 1 inside, 0 outside, soft at the edge.
float corner(vec2 uv) {
    vec2 d = min(uv, vec2(1.0) - uv);
    vec2 cdist = vec2(CORNER_SIZE);
    d = cdist - min(d, cdist);
    return clamp((cdist.x - length(d)) * CORNER_SMOOTH, 0.0, 1.0);
}

vec3 saturate_rgb(vec3 c) {
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    return mix(vec3(lum), c, SATURATION);
}

vec4 effect(vec4 color, Image tex, vec2 texture_coords, vec2 screen_coords) {
    vec2 uv = (CURVATURE > 0.0) ? curve(texture_coords) : texture_coords;

    // Outside the tube after distortion: black bezel.
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        return vec4(0.0, 0.0, 0.0, 1.0);
    }

    // To linear-ish light before applying scanlines and mask, so the
    // darkening behaves like a real beam rather than crushing midtones.
    vec3 col = pow(Texel(tex, uv).rgb, vec3(CRT_GAMMA));

    // Scanlines: repeating soft dark band down the physical screen.
    float f = fract(screen_coords.y / SCANLINE_PERIOD);
    float line = smoothstep(0.0, 0.5, f) * smoothstep(1.0, 0.5, f);
    col *= mix(1.0 - SCANLINE_STRENGTH, 1.0, line);

    // Phosphor mask: 3px RGB triads. Each column dims two of three channels.
    if (MASK_STRENGTH > 0.0) {
        float m = mod(screen_coords.x, 3.0);
        vec3 mask = vec3(1.0 - MASK_STRENGTH);
        if (m < 1.0)      mask.r = 1.0;
        else if (m < 2.0) mask.g = 1.0;
        else              mask.b = 1.0;
        col *= mask;
    }

    col *= BRIGHTNESS;
    col *= corner(uv);

    col = saturate_rgb(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / MONITOR_GAMMA));

    return vec4(col, 1.0) * color;
}
