// Tensioner block: bolts to the rail outside a post; its push bolt moves the post inward. Print 2.
// Print orientation: the outer end on the bed, no supports. The head slot opens on the bed
// and the shoulder bridges over it. Drill out the thin skin in the shoulder hole with a 5 mm drill.
include <params.scad>
include <lib.scad>

translate([0, 0, ten_neck_x1]) rotate([0, 90, 0]) translate([0, 0, -ten_arm_z0]) tensioner_block();
