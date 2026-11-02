// Dummy flip cover for the covered buttons on the replica, hinged on a 1.75 mm
// filament pin, for the cover-opening check. Print 2, top on the bed.
include <../cad/params.scad>
include <../cad/lib.scad>

wall = 1.6;

module alarm_cover() {
    pin_z = cover_pin_z;
    difference() {
        union() {
            difference() {
                box(-cover_w / 2, cover_w / 2, -cover_d, 0, 0, cover_h);
                box(-cover_w / 2 + wall, cover_w / 2 - wall, -cover_d + wall, -wall, -1, cover_h - wall);
            }
            // hinge knuckle
            translate([-cover_w / 2, 0, pin_z]) rotate([0, 90, 0]) cylinder(r = 3, h = cover_w);
        }
        translate([-cover_w / 2 - 1, 0, pin_z]) rotate([0, 90, 0]) cylinder(d = 1.95, h = cover_w + 2);
    }
}

translate([0, 0, cover_h]) mirror([0, 0, 1]) alarm_cover();
