// The whole rig on the desk, default configuration. Not printed: a check and a
// picture. Contains the safety asserts: nothing enters the covered buttons'
// keep-out volumes. Keep-outs are drawn as translucent % volumes.
include <params.scad>
include <lib.scad>
include <hardware.scad>

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
echo(tensioner_travel = ten_travel, tensioner_z = ten_z, stop_collar_t = ten_collar_t, stop_collar_set = [for (s = ten_collar_steps) ten_collar_t + s], bracket_key_clearance = bracket_key_clearance);
echo(gauge_go = gauge_go, gauge_nogo = gauge_nogo);
echo(test_button_leaf_t = tb_leaf_t, test_button_force_N = tb_print_E * tb_leaf_b * pow(tb_leaf_t, 3) / (4 * pow(tb_leaf_l, 3)) * (tb_preload + btn_travel));

// ---- Picture -----------------------------------------------------------------
// Print colours (Bambu Lab PLA Basic). No red on the rig: red is for the alarm covers.
c_structure = "#101010";    // Black: jaws, tensioner, end caps, speaker holder
c_module = "#0A2989";       // Blue: carriage and bracket of the zone modules
c_spreken = "#FF9016";      // Pumpkin Orange: carriage and bracket of the SPREKEN module
c_moving = "#FEC600";       // Sunflower Yellow: cams and plungers
c_collar = "#00AE42";       // Bambu Green: nominal stop collar

module desk() {
    color("DimGray") difference() {
        translate([0, 0, case_rim_h - case_h]) cube([case_w, case_d, case_h]);
        box(case_rim_w, case_w - case_rim_w, case_rim_w, case_d - case_rim_w, 0, case_rim_h + 1);
    }
    for (b = buttons) {
        p = panel_xy(b[0]);
        covered = len([for (c = covered_buttons) if (c == b[0]) c]) > 0;
        color(covered ? "Red" : "WhiteSmoke")
            translate([p[0] - btn_w / 2, p[1] - btn_d / 2, 0]) cube([btn_w, btn_d, btn_proud]);
    }
}

module frame() {
    color("Silver") {
        translate([rail_x0, rail_y, rail_zc]) rotate([0, 90, 0]) ext2020(rail_len);
        for (x = [post_x_l, post_x_r]) translate([x, rail_y, post_z0]) ext2020(post_len);
    }
    // corner brackets, both sides of each post, with their bolts and nuts
    for (x = [post_x_l, post_x_r], s = [-1, 1])
        translate([x + s * ext / 2, rail_y, rail_z0]) mirror([s < 0 ? 1 : 0, 0, 0]) corner_joint();
    // cable clips on the rail's top slot, with their bolts and nuts
    for (x = clip_centres) translate([x - clip_len / 2, rail_y, rail_z1]) {
        color(c_structure) cable_clip();
        cable_clip_parts();
    }
    // end caps: rail ends and post bottoms, tongues into the profile
    color(c_structure) {
        translate([rail_x0 - 2, rail_y, rail_zc]) rotate([0, 90, 0]) end_cap();
        translate([rail_x0 + rail_len + 2, rail_y, rail_zc]) rotate([0, -90, 0]) end_cap();
        for (x = [post_x_l, post_x_r]) translate([x, rail_y, post_z0 - 2]) end_cap();
    }
    for (a = [[post_x_l + ext / 2, 0], [post_x_r - ext / 2, 180]])
        translate([a[0], rail_y, 0]) rotate(a[1]) {
            color(c_structure) edge_clamp();
            edge_clamp_parts();
        }
    // tensioners, clamped: the push bolt is seated on its collar, so the block stands
    // pad_squeeze further out than where its pad first touched the post
    for (a = [[post_x_l - ext / 2, 180], [post_x_r + ext / 2, 0]])
        translate([a[0], rail_y, 0]) rotate(a[1]) {
            color(c_structure) translate([0, 0, ten_z]) tensioner_pad();
            translate([pad_squeeze, 0, 0]) {
                color(c_structure) tensioner_block();
                tensioner_parts();
            }
        }
}

module servo_module(body = c_module) {
    color(body) servo_carriage();
    color(body) servo_bracket();
    color("#303030") translate([0, sv_base_y, z_shaft]) mg90s();
    // cam drawn at press: eccentric past horizontal, button bottomed out
    color(c_moving) translate([0, cam_back_y, z_shaft]) rotate([-90, 0, 0]) rotate(90 - cam_press_angle) servo_cam();
    color(c_moving) translate([0, mod_d, btn_proud - btn_travel]) servo_plunger();
    translate([0, mod_d, btn_proud - btn_travel]) plunger_dot();
    servo_module_parts();
}

desk();
frame();
for (a = actuated) {
    p = btn_xy(a);
    translate([p[0], rail_y, 0]) rotate(p[1] > rail_y ? 0 : 180) servo_module(a == "SPREKEN" ? c_spreken : c_module);
}
for (c = covered_buttons) {
    k = keepout_box(c);
    %translate(k[0]) cube(k[1] - k[0]);
}
