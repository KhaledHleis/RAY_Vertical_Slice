// Test CRT Shader - OBVIOUS scanlines
// If you see horizontal lines, the shader is working

#define PI 3.14159265

vec4 effect(vec4 color, Image tex, vec2 texture_coords, vec2 screen_coords) {
    // Sample texture
    vec3 col = Texel(tex, texture_coords).rgb;
    
    // Create VERY OBVIOUS scanlines
    float scanline = sin(texture_coords.y * 720.0 * PI) * 0.5 + 0.5;
    scanline = pow(scanline, 2.0);  // Make them darker
    scanline = mix(0.5, 1.0, scanline);  // Strong effect: 0.5 to 1.0
    
    col *= scanline;
    
    return vec4(col, 1.0);
}
