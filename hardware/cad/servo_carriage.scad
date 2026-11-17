// Servo module carriage: bolts to a rail face, keyed in the slot. Print 4.
// Print orientation: front face (the one the bracket slides on) on the bed. Nut pocket and slot key face up: no overhang.
include <params.scad>
include <lib.scad>

translate([0, -rail_z0, car_y1]) rotate([-90, 0, 0]) servo_carriage();
