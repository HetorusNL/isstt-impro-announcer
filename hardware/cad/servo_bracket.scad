// Servo module bracket: holds the servo and plunger guide, slides up and down the carriage. Print 4.
// Print orientation: on a side wall.
include <params.scad>
include <lib.scad>

rotate([0, 90, 0]) translate([-br_w / 2, 0, -sleeve_z0]) servo_bracket();
