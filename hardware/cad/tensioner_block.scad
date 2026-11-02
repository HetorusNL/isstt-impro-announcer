// Tensioner block: bolts to the rail outside a post; its push bolt moves the post inward. Print 2.
// Print orientation: closed Y face on the bed, T-nut pocket opening up.
include <params.scad>
include <lib.scad>

rotate([90, 0, 0]) translate([0, ten_w / 2, -ten_arm_z0]) tensioner_block();
