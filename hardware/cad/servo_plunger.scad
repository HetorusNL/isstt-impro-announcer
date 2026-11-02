// Guided plunger between cam and button. Print 4 plus spares.
// Print orientation: lying on one flat.
include <params.scad>
include <lib.scad>

rotate([0, 90, 0]) translate([-pl_collar / 2, 0, 0]) servo_plunger();
