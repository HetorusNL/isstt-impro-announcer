// Snap catch test: one cradle end per hook height, to tune spk_snap before printing the cradle.
// Print 1 plate, as laid out: end walls on the bed, no supports. The number under each end wall
// is its spk_snap. Push one end of the speaker into each and pick the one that clicks in and
// holds, but comes out by hand without forcing. Set spk_snap in params.scad to that number.
include <params.scad>
include <lib.scad>

snaps = [0.6, 1.0, 1.4];

for (i = [0 : len(snaps) - 1]) translate([i * 75, 0, 0])
    // end wall's outer face on the bed, the cup and its snap tab pointing up
    translate([0, 0, spk_clear + cup_wall]) rotate([0, 90, 0]) difference() {
        spk_cup_end(snaps[i]);
        // number, read from below
        translate([spk_clear + cup_wall - 0.6, 0, spk_h / 2 + 4]) rotate([90, 0, 90]) linear_extrude(1)
            mirror([1, 0, 0]) text(str(snaps[i]), size = 6, halign = "center", valign = "center");
    }
