// ISSTT IMPRO announcer servo rig: the one parameter file.
//
// Every part file includes this file. Units: mm, N, degrees.
//
// MEASURED = taken on the real desk, with the date. Photos: docs/reference/impro-desk.jpg
// and impro-desk-mic.jpg. ESTIMATE = not measured yet: scaled from a photo or
// taken from web listings. Each ESTIMATE says what to measure. Change the
// number, re-render, reprint; nothing else needs editing. The asserts at the
// bottom of this file and in frame_assembly.scad fail the render if a change
// breaks the design.
//
// Desk coordinates:
//   X left to right,   X=0 at the case's left outer side face
//   Y front to back,   Y=0 at the case's front outer face (operator side)
//   Z up,              Z=0 at the top surface of the aluminium button panel

$fn = 64;

// ---- Desk case --------------------------------------------------------------
case_w = 280;           // MEASURED 2026-11-12: case outer width, left to right
case_d = 230;           // MEASURED 2026-11-12: case outer depth, front to back
case_h = 66;            // MEASURED 2026-11-12: table to the top of the rim at the front. The top slopes: 78.5 at the back
case_rim_w = 15;        // MEASURED 2026-11-12: width of the rim seen from above, all four sides
case_rim_h = 1;         // MEASURED 2026-11-12: rim top above the panel surface

// ---- Buttons ----------------------------------------------------------------
btn_w = 24;             // MEASURED 2026-11-12: button width (X)
btn_d = 18;             // MEASURED 2026-11-12: button depth (Y)
btn_gap = 6.5;          // MEASURED 2026-11-12: space between buttons, taken as equal in X and Y
pitch_x = btn_w + btn_gap;
pitch_y = btn_d + btn_gap;
btn_proud = 10;         // MEASURED 2026-11-12: unpressed cap top above the panel
btn_travel = 3;         // MEASURED 2026-11-12: cap travel
btn_force = 3;          // ESTIMATE [N] measure: SPREKEN press force (cup + water/coins, then weigh)
btn_x0 = 37 + btn_w / 2; // MEASURED 2026-11-12: 37 from the case left face to the ALGEMEEN button
btn_y_row3 = 37 + btn_d / 2; // MEASURED 2026-11-12: 37 from the case front face to the SPREKEN button

function btn_x(col) = btn_x0 + col * pitch_x;
function btn_y(row) = btn_y_row3 + (3 - row) * pitch_y;

// Layout read from the photo: name, column, row. Row 0 is the row with the two
// covered buttons, row -1 the BEZET indicator above it.
buttons = [
    ["BEZET", 3, -1],
    ["KOPPEL", 0, 0], ["ONTRUIMING", 2, 0], ["15MIN", 3, 0],
    ["OMROEP3", 4, 0], ["OMROEP4", 5, 0], ["MUZIEK_AAN", 6, 0],
    ["SC1", 0, 1], ["SC2", 1, 1], ["SC3", 2, 1], ["SC4", 3, 1],
    ["SC5", 4, 1], ["SC6", 5, 1], ["MUZIEK_HARDER", 6, 1],
    ["ALGEMEEN", 0, 2], ["ZWEMBAD", 1, 2], ["KANTINE", 2, 2], ["TERRAS", 3, 2],
    ["FITNESS", 4, 2], ["DOJO", 5, 2], ["MUZIEK_ZACHTER", 6, 2],
    ["SPREKEN", 6, 3]
];
function btn_rec(name) = [for (b = buttons) if (b[0] == name) b][0];
function btn_xy(name) = let (b = btn_rec(name)) [btn_x(b[1]), btn_y(b[2])];

// Buttons that get a servo module. Matches [actuators] in config.example.toml.
actuated = ["SC1", "SC2", "SC3", "SPREKEN"];

// ---- Covered buttons and their keep-out volume (safety, spec section 4) ------
// Ontruimingsalarm (evacuation alarm) and Koppel ruimtes. No frame part may enter.
covered_buttons = ["KOPPEL", "ONTRUIMING"];
// The keep-outs follow these two positions, not the grid. Measure them directly.
alarm_xy = btn_xy("ONTRUIMING"); // MEASURED 2026-11-12: on the button grid
koppel_xy = btn_xy("KOPPEL");    // MEASURED 2026-11-12: on the button grid
function panel_xy(name) = name == "ONTRUIMING" ? alarm_xy : name == "KOPPEL" ? koppel_xy : btn_xy(name);
cover_w = btn_w;        // MEASURED 2026-11-12: flip cover is as wide as the button
cover_d = 23;           // MEASURED 2026-11-12: flip cover depth (Y), 5 more than the button, all of it at the back
cover_off_y = (cover_d - btn_d) / 2; // cover centre behind the button centre: front edges are flush
cover_h = 13.5;         // MEASURED 2026-11-12: closed cover top above the panel, hinge at the back
cover_pin_z = 4;        // ESTIMATE measure: hinge pin height above the panel (dummy cover on the replica)
cover_swing_r = sqrt(cover_d * cover_d + cover_h * cover_h); // cover pivots on its back edge
keepout_side = 10;      // finger room left and right of the cover
lip_clearance_min = 4;  // minimum clearance, any part to the cover lip. Not finger room: the hand comes from above
keepout_back = 5;       // margin behind the swung-open cover
keepout_h = 120;        // hand room above the panel; no part may span over the cover below this

// [[xmin, ymin, zmin], [xmax, ymax, zmax]] of the keep-out around one covered button
function keepout_box(name) = let (p = panel_xy(name)) [
    [p[0] - cover_w / 2 - keepout_side, p[1] + cover_off_y - cover_d / 2 - lip_clearance_min, 0],
    [p[0] + cover_w / 2 + keepout_side, p[1] + cover_off_y + cover_d / 2 + cover_swing_r + keepout_back, keepout_h]
];

// ---- Rubber/EVA pads --------------------------------------------------------
pad_t = 3;              // MEASURED 2026-11-17: EVA sheet thickness. No adhesive backing: pads are a push fit
pad_pocket = 1.5;       // pad recess depth; the pad stands proud by the rest
pad_squeeze = 0.8;      // compression per side when clamped: one full turn of the M5 push bolt. The one squeeze number; sets the stop collar
pad_stress = 0.05;      // ESTIMATE [N/mm2] EVA stress at about 25 % compression, low end. A constant: if pad_squeeze / pad_t changes much, change this too
pad_mu = 0.5;           // ESTIMATE EVA on powder coat friction, conservative

// ---- 2020 extrusion, slot 6 --------------------------------------------------
ext = 20;
slot_w = 6.3;           // MEASURED 2026-11-17: slot opening
slot_lip = 1.5;         // MEASURED 2026-11-17: lip thickness of the slot opening
slot_cavity_w = 12.2;   // MEASURED 2026-11-17: slot width behind the lip (drawn as a rectangle; the real cavity tapers)
slot_depth = 5.8;       // MEASURED 2026-11-17: face to bottom of the slot
ext_bore = 5.4;         // MEASURED 2026-11-17: centre bore, a square hole
ext_I = 6900;           // ESTIMATE [mm4] second moment of area; check supplier's sheet (equal in both axes)
ext_E = 69000;          // [N/mm2] aluminium
key_w = 5.6;            // printed slot key width (fits slot_w)
key_d = 1.5;            // printed slot key height; stays inside the lip

// M5 hardware
m5_clear = 5.5;
// The bolts are pan head with a Phillips (PH2) drive, not hex button heads: every M5 needs a screwdriver in line with it.
m5_head_d = 10.5;       // MEASURED 2026-11-17: pan head diameter 9.9, + clearance
m5_head_h = 4.3;        // MEASURED 2026-11-17: pan head height 4.0, + clearance
m5_min_thread = 3;      // minimum thread engagement in any T-nut
bolt_long = 9.8;        // MEASURED 2026-11-17: real length under the head of an M5x10 (the M5x8 is 8.0)
// The M5 nuts are drop-in: about 10 x 6 mm seen from above, with two corners cut. They go into the slot from the
// front and turn to lock. A printed pocket must be narrow in one direction, or the nut spins in it.
// (The M4 nuts of the corner brackets are drop-in too: 11.4 x 5.8, 4.1 thick.)
tnut_w = 11.7;          // MEASURED 2026-11-17: M5 nut long diagonal 11.4, + clearance: pocket size, long way
tnut_n = 6.4;           // MEASURED 2026-11-17: M5 nut 6.0 over its long sides, + clearance: pocket size, narrow way
tnut_t = 4.4;           // MEASURED 2026-11-17: M5 nut 4.0 thick, + clearance: pocket size along the bolt
tnut_len = 11.4;        // MEASURED 2026-11-17: M5 nut's longest extent along the slot, before it turns to lock
tnut_recess = 0.5;      // MEASURED 2026-11-17 (by eye): the nut's top sits between the lips, this far below the profile face
key_relief = tnut_len / 2 + 0.5; // no slot key within this distance of a bolt into the profile: the nut's centre is there
m4_head_h = 2.5;        // ESTIMATE corner bracket bolt: M4 button head (2.5 mm key), 2.2 nominal + margin

// ---- MG90S envelope ----------------------------------------------------------
// Servo axes: shaft along the servo's own "height", body length along the ears.
sv_l = 22.8;            // MEASURED 2026-11-17: body length (along the ears)
sv_w = 12.5;            // MEASURED 2026-11-17: body width
sv_h = 28.4;            // MEASURED 2026-11-17: base to top face of the case, without shaft
sv_ear_span = 32.3;     // MEASURED 2026-11-17: ear tip to ear tip
sv_ear_z = 18.2;        // MEASURED 2026-11-17: base to the base-side face of the ears
sv_ear_t = 2.7;         // MEASURED 2026-11-17: ear thickness
sv_hole_pitch = 27.8;   // MEASURED 2026-11-17: ear hole centre to centre
sv_screw_pilot = 1.8;   // ESTIMATE pilot hole for the servo's own screws; test on a scrap
sv_shaft_off = 5.9;     // MEASURED 2026-11-17: shaft axis to the nearest end of the body
sv_shaft_proud = 4.0;   // MEASURED 2026-11-17: shaft top above the top face
sv_stall_kgcm = 2.2;    // ESTIMATE stall torque at 5 V; listings vary 1.8 to 2.2

// ---- The horn pushes: eccentric cam on the stock horn, plus guided plunger ---
// A horn or arm swinging over the button rubs sideways across the cap, and a
// module offset by an arm length does not fit next to its neighbour at 19 mm
// pitch. So each module sits centred on its own column, and a cam on the horn
// pushes a plunger guided straight down. The cam eccentricity is the arm length.
arm_len = 2.5;          // effective lever arm = cam eccentricity
cam_r = 6.75;           // cam disc radius
// cam_t (cam thickness along the shaft) is derived below, from the horn screw
cam_mu = 0.3;           // ESTIMATE printed plastic sliding on printed plastic
horn_seat = 6;          // MEASURED 2026-11-17: servo top face to the outer end of a fitted horn's hub, without the screw
horn_t = 2.1;           // MEASURED 2026-11-17: horn arm thickness
horn_hub_d = 6.8;       // MEASURED 2026-11-17: horn hub diameter
horn_hub_h = 4.9;       // MEASURED 2026-11-17: horn hub height; the hub reaches from the arm down towards the servo, outside the cam
horn_arm_inset = 0.5;   // MEASURED 2026-11-17: the hub's outer end stands this far above the arm's outer face
horn_pocket = horn_t + horn_arm_inset;              // cam pocket depth: the cam's back face is level with the arm's servo-side face
horn_screw_d = 2.5;     // MEASURED 2026-11-17: horn screw thread diameter
horn_screw_len = 10;    // MEASURED 2026-11-18: the M2.5x10 bought for the cam (the stock screw is too short)
shaft_hole_depth = 4.5; // MEASURED 2026-11-18 (about): how far a screw goes into the servo shaft before it bottoms
screw_engage = 4;       // thread wanted in the shaft: 0.5 short of bottoming, so the head clamps
horn_hub_wall = horn_seat - sv_shaft_proud;         // hub end above the shaft end, 2.0: the screw passes it before the shaft
cam_floor = horn_screw_len - horn_hub_wall - screw_engage; // cam material under the screw head, which sits on the cam's front face
cam_t = horn_pocket + cam_floor;                    // cam thickness along the shaft
horn_stub = 7.5;        // length of horn arm kept, from the axis (cut the rest off the stock single arm)
horn_stub_w = 5.5;      // MEASURED 2026-11-17: horn arm width there. The arm tapers: tangent to the hub, this wide at horn_stub
pl_w = 6;               // plunger square section
pl_clear = 0.4;         // total clearance in the guide bore
pl_collar = 9;          // plunger top collar width; stops it dropping out off the desk
pl_collar_t = 2;
pl_dot_proud = 1;       // EVA dot stands this far out of the plunger tip recess
pl_rest_gap = 1;        // gap between cam and plunger top at the cam's closest position
guide_len = 10;         // plunger guide length
guide_wall = 2.4;
guide_clear = 3;        // guide underside above the unpressed button cap; limits downward adjustment

// ---- Servo module: carriage on the rail + height-adjustable bracket ----------
car_w = 16;             // carriage width (X)
car_t = 9;              // carriage thickness (Y)
car_above = 16;         // carriage height above the rail, holds the height-adjust T-nut
car_skin = 3;           // wall between the T-nut pocket and the bracket; the pocket is deeper than the nut, the bolt pulls the nut up to this wall
rail_under_head = car_t - m5_head_h; // printed material under the head of a bolt into the rail (carriage and tensioner block)
br_t = 3.5;             // bracket slotted plate thickness
br_wall = 2.05;         // bracket side wall thickness
br_slide = 0.15;        // side clearance of the bracket on the carriage
sp_t = 4;               // servo plate thickness
shelf_t = 4;            // shelf joining the servo plate to the slotted plate
adj = 6;                // height adjustment, plus and minus
br_back_rib = 4;        // side walls extend this far behind the servo plate

// ---- Clamps ------------------------------------------------------------------
jaw_t = 11;             // jaw thickness post to pad face
jaw_w = 34;             // jaw width along the case side (Y)
grip_h = 25;            // pad height on the case side wall
lip_t = 5;              // lip over the rim
lip_reach = 8;          // lip reach over the rim, kept short of the panel
jaw_under_head = 4.8;   // jaw material under the bolt heads
post_tail = 5;          // post length below the jaw
bracket_leg = 19.6;     // MEASURED 2026-11-17: corner bracket leg length
rail_end_margin = 5;    // rail beyond the tensioner block
ten_gap_x = 0.5;        // tensioner neck to the outer corner bracket, along the rail
ten_gap_z = 6.5;        // tensioner arm below the outer corner bracket, room for the bracket bolt key
bracket_t = 3;          // MEASURED 2026-11-17: corner bracket leg thickness (the bracket is a cube in the CAD)
key_short_arm = 20.5;   // MEASURED 2026-11-17: 2.5 mm L-key for the bracket's M4x8 bolts, short arm length
key_engage = 1.3;       // ESTIMATE how far the key goes into the M4 button head (ISO 7380 minimum)
ten_collar_d = 9.5;     // stop collar outer diameter
ten_collar_steps = [-0.4, -0.2, 0, 0.2]; // printed collar set, relative to the nominal thickness: thinner squeezes more
ten_membrane = 0.2;     // printed skin closing the shoulder hole so the shoulder bridges cleanly; drill it out
ten_neck = 16;          // tensioner neck length along the rail
ten_w = 20;             // tensioner width (Y)
ten_wall = 4;           // tensioner wall above and below the T-nut pocket
ten_shoulder = 2;       // wall the T-nut bears on, with the push bolt head behind it
ten_stub = 8;           // pressure pad stub section and length
ten_plate_t = 3;        // pressure pad plate thickness, bridges the slot in the post
ten_plate_w = 16;       // pressure pad width (Y), wider than slot_w
ten_plate_h = 14;       // pressure pad height (Z), stays below the corner bracket
stock_len = 1000;       // the extrusion Tim ordered
saw_kerf = 3;

// Derived: module chain, bottom up
sleeve_z0 = btn_proud + guide_clear;
sleeve_z1 = sleeve_z0 + guide_len;
z_shaft = sleeve_z1 + 0.5 + pl_collar_t + cam_r + arm_len;
pl_len = z_shaft - (cam_r - arm_len) - pl_rest_gap - btn_proud; // tip to top, plunger resting on the cap
sv_centre_z = z_shaft - sv_shaft_off + sv_l / 2;
sv_top_ear_z = sv_centre_z + sv_ear_span / 2;
shelf_z0 = sv_top_ear_z + 1;
shelf_z1 = shelf_z0 + shelf_t;
rail_z0 = shelf_z1 + adj + 1;
rail_zc = rail_z0 + ext / 2;
rail_z1 = rail_z0 + ext;
nut_z = rail_z1 + car_above / 2;
car_z1 = rail_z1 + car_above;
br_top = nut_z + adj + 6;

// Derived: module, local Y measured outward from the rail centre towards the button
rail_y = btn_y(2);      // rail runs above the ALGEMEEN row, between SC and SPREKEN
mod_d = pitch_y;        // rail centre to button row; same part for both rail faces
car_y0 = ext / 2;
car_y1 = car_y0 + car_t;
br_y1 = car_y1 + br_t;
br_in = car_w / 2 + br_slide;
br_w = 2 * (br_in + br_wall);
cam_back_y = mod_d - cam_t / 2;
sv_top_y = cam_back_y - (horn_seat - horn_pocket);
sv_base_y = sv_top_y - sv_h;
sp_y0 = sv_base_y + sv_ear_z + sv_ear_t;
sp_y1 = sp_y0 + sp_t;
sleeve_half = (pl_w + pl_clear) / 2 + guide_wall;

// Derived: clamp and frame, x measured from the post's inner face
jaw_case_x = jaw_t + pad_t - pad_pocket - pad_squeeze;
// The lip pad only carries the frame's weight, so it compresses less than pad_squeeze
// and the frame sits slightly higher than this. The module height adjustment absorbs it.
lip_z0 = case_rim_h + pad_t - pad_pocket - pad_squeeze;
jaw_z0 = case_rim_h - grip_h;
jaw_z1 = lip_z0 + lip_t;
post_z0 = jaw_z0 - post_tail;
post_len = rail_z0 - post_z0;
post_x_l = -jaw_case_x - ext / 2;           // left post centre
post_x_r = case_w + jaw_case_x + ext / 2;   // right post centre
rail_len = post_x_r - post_x_l + 2 * (ext / 2 + bracket_leg + ten_gap_x + ten_neck + rail_end_margin); // cut length
rail_x0 = (case_w - rail_len) / 2;
post_span = post_x_r - post_x_l;
post_gap_uncompressed = jaw_t + pad_t - pad_pocket; // post inner face to case wall, pad just touching
post_gap_contact = jaw_t;                           // jaw plastic touches the case here: never go this far
post_spacing_target = case_w + 2 * jaw_case_x;      // inner face to inner face of the posts

// Derived: tensioner, local X measured outward from the post's outer face
ten_arm_z1 = rail_z0 - bracket_leg - ten_gap_z;     // arm passes below the outer corner bracket
ten_z = ten_arm_z1 - ten_wall - tnut_n / 2;         // push bolt axis
ten_arm_z0 = ten_z - tnut_n / 2 - ten_wall;
ten_x0 = ten_plate_t;                               // arm's inner end with the pad fully back
ten_nut_x0 = ten_x0 + ten_stub;
ten_nut_x1 = ten_nut_x0 + tnut_t;
ten_head_x = ten_nut_x1 + ten_shoulder;
ten_neck_x0 = bracket_leg + ten_gap_x;
ten_neck_x1 = ten_neck_x0 + ten_neck;
ten_travel = bolt_long - tnut_t - ten_shoulder;     // push bolt reach beyond the nut, head on the shoulder
ten_collar_t = ten_travel - pad_squeeze;            // stop collar: head seats pad_squeeze past pad contact
// ESTIMATE: lowest point of the L-key on the bracket's M4 rail bolt, against the arm below it. The bracket
// is a cube here and the real one is a cast gusset, so access may be from the side or through its window.
bracket_key_clearance = ten_gap_z + bracket_leg - (bracket_t + m4_head_h - key_engage + key_short_arm);
// Feeler gauge: go must fit (plastic is clear), no-go must not fit (the pad is compressed)
gauge_go = jaw_case_x - 0.25;
gauge_nogo = jaw_case_x + 0.35;

// ---- Replica panel (hardware/replica) ----------------------------------------
rp_t = 5;               // top plate thickness
rp_h = 45;              // underside of tray to panel surface; must exceed the post tail
rp_wall = 4;            // outer wall
rp_rib = 2;             // ribs along Y between columns
tb_cap = 13;            // test button cap width
tb_stem = 8;            // test button stem width
tb_slit = 3;            // slit between the two snap prongs
tb_barb = 0.7;          // snap barb overhang
tb_leaf_l = 28;         // leaf spring length, root to stem
tb_leaf_b = 10;         // leaf spring width
tb_preload = 2.5;       // leaf deflection with the button at rest
tb_root_l = 20;         // leaf root block length
tb_root_h = 8;          // leaf root block height
tb_print_E = 3000;      // ESTIMATE [N/mm2] printed PLA; calibrate by measuring the finished button
// Leaf thickness for btn_force at full travel, rounded to 0.2 mm layers (fixed cantilever k = E b t^3 / 4 L^3)
tb_leaf_t = round(5 * pow(btn_force * 4 * pow(tb_leaf_l, 3)
    / ((tb_preload + btn_travel) * tb_print_E * tb_leaf_b), 1 / 3)) / 5;
tb_leaf_z = -rp_t - 6;  // leaf top under the stem at rest
tb_sockets = [["SC1", -1], ["SC2", -1], ["SC3", -1], ["SPREKEN", 1]]; // button, leaf direction in Y

// ---- Speaker holder: Earson ER-151 -------------------------------------------
// The ER-151 is an equilateral triangle with round corners: rubber end parts, and a narrower mesh
// section between them. Shape from the Thingiverse bike holder (thing 2039735, its .scad), sizes
// measured on the speaker.
spk_len = 149;          // MEASURED 2026-11-17: overall length, end to end
spk_r = 11.25;          // MEASURED 2026-11-19: corner radius, a coin of 22 to 23 mm matches the rounding
spk_end_w = 61;         // MEASURED 2026-11-19: rubber end, width over a face
spk_end_s = spk_end_w - 2 * spk_r;                  // corner centre spacing on the rubber ends: 39.5
spk_mesh_w = 54.5;      // MEASURED 2026-11-19: mesh section, width over a face (54.5, 54.5 and 55.4)
spk_mesh_s = spk_mesh_w - 2 * spk_r;                // corner centre spacing on the mesh section, same corner radius assumed
spk_end_len = 25;       // MEASURED 2026-11-19: length of each rubber end part
spk_base = spk_end_w;                               // rubber end, width over a face
spk_h = spk_end_s * sqrt(3) / 2 + 2 * spk_r;        // rubber end, face to opposite corner: 55.8
spk_face_inset = (spk_end_s - spk_mesh_s) / (2 * sqrt(3)); // mesh face behind the rubber end's face: 1.9
spk_driver_pitch = 55;  // driver centres on the long face, symmetric about the face centre
spk_driver_d = 38.1;    // 1.5 inch driver
spk_clear = 0.2;        // TESTED 2026-11-20: cradle clearance per side (0.4, 0.6 and 0.8 rattle)
mic_dist = 40;          // driver face (the mesh) to mic head tip; spec: 30 to 50
mic_offset = 0;         // 0 = mic centred between the drivers, spk_driver_pitch / 2 = mic on one driver
tube_d = 12.5;          // MEASURED 2026-11-12: gooseneck tube outer diameter
tube_lining = 1;        // EVA or rubber lining in the clamp, per side
mic_head_d = 32;        // MEASURED 2026-11-12: mic head diameter
mic_head_len = 45;      // MEASURED 2026-11-12: mic head length
clamp_gap_below_head = 10; // clamp top edge below the mic head
clamp_h = 20;           // clamp height along the tube
cup_lip = 6;            // cradle grips this far along each rubber end part
cup_wall = 3;           // cradle wall
// Snap catch: a flexible tab under each cup's open corner, with a hook the prism's corner snaps behind.
spk_snap = 1.8;         // TESTED 2026-11-20: hook height beyond the free play, how far the tab bends. Hook 2.2 mm tall, as on the 0.6 test piece
snap_tab_l = 16.8;      // tab length along the prism, inward from the cup: as long as the rubber end allows
snap_tab_t = 1.6;       // tab thickness: the direction it bends
snap_hook_l = 5;        // hook length along the prism, at the tab's free end

// ---- Checks true for every part ----------------------------------------------
sv_stall_nmm = sv_stall_kgcm * 98.0665;             // 1 kg.cm = 98.0665 N.mm
press_torque = btn_force * (arm_len + cam_mu * cam_r); // lever plus cam friction, worst cam angle
servo_margin = sv_stall_nmm / press_torque;
assert(servo_margin >= 2, "servo force margin below 2x at this arm length");
assert(cam_r + arm_len <= pitch_x / 2 - 0.25, "cams of neighbouring modules could touch");
assert(cam_r - arm_len >= horn_hub_d / 2 + 0.15 + 0.4, "cam wall around the horn hub too thin");
assert(horn_pocket <= horn_hub_h && horn_seat - horn_hub_h >= 0, "horn measurements do not add up");
assert(cam_floor >= 1.5, "horn screw too short for the cam: thread would bottom out or not clamp");
assert(screw_engage <= shaft_hole_depth - 0.3, "horn screw would bottom out in the shaft before the head clamps");
assert(car_w / 2 - key_relief >= 1.5 && ten_neck / 2 - key_relief >= 1.5, "no room for a slot key beside the T-nut");
assert(key_d > tnut_recess, "slot key no longer needs its relief around the nut");
assert(ten_z + m5_head_d / 2 + 0.1 <= ten_arm_z1 - 1.5, "tensioner head slot breaks through the top of the arm");
assert(car_w - tnut_w >= 4, "carriage walls beside the T-nut pocket thinner than 2 mm");
assert(jaw_under_head + m5_head_h <= jaw_t - pad_pocket, "jaw bolt head stands into the pad pocket");
assert(bolt_long - ten_shoulder - ten_collar_t - max(ten_collar_steps) >= m5_min_thread, "push bolt thread engagement too short");
assert(pad_squeeze <= 0.6 * (pad_t - pad_pocket), "pad_squeeze too close to jaw plastic touching the case");
assert(ten_travel >= 2 * pad_squeeze, "tensioner travel too short for the squeeze");
assert(ten_travel - ten_collar_t < pad_t - pad_pocket - 0.3, "stop collar lets the jaw plastic reach the case");
assert(ten_collar_t + min(ten_collar_steps) >= 1.2, "thinnest stop collar too thin to print");
assert(ten_travel - ten_collar_t - min(ten_collar_steps) <= pad_t - pad_pocket - 0.2, "thinnest stop collar lets the jaw plastic reach the case");
assert(bracket_key_clearance >= 1, "hex key cannot reach the outer corner bracket's rail bolt");
assert(gauge_go >= post_gap_contact + 0.2, "go blade would pass with the jaw plastic touching");
assert(gauge_nogo <= post_gap_uncompressed - 0.2, "no-go blade would pass with the pad uncompressed");
assert(ten_z + ten_plate_h / 2 <= rail_z0 - bracket_leg, "tensioner pad would hit the corner bracket");
assert(ten_arm_z0 > jaw_z1, "tensioner must stay above the jaw");
assert(br_w < pitch_x, "module wider than the button pitch");
assert(bolt_long - br_t - car_skin >= m5_min_thread, "height bolt thread engagement too short");
assert(bolt_long - rail_under_head - slot_lip >= m5_min_thread, "rail bolt thread engagement too short");
assert(bolt_long - jaw_under_head - slot_lip >= m5_min_thread, "clamp bolt thread engagement too short");
assert(bolt_long - jaw_under_head <= slot_depth - 0.3, "clamp bolt bottoms out in the slot");
assert(bolt_long - rail_under_head <= slot_depth - 0.3, "rail bolt bottoms out in the slot");
assert(sp_y1 <= car_y1, "servo plate must sit below the carriage");
assert(lip_reach <= case_rim_w - 1, "clamp lip must stay on the rim");
assert(grip_h + post_tail <= case_h - 10, "post would reach the table");
assert(rp_h >= grip_h + post_tail, "replica too shallow for the posts");
assert(rail_len + 2 * post_len + 2 * saw_kerf <= stock_len, "rail and posts do not fit the ordered 1 m");
assert(mic_dist >= 30 && mic_dist <= 50, "mic distance outside 3-5 cm");
assert(spk_driver_pitch / 2 + spk_driver_d / 2 <= spk_len / 2 - cup_lip, "cradle would cover a driver");
assert(spk_driver_pitch / 2 + spk_driver_d / 2 <= spk_len / 2 - cup_lip - snap_tab_l, "snap tab would reach a driver");
assert(cup_lip + snap_tab_l + spk_clear <= spk_end_len - 2, "snap hook must catch the rubber end, not the mesh section");
// PLA yields at about 3 to 4 % strain; the cradle snaps on a handful of times, so 2 % leaves margin
assert(1.5 * snap_tab_t * spk_snap / pow(snap_tab_l, 2) <= 0.02, "snap tab bends past 2 % strain: PLA may crack");
for (a = actuated) {
    assert(len([for (c = covered_buttons) if (c == a) c]) == 0, str(a, " is a covered button, never actuate it"));
    assert(abs(abs(btn_xy(a)[1] - rail_y) - mod_d) < 0.01, str(a, " is not one row from the rail; the module cannot reach it"));
}
