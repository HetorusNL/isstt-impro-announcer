// Bought parts and EVA pads, for the pictures: frame_assembly.scad and assembly_steps.scad.
// Not printed. Drawn at their measured sizes, with simplified shapes. Include after
// params.scad and lib.scad.

c_steel = "#8A8A8A";    // bolts and screws
c_nut = "#B08D57";      // drop-in nuts, so they stand out
c_eva = "#383E42";      // EVA foam, anthracite
c_alu_cast = "#A8A8A8"; // corner brackets

// ---- Bolts: head's underside at the origin, shank along +Z, head below --------
module phillips(d, depth) {
    for (a = [0, 90]) rotate(a) translate([-d / 2, -0.5, -0.01]) cube([d, 1, depth]);
}
module pan_head(d, len, head_d, head_h) {
    color(c_steel) difference() {
        union() {
            translate([0, 0, -head_h]) cylinder(d = head_d, h = head_h);
            cylinder(d = d, h = len);
        }
        translate([0, 0, -head_h]) phillips(head_d * 0.5, head_h * 0.5);
    }
}
// M5x10 pan head Phillips, as measured: head 9.9 x 4.0, real length 9.8
module m5_bolt(len = bolt_long) pan_head(5, len, m5_head_d - 0.6, m5_head_h - 0.3);
// M4x8 button head of the corner brackets (ISO 7380: head 7.6 x 2.2, 2.5 mm hex)
module m4_bolt(len = 8) {
    color(c_steel) difference() {
        union() {
            translate([0, 0, -2.2]) cylinder(d = 7.6, h = 2.2);
            cylinder(d = 4, h = len);
        }
        translate([0, 0, -2.21]) cylinder(d = 2.5 / cos(30), h = 1.4, $fn = 6);
    }
}
// M2.5x10 horn screw
module m2_5_screw(len = horn_screw_len) pan_head(2.5, len, 4.5, 1.7);
// the servo's own mounting screw
module servo_screw(len = 8) pan_head(2, len, 4, 1.5);

// ---- Drop-in nuts: bolt axis along Z, from Z=0 up by the thickness, long way along Y.
// Locked in a slot, the long way lies across the slot. A parallelogram seen from above.
module drop_in_nut(len, w, t) {
    skew = len / 2 - w / 2;
    color(c_nut) difference() {
        linear_extrude(t) polygon([[-w / 2, -len / 2], [w / 2, -len / 2 + skew], [w / 2, len / 2], [-w / 2, len / 2 - skew]]);
        translate([0, 0, -1]) cylinder(d = 4, h = t + 2);
    }
}
module m5_nut() drop_in_nut(tnut_len, tnut_n - 0.4, tnut_t - 0.4);   // 11.4 x 6.0 x 4.0
module m4_nut() drop_in_nut(11.4, 5.8, 4.1);

// ---- Corner bracket: cast, two legs, a sloped face with a window, centring lips.
// Axes: X=0 on the post face, Z=0 on the rail's bottom face; the rail leg runs along +X
// under the rail, the post leg down -Z along the post. Width along Y.
module corner_bracket() {
    t = bracket_t;
    w = corner_w;
    color(c_alu_cast) difference() {
        union() {
            box(0, bracket_leg, -w / 2, w / 2, -t, 0);
            box(0, t, -w / 2, w / 2, -bracket_leg, 0);
            // sloped face, from leg tip to leg tip
            rotate([90, 0, 0]) translate([0, 0, -w / 2]) linear_extrude(w) polygon([
                [bracket_leg, -t], [bracket_leg, 0], [0, -bracket_leg], [t, -bracket_leg],
                [t, -bracket_leg + t * sqrt(2) / 2], [bracket_leg - t * sqrt(2) / 2, -t]]);
            // centring lips, into the slots
            for (x = [1, bracket_leg - 4]) {
                box(x, x + 3, -corner_lip_w / 2, corner_lip_w / 2, -0.01, corner_lip_h);
                box(-corner_lip_h, 0.01, -corner_lip_w / 2, corner_lip_w / 2, -x - 3, -x);
            }
        }
        // bolt holes
        translate([corner_hole, 0, -t - 1]) cylinder(d = 4.5, h = t + corner_lip_h + 2);
        translate([-corner_lip_h - 1, 0, -corner_hole]) rotate([0, 90, 0]) cylinder(d = 4.5, h = t + corner_lip_h + 2);
        // window in the sloped face
        translate([bracket_leg / 2, 0, -bracket_leg / 2]) rotate([0, 45, 0])
            box(-corner_window / 2, corner_window / 2, -corner_window_w / 2, corner_window_w / 2, -10, 10);
    }
}
// with its bolts, heads inside the bracket, and its nuts in the slots
module corner_joint() {
    corner_bracket();
    translate([corner_hole, 0, -bracket_t]) m4_bolt();
    translate([corner_hole, 0, slot_lip]) m4_nut();
    translate([bracket_t, 0, -corner_hole]) rotate([0, -90, 0]) m4_bolt();
    translate([-slot_lip, 0, -corner_hole]) rotate([0, -90, 0]) m4_nut();
}

// ---- Parts on the printed parts, in their axes ----------------------------------
// jaw: clamped EVA pads, bolts, nuts in the post's slot. edge_clamp() axes
module edge_clamp_parts() {
    color(c_eva) {
        // side pad, 30 x 22, squeezed against the case wall
        box(jaw_t - pad_pocket, jaw_case_x, -15, 15, jaw_z0 + 2.15, lip_z0 - 2.15);
        // under-lip pad, 30 x 7, on the rim
        box(jaw_t + 1, jaw_case_x + lip_reach - 1, -15, 15, case_rim_h, lip_z0 + pad_pocket);
    }
    for (z = jaw_bolt_z) {
        translate([jaw_under_head, 0, z]) rotate([0, -90, 0]) m5_bolt();
        translate([-slot_lip, 0, z]) rotate([0, -90, 0]) m5_nut();
    }
}

// tensioner: collar, push bolt seated on it, nut in the pocket, rail bolt and nut.
// tensioner_block() axes
module tensioner_parts() {
    rail_bolt_x = (ten_neck_x0 + ten_neck_x1) / 2;
    color("#00AE42") translate([ten_head_x, 0, ten_z]) rotate([0, 90, 0]) tensioner_collar();
    translate([ten_head_x + ten_collar_t, 0, ten_z]) rotate([0, -90, 0]) m5_bolt();
    translate([ten_nut_x1 - (tnut_t - 0.4), 0, ten_z]) rotate([0, 90, 0]) m5_nut();
    translate([rail_bolt_x, 0, rail_z0 - rail_under_head]) m5_bolt();
    translate([rail_bolt_x, 0, rail_z0 + slot_lip]) m5_nut();
}

// servo module: bolts, nuts, servo screws, horn screw. Servo module axes
module servo_module_parts() {
    // carriage to rail
    translate([0, car_y1 - m5_head_h, rail_zc]) rotate([90, 0, 0]) m5_bolt();
    translate([0, car_y0 - slot_lip, rail_zc]) rotate([90, 0, 0]) m5_nut();
    // bracket to carriage, nut in the carriage's pocket against its skin
    translate([0, br_y1, nut_z]) rotate([90, 0, 0]) m5_bolt();
    translate([0, car_y1 - car_skin, nut_z]) rotate([90, 0, 0]) rotate(90) m5_nut();
    // servo screws through the ears into the servo plate
    for (s = [-1, 1]) translate([0, sp_y0 - sv_ear_t, sv_centre_z + s * sv_hole_pitch / 2]) rotate([-90, 0, 0]) servo_screw();
    // horn screw, head on the cam's front face
    translate([0, cam_back_y + cam_t, z_shaft]) rotate([90, 0, 0]) m2_5_screw();
}

// cable clip's bolt and nut in the rail's top slot, cable_clip() axes
module cable_clip_parts() {
    translate([clip_bolt_x, 0, rail_under_head]) rotate([180, 0, 0]) m5_bolt();
    translate([clip_bolt_x, 0, -slot_lip]) rotate([180, 0, 0]) m5_nut();
}

// EVA dot in the plunger tip, servo_plunger() axes
module plunger_dot() color(c_eva) box(-2.25, 2.25, -2.25, 2.25, 0, pad_t);
