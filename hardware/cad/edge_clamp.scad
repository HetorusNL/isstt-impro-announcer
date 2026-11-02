// Padded edge clamp jaw, one per case side (the same part, turned 180 degrees). Print 2.
// Print orientation: on its Y face.
include <params.scad>
include <lib.scad>

rotate([90, 0, 0]) translate([0, jaw_w / 2, -jaw_z0]) edge_clamp();
