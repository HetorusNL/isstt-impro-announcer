// Servo module carriage: bolts to a rail face, keyed in the slot. Print 4.
// Print orientation: on its side.
include <params.scad>
include <lib.scad>

rotate([0, 90, 0]) translate([-car_w / 2, -car_y0, -rail_z0]) servo_carriage();
