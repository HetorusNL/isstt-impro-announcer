// Removable half of the gooseneck tube clamp. Print 1.
// Print orientation: flange on the bed.
include <params.scad>
include <lib.scad>

rotate([90, 0, 0]) translate([0, -clamp_gap / 2, 0]) speaker_clamp_cap();
