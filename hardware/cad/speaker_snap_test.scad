// Cradle fit test: one cradle end per clearance, to tune spk_clear before printing the cradle.
// Print 1 plate, as laid out: end walls on the bed, no supports. The number under each end wall
// is its spk_clear (mm per side). Push one end of the speaker into each and pick the tightest
// one that still slides in, clicks past the hook and doesn't rattle. Set spk_clear in
// params.scad to that number. The hook height (spk_snap) is the same on all three.
include <params.scad>
include <lib.scad>

clears = [0.2, 0.4, 0.6];

for (i = [0 : len(clears) - 1]) let (c = clears[i]) translate([i * 75, 0, 0])
    // end wall's outer face on the bed, the cup and its snap tab pointing up
    translate([0, 0, c + cup_wall]) rotate([0, 90, 0]) difference() {
        spk_cup_end(spk_snap, c);
        // number, read from below
        translate([c + cup_wall - 0.6, 0, spk_h / 2 + 4]) rotate([90, 0, 90]) linear_extrude(1)
            mirror([1, 0, 0]) text(str(c), size = 6, halign = "center", valign = "center");
    }
