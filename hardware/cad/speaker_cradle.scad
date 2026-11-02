// Speaker cradle for the Earson ER-151, with the arm and the fixed half of the tube clamp. Print 1.
// Print orientation: with the beam on the bed. Use supports under the cups.
include <params.scad>
include <lib.scad>

rotate([90, 0, 0]) translate([0, -spk_arm_y0, 0]) speaker_cradle();
