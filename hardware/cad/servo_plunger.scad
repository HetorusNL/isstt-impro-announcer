// Guided plunger between cam and button. Print 4 plus spares.
// Print orientation: upright, collar on the bed, tip recess up.
include <params.scad>
include <lib.scad>

translate([0, 0, pl_len]) mirror([0, 0, 1]) servo_plunger();
