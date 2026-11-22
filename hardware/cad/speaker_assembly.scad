// The speaker holder on the desk microphone: the ER-151 in its cradle, clamped to the
// gooseneck tube under the mic head. Not printed: a picture and a check of the mic
// distance. Separate from frame_assembly.scad: the mic stands on its own.
// Axes as in lib.scad's speaker section: mic head tip at the origin, tube along -Z,
// the speaker's long axis along X, its mesh face at Z = mic_dist facing the mic.
include <params.scad>
include <lib.scad>
include <hardware.scad>

c_structure = "#181818";    // Black: cradle and clamp cap
c_rubber = "#3C3C3C";       // speaker rubber ends
c_mesh = "#6E6E6E";         // speaker mesh section
c_mic = "#A0A0A0";          // mic head and tube
tube_shown = 110;           // tube length drawn below the head

// ER-151: rounded triangle, rubber ends 61 mm across a face, mesh section 1.9 mm smaller
// all round. Face (towards the mic) on Z = spk_face_z.
module er151() {
    translate([spk_x() - spk_len / 2, 0, spk_face_z]) rotate([90, 0, 90]) {
        for (x = [0, spk_len - spk_end_len]) color(c_rubber) translate([0, 0, x]) linear_extrude(spk_end_len) spk_tri(0);
        color(c_mesh) translate([0, 0, spk_end_len - 0.01]) linear_extrude(spk_len - 2 * spk_end_len + 0.02) offset(delta = -spk_face_inset) spk_tri(0);
    }
}

module mic() {
    color(c_mic) {
        // head, tip at the origin
        translate([0, 0, -mic_head_len]) cylinder(d = mic_head_d, h = mic_head_len - 4);
        translate([0, 0, -4]) cylinder(d1 = mic_head_d, d2 = mic_head_d - 6, h = 4);
        // gooseneck tube
        translate([0, 0, -mic_head_len - tube_shown]) cylinder(d = tube_d, h = tube_shown);
    }
}

// EVA lining in the clamp bore, two halves
module clamp_lining() {
    color(c_eva) translate([0, 0, clamp_z0]) linear_extrude(clamp_h) difference() {
        circle(d = clamp_bore);
        circle(d = tube_d);
        square([clamp_bore + 2, clamp_gap], center = true);
    }
}

// clamp bolts into the nuts in the cradle's pockets
module clamp_parts() {
    for (s = [-1, 1]) translate([s * clamp_bolt_x, 0, (clamp_z0 + clamp_z1) / 2]) {
        translate([0, clamp_gap / 2 + clamp_cap_t, 0]) rotate([90, 0, 0]) m5_bolt();
        translate([0, -clamp_nut_skin - clamp_gap / 2, 0]) rotate([90, 0, 0]) rotate(90) m5_nut();
    }
}

mic();
er151();
color(c_structure) speaker_cradle();
color(c_structure) speaker_clamp_cap();
clamp_lining();
clamp_parts();

echo(mic_to_mesh = mic_dist, mic_to_rubber_face = spk_face_z);
