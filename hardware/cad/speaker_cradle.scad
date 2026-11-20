// Speaker cradle for the Earson ER-151, with the arm and the fixed half of the tube clamp. Print 1.
// Print orientation: beam and arm flat on the bed. Supports only under the low side of each cup (tree, build plate only). Tune the clearance first: speaker_snap_test.scad
include <params.scad>
include <lib.scad>

rotate([90, 0, 0]) translate([0, -spk_arm_y0, 0]) speaker_cradle();
