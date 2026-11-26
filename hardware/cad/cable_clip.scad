// Cable clip: bolts into the rail's top slot with an M5x10 and a drop-in nut, and holds the
// servo leads along the rail. Push the leads in from the top, past the two lips.
// Print orientation: standing on its hoop end, as laid out: the lips print in the layer plane,
// so they flex along the layers. No supports. Copies: one per spare M5 nut.
include <params.scad>
include <lib.scad>

copies = 2;     // 20 M5 nuts: 18 for the rig and speaker clamp, 2 spare

for (i = [0 : copies - 1]) translate([i * (clip_w + 6), 0, 0])
    translate([0, 0, clip_len]) rotate([0, 90, 0]) cable_clip();
