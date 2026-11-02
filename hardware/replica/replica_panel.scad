// Flat replica of the desk's top: same outer size and rim, so the frame clamps on
// exactly as on the real case. Fixed bosses at every button, plunger holes for the
// spring-loaded test buttons at SC1, SC2, SC3 and SPREKEN, hinge lugs for a working
// flip cover at the two covered buttons. Print 1, open side down.
include <../cad/params.scad>
include <../cad/lib.scad>

module replica_panel() {
    leaf_tunnel_w = tb_leaf_b + 0.4;
    difference() {
        union() {
            difference() {
                translate([0, 0, -rp_h]) cube([case_w, case_d, rp_h + case_rim_h]);
                // open underside
                box(rp_wall, case_w - rp_wall, rp_wall, case_d - rp_wall, -rp_h - 1, -rp_t);
                // panel recess inside the rim
                box(case_rim_w, case_w - case_rim_w, case_rim_w, case_d - case_rim_w, 0, case_rim_h + 1);
            }
            // ribs along Y between columns
            for (c = [0 : 7]) translate([btn_x(c) - pitch_x / 2 - rp_rib / 2, rp_wall - 0.1, -rp_h])
                cube([rp_rib, case_d - 2 * rp_wall + 0.2, rp_h - rp_t + 0.1]);
            // leaf spring pillars
            for (t = tb_sockets) {
                p = btn_xy(t[0]);
                y_mouth = p[1] + t[1] * tb_leaf_l;
                y_far = y_mouth + t[1] * (tb_root_l + 3);
                box(p[0] - pitch_x / 2, p[0] + pitch_x / 2, min(y_mouth, y_far), max(y_mouth, y_far), -rp_h, -rp_t + 0.1);
            }
            // bosses
            for (b = buttons) {
                socket = len([for (t = tb_sockets) if (t[0] == b[0]) t]) > 0;
                covered = len([for (c = covered_buttons) if (c == b[0]) c]) > 0;
                size = covered ? cover_w - 7 : btn_size; // clears the dummy cover as it swings
                p = btn_xy(b[0]);
                if (!socket) translate([p[0] - size / 2, p[1] - size / 2, -0.1])
                    cube([size, size, btn_proud + 0.1]);
            }
            // hinge lugs on the covered buttons
            for (c = covered_buttons, s = [-1, 1]) {
                p = btn_xy(c);
                translate([p[0] + s * (cover_w / 2 + 1.8) - 1.5, p[1] + cover_d / 2 - 3, -0.1])
                    cube([3, 6, cover_pin_z + 0.1 + 3]);
            }
        }
        // leaf tunnels, open towards the stem
        for (t = tb_sockets) {
            p = btn_xy(t[0]);
            y_mouth = p[1] + t[1] * tb_leaf_l;
            y_far = y_mouth + t[1] * tb_root_l;
            z1 = tb_leaf_z + tb_preload;
            box(p[0] - leaf_tunnel_w / 2, p[0] + leaf_tunnel_w / 2, min(y_mouth, y_far) - (t[1] < 0 ? 0 : 1), max(y_mouth, y_far) + (t[1] < 0 ? 1 : 0),
                z1 - tb_root_h - 0.2, z1 + 0.2);
        }
        // plunger holes
        for (t = tb_sockets) {
            p = btn_xy(t[0]);
            box(p[0] - tb_stem / 2 - 0.2, p[0] + tb_stem / 2 + 0.2, p[1] - tb_stem / 2 - 0.2, p[1] + tb_stem / 2 + 0.2, -rp_t - 1, 1);
        }
        // hinge pin holes: 1.75 mm filament
        for (c = covered_buttons) {
            p = btn_xy(c);
            translate([p[0] - cover_w, p[1] + cover_d / 2, cover_pin_z]) rotate([0, 90, 0]) cylinder(d = 1.95, h = 2 * cover_w);
        }
    }
}

replica_panel();
