# Servo rig parts

Parametric OpenSCAD sources for the rig that presses buttons on the IMPRO desk from the outside. The numbers come from one file, `params.scad`. Most desk numbers are estimates from the photo, marked `// ESTIMATE` with what to measure. Change them there, re-render, reprint.

Render a part with `openscad -o part.stl part.scad`. STLs are not committed. Each part file lays its part in print orientation.

## Parts

| File | Part | Print |
|---|---|---|
| `edge_clamp.scad` | Padded clamp jaw, for both case sides (the same part turned 180 degrees) | 2 |
| `servo_carriage.scad` | Module carriage: bolts to a rail face, keyed in the slot | 4 |
| `servo_bracket.scad` | Module bracket: holds the servo and plunger guide, slides up and down the carriage | 4 |
| `servo_cam.scad` | Cam on the servo horn | 4 |
| `servo_plunger.scad` | Plunger between cam and button | 4 + spare |
| `end_cap.scad` | Press-fit end cap: 2 rail ends, 2 post bottoms | 4 + spare |
| `speaker_cradle.scad` | ER-151 cradle, arm and fixed half of the tube clamp | 1 |
| `speaker_clamp_cap.scad` | Removable half of the tube clamp | 1 |
| `../replica/replica_panel.scad` | Replica of the desk top | 1 |
| `../replica/test_button_plunger.scad` | Test button cap and snap stem | 4 |
| `../replica/test_button_leaf.scad` | Test button leaf spring | 4 + spare |
| `../replica/alarm_cover.scad` | Dummy flip cover | 2 |
| `frame_assembly.scad` | The whole rig. Not printed: a picture and the safety checks | - |
| `params.scad`, `lib.scad` | All dimensions; shared geometry | - |

## Print settings (Bambu Lab H2D)

| Setting | Structural parts (clamps, carriages, brackets) | Other parts |
|---|---|---|
| Material | PETG (PLA also works, but creeps under the clamp load in a warm room) | PETG or PLA |
| Layer height | 0.2 mm | 0.2 mm |
| Walls | 5 | 3 |
| Top and bottom layers | 6 | 4 |
| Infill | 40 % gyroid | 15 % |
| Supports | None | Only for `speaker_cradle.scad`, under the cups |

Print the replica open side down. The plate bridges between the ribs. The leaf springs need 100 % infill and must lie flat, so the leaf thickness is a whole number of layers. Print the plungers and the cam with 5 walls: they carry the press force.

## Cutting the extrusion

From the 1 m 2020 profile, with the default parameters:

- 1 rail, `rail_len` = **292.5 mm**
- 2 posts, `post_len` = **90.7 mm** each

That leaves about 520 mm spare. These lengths change when the desk is measured: run `openscad -o /tmp/a.stl frame_assembly.scad` and read them from the `ECHO` lines. Cut after measuring the desk.

## Assembly

**The T-nuts are slide-in: they only enter from a profile end.** Insert every nut you need **before** fitting corner brackets or end caps. If you miss one, the joint has to come apart.

Count of slide-in nuts, with the default four modules:

| Where | Slot | Nuts |
|---|---|---|
| Rail | Back face (towards the SC row) | 3, one per SC module |
| Rail | Front face (towards SPREKEN) | 1 |
| Each post | Inner face, for the clamp jaw | 2 per post, so 4 |
| Module carriages | Pocket for the height bolt | 4 |
| Speaker clamp | Pockets | 2 |
| **Total** | | **14 of the 20 ordered** |

The corner brackets come with their own hardware. If its nuts are also slide-in, add them too: 2 per bracket, one each on the rail's bottom slot and the post's side slot. That makes 22 and exceeds the 20 ordered, so buy a few more in that case.

1. Cut the rail and posts, then fit the nuts above, plus any corner bracket nuts.
2. Join each post's top end to the rail's bottom face with 2 corner brackets, one on each side of the post. Leave the bolts loose enough for the posts to slide along the rail.
3. Press the end caps into the rail ends and post bottoms.
4. Bolt a jaw to each post's inner face with 2 M5x10, key in the slot, then push pads into the pockets (side and under the lip). No adhesive. The pad covers the bolt heads, so take it out to adjust the jaw.
5. Module: trim a stock single horn to `horn_stub` (7.5 mm from the axis). Drop the plunger into the guide from above, with a dot of EVA in its tip recess. Fit the servo from the back with the ears on the back face and the servo's own screws. Fit the horn and the cam with the horn screw. If that screw is too short, use M2x8.
6. Carriage on rail: M5x10 into a T-nut, key in the slot. Bracket on carriage: M5x10 through the slot into a T-nut in the pocket. The slot also gives a hex key access to the rail bolt, so a module can slide along the rail without taking it apart.
7. Clamp: lower the frame over the desk with the lips resting on the rim. Squeeze the posts together until the pads compress by about 1 mm, then tighten the corner brackets. The compressed foam is the clamping force.
8. Slide each module over its button and tighten. Adjust the height so that the plunger rests on the cap with about 1 mm gap to the cam.

Module height adjustment is +6 mm and -3 mm: further down, the guide touches the cap.

Use M5x10 for every printed part. M5x8 leaves too little thread in the T-nut there.

## Cam calibration

Fit the cam with the eccentric horizontal at servo angle 90 (the groove on the cam's face marks the eccentric). Then calibrate with the GUI on the real button. Expect rest at about 135 and press at about 65; the numbers mirror depending on which side the eccentric points. Stop at the angle where the button just bottoms out. Going further only makes the servo push against the stop and draw current.

The angles in `config.example.toml` (rest 90, press 60) are placeholders and too small a swing for the cam.

## The button pusher: why a cam

The brief allows a horn or an arm. A swinging arm has two problems at this pitch:

- With a module offset by an arm length, the arm of one module reaches the shaft of the next once the arm is longer than about 11 mm, and the stock horn is longer than that.
- With an arm that short, the pushing finger has to hang down far enough to clear the servo body, and it then slides 5 to 6 mm across the cap during the press.

So each module sits centred on its own column, and a cam on the horn pushes a plunger straight down in a guide. The cam's eccentricity (`arm_len`) is the effective arm length. This also takes up less room and gets a much better force margin.

## Stiffness and force

The requirement: holding SPREKEN, deflection < 0.5 mm, servo force margin at least 2x at the arm length used.

### Force margin at the default arm length

MG90S stall torque is about 2.2 kg.cm at 5 V (ESTIMATE). 2.2 kg.cm is 215.7 N.mm.

Press force 3 N (ESTIMATE) at arm length 2.5 mm, plus cam friction (mu 0.3 at radius 7 mm, ESTIMATE):

- Lever: 3 N x 2.5 mm = 7.5 N.mm
- Friction: 3 N x 0.3 x 7 mm = 6.3 N.mm
- Required torque: 13.8 N.mm

**Margin: 215.7 / 13.8 = 15.6x.** At 1.8 kg.cm, the low end of the listings, it is 12.8x. The 2x limit is reached at a press force of about 23 N. `params.scad` fails the render if the margin drops below 2.

### Deflection while holding SPREKEN

Estimates with press force 3 N; printed PETG E = 2000 N/mm2. The real test is the stiffness check under "Manual checks".

| Item | Calculation | Deflection |
|---|---|---|
| Rail bending | 2020, simply supported over 222.5 mm, load at the middle (worst case): F L^3 / 48 E I | 0.0014 mm |
| Module lower walls | Moment 3 N x 12 mm over 20 mm, two walls 2 x 10 mm | 0.012 mm |
| Module upper U section | Moment 3 N x 12 mm over 39 mm, shelf to height bolt, walls 2 x 11 mm (conservative: the plate also bears on the carriage) | 0.018 mm |
| Plunger compression | 3 N over 6 x 6 mm, 18.5 mm long | 0.001 mm |
| Pad shear | 1.5 N per side over 607 mm2 of 3 mm EVA, G = 0.5 N/mm2 (ESTIMATE) | 0.015 mm |
| **Sum** | | **about 0.05 mm** |

The bolted joints are not in that sum. Even at several times this figure, the budget is well inside 0.5 mm. Gear backlash at the cam is also small: 1 degree at 2.5 mm is 0.04 mm, against 0.35 mm on a 20 mm arm. The load keeps it taken up during a hold.

How the design gets there:

- **Both sides clamped:** the rail spans between two posts, one on each side of the case, so it never acts as a cantilever.
- **Extrusion against the press force:** the reaction pulls straight up the rail's cross-section and along the posts' length. A 2020 profile is square, so its strong axis is both axes (ESTIMATE I = 6900 mm4). No bending reaches a weak section. A printed rail would be many times less stiff.
- **Generous module walls and ribs:** each bracket is a U section whose side walls run from the plunger guide up past the rail, deep behind the servo plate. The servo plate carries the load in its own plane, and the screws in shear, not pull-out.
- **Metal joints:** 2 corner brackets per post.

### Clamp grip

The press force pushes the frame up, and friction at the pads holds it down. At 25 % compression the EVA gives about 0.05 N/mm2 (ESTIMATE, low end) over 607 mm2, so 30 N per side. With mu 0.5 (ESTIMATE) both pads hold 30 N. That is 10x the SPREKEN load, and 2.5x even with all four buttons held at once. The frame's own weight adds to this, and the lips stop it going down.

## Safety: covered buttons

*Ontruimingsalarm* and *Koppel ruimtes* have keep-out volumes in `params.scad`. They cover the flip cover, its swing, finger room and hand room up to 120 mm. `frame_assembly.scad` shows them as translucent volumes and fails the render if the rail, a post, a clamp or a module enters one. `params.scad` also fails the render if a covered button is listed as actuated. Nothing may ever be mounted over them.

The nearest part is the SC 3 module, directly in front of the alarm. Its guide ends about 6 mm in front of the cover's lip. The keep-out passes, but only the manual check below can show whether it is comfortable by hand.

## Speaker holder

The ER-151 slides into the cradle from the open side, then a strap holds it. The strap goes through the slots in the beam and around the prism outside the driver area.

- The driver face points at the mic head, at `mic_dist` (default 40 mm, spec 30 to 50 mm).
- `mic_offset` is 0 for the mic centred between the drivers, or 27.5 for the mic in line with one driver.
- The cups only hold the prism ends, outside the drivers. The end walls have windows, and the sloped faces stay free, so the USB and 3.5 mm plugs fit wherever they turn out to be.
- The tube clamp takes `tube_d` plus a rubber or EVA lining of `tube_lining` per side. Tighten by hand: it must not mark the gooseneck.

**Check first:** the holder and speaker hang on the gooseneck, and a gooseneck may sag under the speaker. See the checklist.

## Test button

Choice: a **printed leaf spring**, no parts to buy. The cap sits on a split stem with snap barbs under the panel. The stem presses on a leaf whose root pushes into a tunnel under the panel.

The leaf is a cantilever, `k = E b t^3 / (4 L^3)`. `params.scad` calculates its thickness from `btn_force`, rounded to whole 0.2 mm layers. The default gives t = 1.4 mm and 3.1 N at full travel, but only if printed PETG really has E = 2000 N/mm2, which is an estimate.

**Calibrate it after printing:** cup + water/coins on the cap until the cap lands, then weigh. If it is off, change `tb_print_E` and reprint the leaf.

The cap landing on the panel is the hard stop, and it represents the button being actuated. Check it with a strip of paper under the cap: when the strip is trapped, the button is fully pressed.

## Manual checks, left for Tim

- [ ] Print the parts and the replica.
- [ ] Calibrate the test button force (see above).
- [ ] Measure the desk and replace every `ESTIMATE` in `params.scad` that matters for fit. Reprint.
- [ ] Check T-nut and servo fits on one printed carriage and bracket before printing all four.
- [ ] **Stiffness:** on the replica, hold SPREKEN with the servo at its press angle for 60 s. The paper strip stays trapped the whole time, and deflection measured at the rail or module is below 0.5 mm (feeler gauge or dial).
- [ ] **Force margin:** check again with the measured press force. Margin = stall torque / (force x (`arm_len` + 0.3 x `cam_r`)), at least 2x.
- [ ] **Cover:** with the rig on the replica, open the dummy flip cover by hand on the alarm and on Koppel ruimtes. Repeat on the real desk on site.
- [ ] **Speaker:** mount the holder on the gooseneck and check it does not sag. Check the distance to the mic with a ruler.
