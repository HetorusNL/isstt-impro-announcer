// ISSTT IMPRO announcer servo rig: the one parameter file.
//
// Every part file includes this file. Units: mm, N, degrees.
//
// ESTIMATE = scaled from docs/reference/impro-desk.jpg (19 mm column pitch as
// the scale reference, buttons assumed square to undo the camera angle) or
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
case_w = 181;           // ESTIMATE measure: case outer width, left to right
case_d = 190;           // ESTIMATE measure: case outer depth, front to back
case_h = 65;            // ESTIMATE measure: table to the top of the black rim
case_rim_w = 10;        // ESTIMATE measure: width of the black rim seen from above (edge profile)
case_rim_h = 2;         // ESTIMATE measure: rim top above the panel surface (edge profile)

// ---- Buttons ----------------------------------------------------------------
pitch_x = 19;           // ESTIMATE scale reference; measure: SC 1 centre to SC 6 centre, divide by 5
pitch_y = 21.5;         // ESTIMATE measure: SC 1 centre to ALGEMEEN centre
btn_size = 16;          // ESTIMATE measure: outer bezel width of one button
btn_proud = 4;          // ESTIMATE measure: unpressed cap top above the panel
btn_travel = 2.5;       // ESTIMATE measure: cap travel until it clicks, with calipers
btn_force = 3;          // ESTIMATE [N] measure: SPREKEN press force (cup + water/coins, then weigh)
btn_x0 = 33.5;          // ESTIMATE measure: case left face to the SC 1 centre
btn_y_row3 = 41;        // ESTIMATE measure: case front face to the SPREKEN centre

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
alarm_xy = btn_xy("ONTRUIMING"); // ESTIMATE measure: case left and front faces to the alarm button centre
koppel_xy = btn_xy("KOPPEL");    // ESTIMATE measure: case left and front faces to the Koppel ruimtes button centre
function panel_xy(name) = name == "ONTRUIMING" ? alarm_xy : name == "KOPPEL" ? koppel_xy : btn_xy(name);
cover_w = 18;           // ESTIMATE measure: flip cover width (X)
cover_d = 20;           // ESTIMATE measure: flip cover depth (Y)
cover_h = 12;           // ESTIMATE measure: closed cover top above the panel
cover_pin_z = 4;        // ESTIMATE measure: hinge pin height above the panel (dummy cover on the replica)
cover_swing_r = sqrt(cover_d * cover_d + cover_h * cover_h); // cover pivots on its back edge
keepout_side = 10;      // finger room left and right of the cover
lip_clearance_min = 4;  // minimum clearance, any part to the cover lip. Not finger room: the hand comes from above
keepout_back = 5;       // margin behind the swung-open cover
keepout_h = 120;        // hand room above the panel; no part may span over the cover below this

// [[xmin, ymin, zmin], [xmax, ymax, zmax]] of the keep-out around one covered button
function keepout_box(name) = let (p = panel_xy(name)) [
    [p[0] - cover_w / 2 - keepout_side, p[1] - cover_d / 2 - lip_clearance_min, 0],
    [p[0] + cover_w / 2 + keepout_side, p[1] + cover_d / 2 + cover_swing_r + keepout_back, keepout_h]
];

// ---- Rubber/EVA pads --------------------------------------------------------
pad_t = 3;              // EVA or rubber sheet thickness (sheet not ordered yet; measure when it arrives)
pad_pocket = 1.5;       // pad recess depth; the pad stands proud by the rest
pad_squeeze = 0.8;      // compression per side when clamped: one full turn of the M5 push bolt. The one squeeze number; sets the stop collar
pad_stress = 0.05;      // ESTIMATE [N/mm2] EVA stress at about 25 % compression, low end. A constant: if pad_squeeze / pad_t changes much, change this too
pad_mu = 0.5;           // ESTIMATE EVA on powder coat friction, conservative

// ---- 2020 extrusion, slot 6 --------------------------------------------------
ext = 20;
slot_w = 6.2;           // ESTIMATE measure: slot opening
slot_lip = 1.8;         // ESTIMATE measure: lip thickness of the slot opening
slot_cavity_w = 11;     // ESTIMATE measure: slot width behind the lip
slot_depth = 6.1;       // ESTIMATE measure: face to bottom of the slot
ext_bore = 4.2;         // ESTIMATE measure: centre bore
ext_I = 6900;           // ESTIMATE [mm4] second moment of area; check supplier's sheet (equal in both axes)
ext_E = 69000;          // [N/mm2] aluminium
key_w = 5.6;            // printed slot key width (fits slot_w)
key_d = 1.5;            // printed slot key height; stays inside the lip

// M5 hardware
m5_clear = 5.5;
m5_head_d = 10.5;       // ESTIMATE measure: button head diameter (9.5 nominal) + clearance
m5_head_h = 3.2;        // ESTIMATE measure: button head height (2.75 nominal) + clearance
m5_min_thread = 3;      // minimum thread engagement in any T-nut
bolt_long = 10;         // the longer of the two ordered lengths (M5x8, M5x10)
tnut_w = 10.6;          // ESTIMATE measure a slide-in T-nut; pocket size across
tnut_t = 5;             // ESTIMATE measure a slide-in T-nut; pocket depth

// ---- MG90S envelope ----------------------------------------------------------
// Servo axes: shaft along the servo's own "height", body length along the ears.
sv_l = 22.8;            // ESTIMATE measure: body length (along the ears)
sv_w = 12.2;            // ESTIMATE measure: body width
sv_h = 28.5;            // ESTIMATE measure: base to top face of the case, without shaft
sv_ear_span = 32.3;     // ESTIMATE measure: ear tip to ear tip
sv_ear_z = 18.5;        // ESTIMATE measure: base to the base-side face of the ears
sv_ear_t = 2.5;         // ESTIMATE measure: ear thickness
sv_hole_pitch = 27.8;   // ESTIMATE measure: ear hole centre to centre
sv_screw_pilot = 1.8;   // ESTIMATE pilot hole for the servo's own screws; test on a scrap
sv_shaft_off = 5.9;     // ESTIMATE measure: shaft axis to the nearest end of the body
sv_shaft_proud = 3.6;   // ESTIMATE measure: shaft top above the top face
sv_stall_kgcm = 2.2;    // ESTIMATE stall torque at 5 V; listings vary 1.8 to 2.2

// ---- The horn pushes: eccentric cam on the stock horn, plus guided plunger ---
// A horn or arm swinging over the button rubs sideways across the cap, and a
// module offset by an arm length does not fit next to its neighbour at 19 mm
// pitch. So each module sits centred on its own column, and a cam on the horn
// pushes a plunger guided straight down. The cam eccentricity is the arm length.
arm_len = 2.5;          // effective lever arm = cam eccentricity
cam_r = 6.75;           // cam disc radius
cam_t = 6;              // cam thickness (along the shaft)
cam_mu = 0.3;           // ESTIMATE printed plastic sliding on printed plastic
horn_seat = 4;          // ESTIMATE measure: servo top face to the horn's outer face with a horn fitted
horn_t = 1.8;           // ESTIMATE measure: horn arm thickness
horn_hub_d = 7.2;       // ESTIMATE measure: horn hub diameter
horn_hub_h = 3.4;       // ESTIMATE measure: horn hub height
horn_stub = 7.5;        // length of horn arm kept, from the axis (cut the rest off the stock single arm)
horn_stub_w = 5;        // ESTIMATE measure: horn arm width there
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
car_w = 13;             // carriage width (X)
car_t = 8;              // carriage thickness (Y)
car_above = 16;         // carriage height above the rail, holds the height-adjust T-nut
car_skin = car_t - tnut_t; // wall between the T-nut pocket and the bracket
br_t = 3.5;             // bracket slotted plate thickness
br_wall = 2.05;         // bracket side wall thickness
br_slide = 0.15;        // side clearance of the bracket on the carriage
sp_t = 4;               // servo plate thickness
shelf_t = 4;            // shelf joining the servo plate to the slotted plate
adj = 6;                // height adjustment, plus and minus
br_back_rib = 4;        // side walls extend this far behind the servo plate

// ---- Clamps ------------------------------------------------------------------
jaw_t = 10;             // jaw thickness post to pad face
jaw_w = 34;             // jaw width along the case side (Y)
grip_h = 25;            // pad height on the case side wall
lip_t = 5;              // lip over the rim
lip_reach = 8;          // lip reach over the rim, kept short of the panel
jaw_under_head = 4;     // jaw material under the bolt heads
post_tail = 5;          // post length below the jaw
bracket_leg = 20;       // ESTIMATE measure: corner bracket leg length
rail_end_margin = 5;    // rail beyond the tensioner block
ten_gap_x = 0.5;        // tensioner neck to the outer corner bracket, along the rail
ten_gap_z = 6.5;        // tensioner arm below the outer corner bracket, room for the hex key
bracket_t = 3;          // ESTIMATE measure: corner bracket leg thickness (the bracket is a cube in the CAD)
key_short_arm = 20;     // ESTIMATE measure: 3 mm L-key, short arm length including the long arm's thickness
key_engage = 2.5;       // ESTIMATE measure: how far the key goes into the button head
ten_collar_d = 9.5;     // stop collar outer diameter
ten_membrane = 0.2;     // printed skin closing the shoulder hole so the shoulder bridges cleanly; drill it out
ten_neck = 16;          // tensioner neck length along the rail
ten_w = 20;             // tensioner width (Y)
ten_wall = 3;           // tensioner wall above and below the T-nut pocket
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
sv_top_y = cam_back_y - (horn_seat - horn_t);
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
ten_z = ten_arm_z1 - ten_wall - tnut_w / 2;         // push bolt axis
ten_arm_z0 = ten_z - tnut_w / 2 - ten_wall;
ten_x0 = ten_plate_t;                               // arm's inner end with the pad fully back
ten_nut_x0 = ten_x0 + ten_stub;
ten_nut_x1 = ten_nut_x0 + tnut_t;
ten_head_x = ten_nut_x1 + ten_shoulder;
ten_neck_x0 = bracket_leg + ten_gap_x;
ten_neck_x1 = ten_neck_x0 + ten_neck;
ten_travel = bolt_long - tnut_t - ten_shoulder;     // push bolt reach beyond the nut, head on the shoulder
ten_collar_t = ten_travel - pad_squeeze;            // stop collar: head seats pad_squeeze past pad contact
// Lowest point of a 3 mm L-key on the bracket's rail bolt, against the arm below it
bracket_key_clearance = ten_gap_z + bracket_leg - (bracket_t + m5_head_h - key_engage + key_short_arm);
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
tb_print_E = 2000;      // ESTIMATE [N/mm2] printed PETG; calibrate by measuring the finished button
// Leaf thickness for btn_force at full travel, rounded to 0.2 mm layers (fixed cantilever k = E b t^3 / 4 L^3)
tb_leaf_t = round(5 * pow(btn_force * 4 * pow(tb_leaf_l, 3)
    / ((tb_preload + btn_travel) * tb_print_E * tb_leaf_b), 1 / 3)) / 5;
tb_leaf_z = -rp_t - 6;  // leaf top under the stem at rest
tb_sockets = [["SC1", -1], ["SC2", -1], ["SC3", -1], ["SPREKEN", 1]]; // button, leaf direction in Y

// ---- Speaker holder: Earson ER-151 -------------------------------------------
spk_len = 150;          // ESTIMATE from web listings; measure: prism length
spk_base = 56;          // ESTIMATE from web listings; measure: width of the driver face
spk_h = 56;             // ESTIMATE from web listings; measure: driver face to opposite ridge
spk_driver_pitch = 55;  // driver centres on the long face, symmetric about the face centre
spk_driver_d = 38.1;    // 1.5 inch driver
spk_clear = 0.8;        // cradle clearance per side
mic_dist = 40;          // driver face to mic head tip; spec: 30 to 50
mic_offset = 0;         // 0 = mic centred between the drivers, spk_driver_pitch / 2 = mic on one driver
tube_d = 10;            // ESTIMATE measure: gooseneck tube outer diameter, 8 to 12
tube_lining = 1;        // EVA or rubber lining in the clamp, per side
mic_head_d = 20;        // ESTIMATE measure: mic head diameter (not in the photo)
mic_head_len = 30;      // ESTIMATE measure: mic head length (not in the photo)
clamp_gap_below_head = 10; // clamp top edge below the mic head
clamp_h = 20;           // clamp height along the tube
cup_lip = 8;            // cradle grips this far along each prism end
cup_wall = 3;           // cradle wall

// ---- Checks true for every part ----------------------------------------------
sv_stall_nmm = sv_stall_kgcm * 98.0665;             // 1 kg.cm = 98.0665 N.mm
press_torque = btn_force * (arm_len + cam_mu * cam_r); // lever plus cam friction, worst cam angle
servo_margin = sv_stall_nmm / press_torque;
assert(servo_margin >= 2, "servo force margin below 2x at this arm length");
assert(cam_r + arm_len <= pitch_x / 2 - 0.25, "cams of neighbouring modules could touch");
assert(cam_r - arm_len >= horn_hub_d / 2 + 0.15 + 0.4, "cam wall around the horn hub too thin");
assert(pad_squeeze <= 0.6 * (pad_t - pad_pocket), "pad_squeeze too close to jaw plastic touching the case");
assert(ten_travel >= 2 * pad_squeeze, "tensioner travel too short for the squeeze");
assert(ten_travel - ten_collar_t < pad_t - pad_pocket - 0.3, "stop collar lets the jaw plastic reach the case");
assert(ten_collar_t >= 1.2, "stop collar too thin to print");
assert(bracket_key_clearance >= 1, "hex key cannot reach the outer corner bracket's rail bolt");
assert(gauge_go >= post_gap_contact + 0.2, "go blade would pass with the jaw plastic touching");
assert(gauge_nogo <= post_gap_uncompressed - 0.2, "no-go blade would pass with the pad uncompressed");
assert(ten_z + ten_plate_h / 2 <= rail_z0 - bracket_leg, "tensioner pad would hit the corner bracket");
assert(ten_arm_z0 > jaw_z1, "tensioner must stay above the jaw");
assert(br_w < pitch_x, "module wider than the button pitch");
assert(bolt_long - br_t - car_skin >= m5_min_thread, "height bolt thread engagement too short");
assert(bolt_long - (car_t - m5_head_h) - slot_lip >= m5_min_thread, "carriage bolt thread engagement too short");
assert(bolt_long - jaw_under_head - slot_lip >= m5_min_thread, "clamp bolt thread engagement too short");
assert(bolt_long - jaw_under_head <= slot_depth, "clamp bolt bottoms out in the slot");
assert(bolt_long - (car_t - m5_head_h) <= slot_depth, "carriage bolt bottoms out in the slot");
assert(sp_y1 <= car_y1, "servo plate must sit below the carriage");
assert(lip_reach <= case_rim_w - 1, "clamp lip must stay on the rim");
assert(grip_h + post_tail <= case_h - 10, "post would reach the table");
assert(rp_h >= grip_h + post_tail, "replica too shallow for the posts");
assert(rail_len + 2 * post_len + 2 * saw_kerf <= stock_len, "rail and posts do not fit the ordered 1 m");
assert(mic_dist >= 30 && mic_dist <= 50, "mic distance outside 3-5 cm");
assert(spk_driver_pitch / 2 + spk_driver_d / 2 <= spk_len / 2 - cup_lip, "cradle would cover a driver");
for (a = actuated) {
    assert(len([for (c = covered_buttons) if (c == a) c]) == 0, str(a, " is a covered button, never actuate it"));
    assert(abs(abs(btn_xy(a)[1] - rail_y) - mod_d) < 0.01, str(a, " is not one row from the rail; the module cannot reach it"));
}
