// Servo module bracket: holds the servo and plunger guide, slides up and down the carriage. Print 4.
// Print orientation: upright, plunger guide end on the bed. No supports: the shelf bridges between the side walls.
include <params.scad>
include <lib.scad>

translate([0, 0, -sleeve_z0]) servo_bracket();
