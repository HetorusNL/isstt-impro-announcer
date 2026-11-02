// The whole rig on the desk, default configuration. Not printed: a check and a
// picture. Contains the safety asserts: nothing enters the covered buttons'
// keep-out volumes. Keep-outs are drawn as translucent % volumes.
include <params.scad>
include <lib.scad>

// ---- Safety ------------------------------------------------------------------
for (c = covered_buttons) {
    k = keepout_box(c);
    assert(!overlap(rail_box(), k), str("rail enters the keep-out of ", c));
    assert(!overlap(post_box(post_x_l), k), str("left post/clamp enters the keep-out of ", c));
    assert(!overlap(post_box(post_x_r), k), str("right post/clamp enters the keep-out of ", c));
    assert(!overlap(tensioner_box(post_x_l), k), str("left tensioner enters the keep-out of ", c));
    assert(!overlap(tensioner_box(post_x_r), k), str("right tensioner enters the keep-out of ", c));
    for (a = actuated)
        assert(!overlap(module_box(a), k), str(a, " module enters the keep-out of ", c));
}

// ---- Stiffness and force numbers quoted in README.md --------------------------
load_all = len(actuated) * btn_force;
rail_defl_all = load_all * pow(post_span, 3) / (48 * ext_E * ext_I);
rail_defl_spreken = btn_force * pow(post_span, 3) / (48 * ext_E * ext_I);
pad_area = (jaw_w - 4) * (lip_z0 - jaw_z0 - 4);
pad_normal = pad_area * pad_stress;
pad_hold = 2 * pad_mu * pad_normal;
echo(rail_len = rail_len, post_len = post_len, post_span = post_span, rail_z0 = rail_z0, z_shaft = z_shaft, pl_len = pl_len);
echo(servo_stall_Nmm = sv_stall_nmm, press_torque_Nmm = press_torque, servo_margin = servo_margin);
echo(rail_defl_spreken_mm = rail_defl_spreken, rail_defl_all_mm = rail_defl_all);
clamp_margin = pad_hold / load_all;
echo(pad_area_mm2 = pad_area, pad_normal_N = pad_normal, clamp_hold_N = pad_hold, clamp_margin = clamp_margin);
// All four buttons at once is the safe upper limit; the normal peak is one button.
assert(clamp_margin >= 2, "pad friction holds less than 2x the press force of all actuated buttons");
echo(post_spacing_target = post_spacing_target, post_gap_target = jaw_case_x, post_gap_uncompressed = post_gap_uncompressed, post_gap_contact = post_gap_contact);
echo(tensioner_travel = ten_travel, tensioner_z = ten_z, stop_collar_t = ten_collar_t, bracket_key_clearance = bracket_key_clearance);
echo(gauge_go = gauge_go, gauge_nogo = gauge_nogo);
echo(test_button_leaf_t = tb_leaf_t, test_button_force_N = tb_print_E * tb_leaf_b * pow(tb_leaf_t, 3) / (4 * pow(tb_leaf_l, 3)) * (tb_preload + btn_travel));

// ---- Picture -----------------------------------------------------------------
module desk() {
    color("DimGray") difference() {
        translate([0, 0, case_rim_h - case_h]) cube([case_w, case_d, case_h]);
        box(case_rim_w, case_w - case_rim_w, case_rim_w, case_d - case_rim_w, 0, case_rim_h + 1);
    }
    for (b = buttons) {
        p = panel_xy(b[0]);
        covered = len([for (c = covered_buttons) if (c == b[0]) c]) > 0;
        color(covered ? "Red" : "WhiteSmoke")
            translate([p[0] - btn_size / 2, p[1] - btn_size / 2, 0]) cube([btn_size, btn_size, btn_proud]);
    }
}

module frame() {
    color("Silver") {
        translate([rail_x0, rail_y, rail_zc]) rotate([0, 90, 0]) ext2020(rail_len);
        for (x = [post_x_l, post_x_r]) translate([x, rail_y, post_z0]) ext2020(post_len);
    }
    // corner brackets, both sides of each post
    color("DarkGray") for (x = [post_x_l, post_x_r], s = [-1, 1])
        translate([x + s * (ext / 2 + bracket_leg / 2), rail_y, rail_z0 - bracket_leg / 2])
            cube([bracket_leg, ext, bracket_leg], center = true);
    color("Orange") {
        translate([post_x_l + ext / 2, rail_y, 0]) edge_clamp();
        translate([post_x_r - ext / 2, rail_y, 0]) rotate(180) edge_clamp();
    }
    color("Salmon") for (a = [[post_x_l - ext / 2, 180], [post_x_r + ext / 2, 0]])
        translate([a[0], rail_y, 0]) rotate(a[1]) {
            tensioner_block();
            translate([0, 0, ten_z]) tensioner_pad();
            translate([ten_head_x, 0, ten_z]) rotate([0, 90, 0]) tensioner_collar();
        }
}

module servo_module() {
    color("SkyBlue") servo_carriage();
    color("SteelBlue") servo_bracket();
    color("Black") translate([0, sv_base_y, z_shaft]) mg90s();
    // cam drawn at press: eccentric past horizontal, button bottomed out
    color("Gold") translate([0, cam_back_y, z_shaft]) rotate([-90, 0, 0]) rotate(90 - cam_press_angle) servo_cam();
    color("Tomato") translate([0, mod_d, btn_proud - btn_travel]) servo_plunger();
}

desk();
frame();
for (a = actuated) {
    p = btn_xy(a);
    translate([p[0], rail_y, 0]) rotate(p[1] > rail_y ? 0 : 180) servo_module();
}
for (c = covered_buttons) {
    k = keepout_box(c);
    %translate(k[0]) cube(k[1] - k[0]);
}
