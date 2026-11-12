// Stop collars under the push bolt head: the collar sets the squeeze, so it sets the post position.
// One file prints the set, two of each thickness. Start with the nominal pair (no notch).
// Print orientation: flat. Check the thicknesses with calipers.
include <params.scad>
include <lib.scad>

for (i = [0 : len(ten_collar_steps) - 1], j = [0, 1])
    translate([i * (ten_collar_d + 3), j * (ten_collar_d + 3), 0]) tensioner_collar(ten_collar_steps[i]);
