// Eccentric cam, fits over the trimmed stock horn. Print 4.
// Print orientation: front face on the bed.
include <params.scad>
include <lib.scad>

translate([0, 0, cam_t]) mirror([0, 0, 1]) servo_cam();
