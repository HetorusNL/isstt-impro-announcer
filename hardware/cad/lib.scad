// Shared geometry. Include after params.scad. Part geometry lives here so the
// part files and frame_assembly.scad draw exactly the same shape.

module box(x0, x1, y0, y1, z0, z1) {
    translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}

// 2020 profile along +Z, centred on the axis
module ext2020(len) {
    linear_extrude(len) difference() {
        square(ext, center = true);
        circle(d = ext_bore);
        for (a = [0 : 90 : 270]) rotate(a) {
            translate([ext / 2 - slot_lip - 0.05, -slot_w / 2]) square([slot_lip + 0.1, slot_w]);
            translate([ext / 2 - slot_depth, -slot_cavity_w / 2]) square([slot_depth - slot_lip, slot_cavity_w]);
        }
    }
}

// MG90S envelope, module axes: shaft along +Y, body length along +Z, shaft axis
// through the origin, servo base at Y=0.
module mg90s() {
    multmatrix([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) {
        translate([-sv_shaft_off, -sv_w / 2, 0]) cube([sv_l, sv_w, sv_h]);
        translate([sv_l / 2 - sv_shaft_off - sv_ear_span / 2, -sv_w / 2, sv_ear_z]) cube([sv_ear_span, sv_w, sv_ear_t]);
        cylinder(d = 4.8, h = sv_h + sv_shaft_proud);
    }
}

// ---- Servo module, local axes: X across, Y outward from the rail centre, Z as desk

module servo_carriage() {
    difference() {
        union() {
            box(-car_w / 2, car_w / 2, car_y0, car_y1, rail_z0, car_z1);
            box(-car_w / 2, car_w / 2, car_y0 - key_d, car_y0, rail_zc - key_w / 2, rail_zc + key_w / 2);
        }
        // rail bolt, head recessed so the bracket passes over it
        translate([0, 0, rail_zc]) rotate([-90, 0, 0]) {
            cylinder(d = m5_clear, h = car_y1 + 1);
            translate([0, 0, car_y1 - m5_head_h]) cylinder(d = m5_head_d, h = m5_head_h + 1);
        }
        // height bolt: T-nut pocket from the back, above the rail
        translate([0, 0, nut_z]) rotate([-90, 0, 0]) cylinder(d = m5_clear, h = car_y1 + 1);
        box(-tnut_w / 2, tnut_w / 2, car_y0 - 1, car_y0 + tnut_t, nut_z - tnut_w / 2, nut_z + tnut_w / 2);
    }
}

module servo_bracket() {
    y_back = sp_y0 - br_back_rib;
    y_nose = mod_d + sleeve_half;
    difference() {
        union() {
            // servo plate
            box(-br_w / 2, br_w / 2, sp_y0, sp_y1, sleeve_z0, shelf_z1);
            // shelf
            box(-br_w / 2, br_w / 2, sp_y0, br_y1, shelf_z0, shelf_z1);
            // slotted plate
            box(-br_w / 2, br_w / 2, car_y1, br_y1, shelf_z0, br_top);
            // nose with the plunger guide
            box(-br_w / 2, br_w / 2, sp_y0, y_nose, sleeve_z0, sleeve_z1);
            // side walls, deep behind the plate: these are the ribs carrying the press load up
            for (s = [-1, 1]) translate([s > 0 ? br_in : -br_w / 2, 0, 0])
                rotate([90, 0, 90]) linear_extrude(br_wall) {
                    polygon([
                        [y_back, sleeve_z0], [y_nose, sleeve_z0], [y_nose, sleeve_z1],
                        [sp_y1 + 2, sleeve_z1 + 4], [sp_y1 + 2, shelf_z1], [y_back, shelf_z1]
                    ]);
                    translate([car_y0 + 0.3, shelf_z0]) square([br_y1 - car_y0 - 0.3, br_top - shelf_z0]);
                }
        }
        // servo body window, servo goes in from the back with its ears on the back face
        box(-sv_w / 2 - 0.25, sv_w / 2 + 0.25, sp_y0 - 1, sp_y1 + 1,
            z_shaft - sv_shaft_off - 0.25, z_shaft - sv_shaft_off + sv_l + 0.25);
        // servo screw pilots
        for (s = [-1, 1]) translate([0, sp_y0 - 1, sv_centre_z + s * sv_hole_pitch / 2])
            rotate([-90, 0, 0]) cylinder(d = sv_screw_pilot, h = sp_t + 2);
        // plunger guide bore
        translate([0, mod_d, 0]) box(-(pl_w + pl_clear) / 2, (pl_w + pl_clear) / 2,
            -(pl_w + pl_clear) / 2, (pl_w + pl_clear) / 2, sleeve_z0 - 1, sleeve_z1 + 1);
        // adjust slot; also gives a hex key access to the rail bolt behind it
        hull() for (z = [rail_zc - adj, nut_z + adj]) translate([0, car_y1 - 1, z])
            rotate([-90, 0, 0]) cylinder(d = m5_clear, h = br_t + 2);
    }
}

// Eccentric angle from straight down where the plunger has pushed the cap to the
// end of its travel (cam contact radius = cam_r + arm_len * cos(angle)).
cam_press_angle = acos((pl_len + btn_proud - btn_travel < z_shaft ? z_shaft - pl_len - btn_proud + btn_travel - cam_r : 0) / arm_len);

// Cam axes: shaft along +Z, back face at Z=0, eccentric towards +X
module servo_cam() {
    difference() {
        translate([arm_len, 0, 0]) cylinder(r = cam_r, h = cam_t);
        translate([0, 0, -1]) cylinder(d = horn_hub_d + 0.3, h = horn_hub_h + 1);
        translate([0, -(horn_stub_w + 0.3) / 2, -1]) cube([horn_stub + 0.3, horn_stub_w + 0.3, horn_t + 1]);
        translate([0, 0, -1]) cylinder(d = 2.6, h = cam_t + 2);
        translate([0, 0, horn_hub_h + 1.2]) cylinder(d = 5, h = cam_t);
        // marks the eccentric direction on the front face
        translate([arm_len + cam_r - 1.5, -0.6, cam_t - 0.6]) cube([1.6, 1.2, 1]);
    }
}

// Plunger axes: tip of the EVA dot at Z=0, top at Z=pl_len, centred on the axis
module servo_plunger() {
    difference() {
        union() {
            box(-pl_w / 2, pl_w / 2, -pl_w / 2, pl_w / 2, pl_dot_proud, pl_len);
            box(-pl_collar / 2, pl_collar / 2, -pl_collar / 2, pl_collar / 2, pl_len - pl_collar_t, pl_len);
        }
        // recess for an EVA dot, so the tip leaves no marks on the cap
        box(-2.25, 2.25, -2.25, 2.25, pl_dot_proud - 1, pad_t);
    }
}

// ---- Clamp, local axes: X=0 at the post's inner face, +X towards the case,
// Y centred on the post, Z as desk

module edge_clamp() {
    difference() {
        union() {
            box(0, jaw_t, -jaw_w / 2, jaw_w / 2, jaw_z0, jaw_z1);
            // lip over the rim
            box(0, jaw_case_x + lip_reach, -jaw_w / 2, jaw_w / 2, lip_z0, jaw_z1);
            // slot key along the post
            box(-key_d, 0, -key_w / 2, key_w / 2, jaw_z0, jaw_z1);
        }
        // side pad
        box(jaw_t - pad_pocket, jaw_t + 1, -jaw_w / 2 + 2, jaw_w / 2 - 2, jaw_z0 + 2, lip_z0 - 2);
        // pad under the lip
        box(jaw_t + 1, jaw_case_x + lip_reach - 1, -jaw_w / 2 + 2, jaw_w / 2 - 2, lip_z0 - 1, lip_z0 + pad_pocket);
        // M5 into T-nuts in the post's slot, heads below the pad
        for (z = jaw_bolt_z) translate([-key_d - 1, 0, z]) rotate([0, 90, 0]) {
            cylinder(d = m5_clear, h = jaw_t + key_d + 2);
            translate([0, 0, key_d + 1 + jaw_under_head]) cylinder(d = m5_head_d, h = jaw_t);
        }
    }
}
jaw_bolt_z = [jaw_z0 + 8, lip_z0 - 8];

// ---- Tensioner, local axes: X=0 at the post's outer face, +X outward along the
// rail, Y centred on the rail, Z as desk. The block bolts to the rail's bottom slot
// outside the outer corner bracket, and its arm passes under that bracket. The push
// bolt's head sits behind the shoulder, its thread in a captive T-nut, and its tip
// pushes the pad's stub. The pad bridges the slot in the post. It only pushes.

module tensioner_block() {
    socket = ten_stub + 0.4;
    head_half = m5_head_d / 2 + 0.1;
    rail_bolt_x = (ten_neck_x0 + ten_neck_x1) / 2;
    difference() {
        union() {
            box(ten_x0, ten_neck_x1, -ten_w / 2, ten_w / 2, ten_arm_z0, ten_arm_z1);
            box(ten_neck_x0, ten_neck_x1, -ten_w / 2, ten_w / 2, ten_arm_z1 - 0.01, rail_z0);
            // slot key along the rail
            box(ten_neck_x0, ten_neck_x1, -key_w / 2, key_w / 2, rail_z0, rail_z0 + key_d);
        }
        // pad stub socket
        box(ten_x0 - 1, ten_nut_x0 + 0.01, -socket / 2, socket / 2, ten_z - socket / 2, ten_z + socket / 2);
        // captive T-nut, slides in from the +Y side
        box(ten_nut_x0, ten_nut_x1, -tnut_w / 2, ten_w / 2 + 1, ten_z - tnut_w / 2, ten_z + tnut_w / 2);
        // push bolt through the shoulder
        translate([ten_nut_x1 - 0.01, 0, ten_z]) rotate([0, 90, 0]) cylinder(d = m5_clear, h = ten_shoulder + 0.02);
        // head slot: open outward for the hex key, open below for the rail bolt
        box(ten_head_x, ten_neck_x1 + 1, -head_half, head_half, ten_arm_z0 - 1, ten_z + head_half);
        // rail bolt, reached from below through the head slot
        translate([rail_bolt_x, 0, ten_z]) {
            cylinder(d = m5_clear, h = rail_z0 + key_d + 1 - ten_z);
            cylinder(d = m5_head_d, h = rail_z0 - (car_t - m5_head_h) - ten_z);
        }
    }
}

// Pad axes: plate on the post's face at X=0, stub towards +X
module tensioner_pad() {
    box(0, ten_plate_t, -ten_plate_w / 2, ten_plate_w / 2, -ten_plate_h / 2, ten_plate_h / 2);
    box(ten_plate_t - 0.01, ten_nut_x0, -ten_stub / 2, ten_stub / 2, -ten_stub / 2, ten_stub / 2);
}

module end_cap() {
    plate = 2;
    finger = 5;
    box(-ext / 2, ext / 2, -ext / 2, ext / 2, 0, plate);
    // one tongue per slot, press fit in the slot opening
    for (a = [0 : 90 : 270]) rotate(a)
        box(ext / 2 - slot_depth + 0.2, ext / 2 - 0.2, -(slot_w - 0.25) / 2, (slot_w - 0.25) / 2, plate, plate + finger);
}

// ---- Speaker holder, local axes: mic head tip at the origin, tube along -Z,
// prism long axis along X, driver face at Z=mic_dist facing the mic.

function spk_x() = -mic_offset;
clamp_z1 = -mic_head_len - clamp_gap_below_head;
clamp_z0 = clamp_z1 - clamp_h;
clamp_bore = tube_d + 2 * tube_lining;
clamp_wall = 4;
clamp_bolt_x = clamp_bore / 2 + 1 + tnut_w / 2 + 1;
clamp_flange_x = clamp_bolt_x + tnut_w / 2 + 1.5;
clamp_cap_t = 4;
clamp_gap = 1;
clamp_nut_skin = 1.5;
spk_beam_y1 = -spk_base / 2 - spk_clear - cup_wall + 0.5;
spk_beam_y0 = spk_beam_y1 - 4;
spk_arm_y0 = spk_beam_y1 - 8;
assert(bolt_long - clamp_cap_t - clamp_gap - clamp_nut_skin >= m5_min_thread, "speaker clamp bolt thread engagement too short");

module spk_tri(c) {
    offset(delta = c) polygon([[-spk_base / 2, 0], [spk_base / 2, 0], [0, spk_h]]);
}

// One end of the cradle; the prism slides in from +Y and straps down.
module spk_cup(s) {
    x_face = s * spk_len / 2;
    translate([spk_x() + x_face + (s > 0 ? -cup_lip : -spk_clear), 0, mic_dist])
        rotate([90, 0, 90]) linear_extrude(cup_lip + spk_clear) difference() {
            offset(r = cup_wall) spk_tri(spk_clear);
            hull() {
                spk_tri(spk_clear);
                translate([200, 0]) spk_tri(spk_clear);
            }
        }
    // end wall with a window, so the ports and buttons stay reachable
    translate([spk_x() + x_face + (s > 0 ? spk_clear : -spk_clear - cup_wall), 0, mic_dist])
        rotate([90, 0, 90]) linear_extrude(cup_wall) difference() {
            offset(r = cup_wall) spk_tri(spk_clear);
            offset(delta = -5) spk_tri(spk_clear);
        }
}

module speaker_cradle() {
    beam_z0 = mic_dist - spk_clear - cup_wall;
    beam_z1 = mic_dist + 18;
    strap_x = (spk_driver_pitch / 2 + spk_driver_d / 2 + spk_len / 2 - cup_lip) / 2;
    difference() {
        union() {
            spk_cup(1);
            spk_cup(-1);
            // beam along the driver face, outside it
            box(spk_x() - spk_len / 2 - spk_clear - cup_wall, spk_x() + spk_len / 2 + spk_clear + cup_wall,
                spk_beam_y0, spk_beam_y1, beam_z0, beam_z1);
            // arm from the clamp up to the beam
            box(-8, 8, spk_arm_y0, spk_beam_y1, clamp_z0, beam_z1);
            box(-8, 8, spk_arm_y0, -clamp_bore / 2, clamp_z0, clamp_z1);
            // clamp, fixed half
            translate([0, 0, clamp_z0]) linear_extrude(clamp_h) difference() {
                intersection() {
                    circle(d = clamp_bore + 2 * clamp_wall);
                    translate([-clamp_flange_x, -clamp_bore]) square([2 * clamp_flange_x, clamp_bore - clamp_gap / 2]);
                }
            }
            box(-clamp_flange_x, clamp_flange_x, -tnut_t - clamp_nut_skin - clamp_gap / 2, -clamp_gap / 2, clamp_z0, clamp_z1);
        }
        translate([0, 0, clamp_z0 - 1]) cylinder(d = clamp_bore, h = clamp_h + 2);
        for (s = [-1, 1]) translate([s * clamp_bolt_x, 0, (clamp_z0 + clamp_z1) / 2]) {
            rotate([90, 0, 0]) cylinder(d = m5_clear, h = 40);
            box(-tnut_w / 2, tnut_w / 2, -tnut_t - clamp_nut_skin - clamp_gap / 2 - 1, -clamp_nut_skin - clamp_gap / 2, -tnut_w / 2, tnut_w / 2);
        }
        // strap slots, outside the driver area
        for (s = [-1, 1]) translate([spk_x() + s * strap_x, 0, 0])
            box(-1.5, 1.5, spk_beam_y0 - 1, spk_beam_y1 + 1, beam_z0 + 1.5, beam_z1 - 1.5);
    }
}

module speaker_clamp_cap() {
    difference() {
        union() {
            translate([0, 0, clamp_z0]) linear_extrude(clamp_h) intersection() {
                circle(d = clamp_bore + 2 * clamp_wall);
                translate([-clamp_flange_x, clamp_gap / 2]) square([2 * clamp_flange_x, clamp_bore]);
            }
            box(-clamp_flange_x, clamp_flange_x, clamp_gap / 2, clamp_gap / 2 + clamp_cap_t, clamp_z0, clamp_z1);
        }
        translate([0, 0, clamp_z0 - 1]) cylinder(d = clamp_bore, h = clamp_h + 2);
        for (s = [-1, 1]) translate([s * clamp_bolt_x, -1, (clamp_z0 + clamp_z1) / 2])
            rotate([-90, 0, 0]) cylinder(d = m5_clear, h = 40);
    }
}

// Bounding boxes used by the safety asserts: [[xmin, ymin, zmin], [xmax, ymax, zmax]]
function module_box(name) = let (
    p = btn_xy(name),
    s = sign(p[1] - rail_y),
    half = max(br_w / 2, cam_r + arm_len),
    y_in = sv_base_y,
    y_out = mod_d + max(sleeve_half, cam_t / 2),
    ya = rail_y + s * y_in,
    yb = rail_y + s * y_out
) [[p[0] - half, min(ya, yb), btn_proud - btn_travel],
   [p[0] + half, max(ya, yb), br_top]];

function rail_box() = [[rail_x0, rail_y - ext / 2, rail_z0], [rail_x0 + rail_len, rail_y + ext / 2, rail_z1]];
function post_box(x) = let (
    s = x < case_w / 2 ? 1 : -1,   // +1 for the left post: the desk side is +X
    in_ = max(ext / 2 + bracket_leg, ext / 2 + jaw_case_x + lip_reach),
    out = ext / 2 + bracket_leg
) [[min(x - s * out, x + s * in_), rail_y - jaw_w / 2, post_z0],
   [max(x - s * out, x + s * in_), rail_y + jaw_w / 2, rail_z0]];
function tensioner_box(x) = let (
    s = x < case_w / 2 ? -1 : 1,   // outward
    a = x + s * ext / 2,
    b = a + s * ten_neck_x1
) [[min(a, b), rail_y - ten_w / 2, ten_arm_z0], [max(a, b), rail_y + ten_w / 2, rail_z0]];

function overlap(a, b) =
    a[0][0] < b[1][0] && b[0][0] < a[1][0] &&
    a[0][1] < b[1][1] && b[0][1] < a[1][1] &&
    a[0][2] < b[1][2] && b[0][2] < a[1][2];
