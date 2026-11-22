// Assembly step pictures for README.md. Not printed. Drawn the right way up, as on the
// desk, without the desk. Bolts and nuts are simplified. Render one view with
//   openscad -D 'view="corner"' -o img/assembly-corner.png --camera=... assembly_steps.scad
// or all of them with render_assembly_steps.sh.
include <params.scad>
include <lib.scad>
include <hardware.scad>

view = "frame";   // frame, corner, cap, jaw, tensioner, done

c_alu = "Silver";
c_black = "#202020";
c_pad = c_eva;          // EVA foam
c_collar = "#00AE42";

// ---- hardware, from hardware.scad ---------------------------------------------
module m5(len = bolt_long) m5_bolt(len);
module m4() m4_bolt();
module nut() m5_nut();

// ---- frame parts ----------------------------------------------------------------
module rail() color(c_alu) translate([rail_x0, rail_y, rail_zc]) rotate([0, 90, 0]) ext2020(rail_len);
module post(x, drop = 0) color(c_alu) translate([x, rail_y, post_z0 - drop]) ext2020(post_len);

// corner bracket on the post face at x = face, reaching away from the post in direction s
module bracket(face, s, e = 0) {
    translate([face + s * e, rail_y, rail_z0 - e]) mirror([s < 0 ? 1 : 0, 0, 0]) corner_bracket();
    // bolts and nuts: into the rail from below, into the post from the side. Exploded,
    // the nut sits in the gap between the profile and the bracket.
    bx = face + s * (corner_hole + e);
    translate([bx, rail_y, rail_z0 - bracket_t - e - (e > 0 ? 3 : 0)]) m4();
    translate([bx, rail_y, e > 0 ? rail_z0 - e / 2 - 2 : rail_z0 + slot_lip]) m4_nut();
    bz = rail_z0 - corner_hole - e;
    translate([face + s * (bracket_t + e + (e > 0 ? 3 : 0)), rail_y, bz]) rotate([0, s > 0 ? -90 : 90, 0]) m4();
    translate([e > 0 ? face + s * (e / 2 + 2) : face - s * slot_lip, rail_y, bz]) rotate([0, s > 0 ? -90 : 90, 0]) m4_nut();
}

module corner(x, e = 0) {
    for (s = [-1, 1]) bracket(x + s * ext / 2, s, e);
}

module end_caps(e = 0) {
    // the cap's plate is at its Z=0..2 and its tongues point +Z: into the profile end
    plate = 2;
    color(c_black) {
        translate([rail_x0 - plate - e, rail_y, rail_zc]) rotate([0, 90, 0]) end_cap();
        translate([rail_x0 + rail_len + plate + e, rail_y, rail_zc]) rotate([0, -90, 0]) end_cap();
        for (x = [post_x_l, post_x_r]) translate([x, rail_y, post_z0 - plate - e]) end_cap();
    }
}

// jaw on the left post, e explodes it towards the desk (+X)
module jaw_left(e = 0) {
    x0 = post_x_l + ext / 2;
    translate([x0, rail_y, 0]) {
        color(c_black) translate([e, 0, 0]) edge_clamp();
        for (z = jaw_bolt_z) {
            translate([jaw_under_head + 2.2 * e, 0, z]) rotate([0, -90, 0]) m5();
            translate([e > 0 ? 0.6 * e : -slot_lip - tnut_recess, 0, z]) rotate([0, -90, 0]) nut();
        }
        // pads
        color(c_pad) {
            translate([jaw_t - pad_pocket + 3 * e, -15, jaw_z0 + 2.5]) cube([pad_t, 30, 21]);
            translate([jaw_t + 1.5, -15, lip_z0 - pad_pocket - 3 + 0.01 - (e > 0 ? 12 : 0)]) cube([6, 30, pad_t]);
        }
    }
}
module jaw_right() translate([post_x_r - ext / 2, rail_y, 0]) rotate(180) {
    color(c_black) edge_clamp();
    color(c_pad) {
        translate([jaw_t - pad_pocket, -15, jaw_z0 + 2.5]) cube([pad_t, 30, 21]);
        translate([jaw_t + 1.5, -15, lip_z0 - pad_pocket - 3 + 0.01]) cube([6, 30, pad_t]);
    }
}

// tensioner outside the left post, e explodes it: the block drops and moves out, the pad
// stays at the post, the push bolt comes out of the back, the nut out of its side pocket
module tensioner_left(e = 0) {
    rail_bolt_x = (ten_neck_x0 + ten_neck_x1) / 2;
    translate([post_x_l - ext / 2, rail_y, 0]) rotate(180) {
        translate([e, 0, -e]) {
            color(c_black) tensioner_block();
            translate([e > 0 ? ten_neck_x1 + 0.6 * e : ten_head_x, 0, ten_z]) {   // exploded: out past the block's end, so it shows
                color(c_collar) rotate([0, 90, 0]) tensioner_collar();
                translate([ten_collar_t + e, 0, 0]) rotate([0, -90, 0]) m5();
            }
            translate([ten_nut_x0 + 0.2, (e > 0 ? 2 * e : 0), ten_z]) rotate([0, 90, 0]) nut();
            translate([rail_bolt_x, 0, rail_z0 - rail_under_head - 1.5 * e]) m5();
        }
        color(c_black) translate([0, 0, ten_z - e]) tensioner_pad();
        translate([rail_bolt_x + e, 0, e > 0 ? rail_z0 - e / 2 - 2 : rail_z0 + slot_lip + tnut_recess]) nut();
    }
}
module tensioner_right() translate([post_x_r + ext / 2, rail_y, 0]) {
    color(c_black) tensioner_block();
    color(c_black) translate([0, 0, ten_z]) tensioner_pad();
    color(c_collar) translate([ten_head_x, 0, ten_z]) rotate([0, 90, 0]) tensioner_collar();
}

// ---- views ----------------------------------------------------------------------
if (view == "frame") {           // step 2, whole frame
    rail();
    for (x = [post_x_l, post_x_r]) { post(x); corner(x); }
} else if (view == "corner") {   // step 2, left post top, exploded
    rail();
    post(post_x_l, 12);
    corner(post_x_l, 10);
} else if (view == "cap") {      // step 3, end caps pulled off
    rail();
    for (x = [post_x_l, post_x_r]) { post(x); corner(x); }
    end_caps(15);
} else if (view == "jaw") {      // step 4, left jaw exploded towards the desk
    rail();
    post(post_x_l);
    corner(post_x_l);
    end_caps();
    jaw_left(14);
} else if (view == "tensioner") { // step 5, left tensioner exploded
    rail();
    post(post_x_l);
    corner(post_x_l);
    end_caps();
    jaw_left();
    tensioner_left(12);
} else if (view == "done") {     // frame complete, ready for the squeeze
    rail();
    for (x = [post_x_l, post_x_r]) { post(x); corner(x); }
    end_caps();
    jaw_left();
    jaw_right();
    tensioner_left();
    tensioner_right();
}
