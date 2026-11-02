// Test button plunger: cap on a split stem with two snap barbs. The cap lands on
// the panel at full travel: that is the hard stop. Print 4, cap on the bed.
include <../cad/params.scad>
include <../cad/lib.scad>

cap_t = btn_proud - btn_travel;
stem_len = btn_travel - tb_leaf_z; // cap underside to leaf, at rest
barb_z = rp_t + btn_travel;        // cap underside to barb shoulder

assert(cap_t >= 1.2, "cap too thin: btn_proud - btn_travel");

module test_button_plunger() {
    box(-tb_cap / 2, tb_cap / 2, -tb_cap / 2, tb_cap / 2, 0, cap_t);
    difference() {
        union() {
            box(-tb_stem / 2, tb_stem / 2, -tb_stem / 2, tb_stem / 2, cap_t, cap_t + stem_len);
            for (s = [-1, 1]) hull() {
                translate([-tb_stem / 2, s > 0 ? tb_stem / 2 - 0.1 : -tb_stem / 2 - tb_barb, cap_t + barb_z])
                    cube([tb_stem, tb_barb + 0.1, 0.1]);
                translate([-tb_stem / 2, s > 0 ? tb_stem / 2 - 0.1 : -tb_stem / 2, cap_t + barb_z + 3])
                    cube([tb_stem, 0.1, 0.1]);
            }
        }
        // slit so the barbs flex through the hole
        box(-tb_stem, tb_stem, -tb_slit / 2, tb_slit / 2, cap_t + 1, cap_t + stem_len + 1);
    }
}

test_button_plunger();
