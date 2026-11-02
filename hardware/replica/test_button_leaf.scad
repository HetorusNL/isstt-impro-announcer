// Test button spring: a printed leaf (cantilever). Its root pushes into the tunnel
// under the replica panel. Force comes from tb_leaf_t, calculated in params.scad.
// Print 4, flat on the bed.
include <../cad/params.scad>
include <../cad/lib.scad>

tip_past_stem = 6;

module test_button_leaf() {
    box(0, tb_root_l, -tb_leaf_b / 2, tb_leaf_b / 2, 0, tb_root_h);
    box(tb_root_l - 0.1, tb_root_l + tb_leaf_l + tip_past_stem, -tb_leaf_b / 2, tb_leaf_b / 2, tb_root_h - tb_leaf_t, tb_root_h);
}

translate([0, 0, tb_root_h]) mirror([0, 0, 1]) test_button_leaf();
