# Bill of materials

Shipping takes 2-4 weeks, so order early.

| Qty | Part | Reason |
|-----|------|--------|
| 10 | MG90S metal-gear micro servos — **arrived**, measured 2026-11-17 | 4 needed (SC1, SC2, SC3, SPREKEN); 6 spare or for extra buttons (firmware drives up to 8 channels) |
| 1 | 5 V, ≥ 4 A regulated wall adapter with barrel jack (closed unit, e.g. Mean Well GST25E05; no open-frame mains supply) | Powers the servos and the Nucleo (E5V). 4 servos move one at a time in normal use; worst case all 4 return to rest at once (~3–4 A peak, buffered by the 1000 µF cap). A closed adapter avoids exposed mains terminals at the venue. Budget more if running all 8 servos with simultaneous moves |
| 1 | 5.5/2.1 mm female DC jack to screw-terminal adapter | Feeds the servo rail and the Nucleo E5V/GND from the adapter (candidate adapter: TinyTronics XSG-0504000HEU, 5.0 V 4 A, 5.5/2.1 mm). Check the voltage under load stays within 4.75–5.25 V |
| 10 | Servo extension leads, 30 cm — **ordered** | Reach from the controller to the servos on the desk |
| 1 set | Jumper wires (Dupont), perfboard, pin headers — **on hand** | Servo rail on perfboard: a 3-pin header per servo (GND / +5 V / signal), signal pins to the Nucleo header by jumper. Tape or hot-glue connections for transport |
| 1 | 1000 uF electrolytic capacitor, ≥ 10 V (16 V preferred) — **on hand** | Across the servo rail (+5 V / GND, mind polarity) close to the servo headers, to absorb current spikes |
| 1 | Earson ER-151 speaker (Tim's own; triangular, measured 149×54.5×55 mm, 2× 1.5" drivers) on the laptop's 3.5 mm output — **on hand** | Plays the announcement at the paging desk mic. No USB sound card: previews also come out of this speaker, which is harmless because the desk mic is only live while Spreken is held. Battery lasts ~5 h, so power it from a separate USB wall charger (not the laptop) during the day; check for hum and for auto power-off in AUX mode |
| 1 | 2020 aluminium extrusion, 1 m (slot 6) — **arrived**, measured 2026-11-17 | Stiff backbone; cut to length (desk measured 2026-11-12: 1 rail 425.6 mm, 2 posts 97.4 mm, about 374 mm spare; the rig needs 73 mm of free space beside each side wall) |
| 4 | 2020 aluminium corner brackets (123-3D, cast gusset with centring lips and a window in the sloped face), with 2 M4×8 bolts and 2 M4 drop-in nuts each, so 8 of each — **arrived**, measured 2026-11-17 | Rigid joints between rails / clamp blocks (stiffer than printed joints). M4, not M5: the bracket nuts come on top of the 18 M5 nuts. The M4 bolts take a 2.5 mm hex key |
| 20 + 50 + 50 | M5 drop-in T-nuts for 2020 (about 10×6 mm, go in from the front and turn to lock), M5×8 and M5×10 bolts — **arrived**, measured 2026-11-17: pan head with Phillips (PH2) drive, not hex button head | All printed parts mount with M5 into the slot; servos use their own MG90S screws. End caps are printed |
| 1 | EVA foam sheet, high density, 3 mm — **arrived**: 3.0 mm thick, no adhesive backing | Clamp pads |
| 4 + spare | M2.5x5 or M2.5x6 horn screws, same kind as the MG90S stock horn screw (pointed self-tapping or blunt machine thread) — **to buy** | Hold the cam on the horn. The stock screw is too short with the cam fitted |
| 1 | Speaker strap: any velcro cable tie or elastic strap that fits the cradle slots (3 × 18.8 mm) | Holds the ER-151 in the cradle |
| (4) | M2×8 screws for the servo horns, **only if needed** | Only if the stock horn screw is too short with the cam fitted. Check on one servo first |

## Order status / expected delivery

| Part | Supplier | Ordered on | Expected delivery |
|------|----------|------------|-------------------|
| MG90S servos ×10 | TinyTronics (000263) | 2026-11-01 | in stock (Eindhoven warehouse), a few days |
| Power adapter XSG-0504000HEU 5 V 4 A + DC jack to terminal block | TinyTronics (006405, 000287) | 2026-11-01 | in stock (Eindhoven warehouse), a few days |
| Servo extension cable 30 cm ×10 | product code KW-2640 (mailbox package, 48 h) | 2026-11-01 | ~2026-11-03 |
| 2020 profile 1 m, 4 corner brackets, 20 M5 drop-in nuts, M5×8/M5×10 bolts | 123-3D | 2026-11-01 | 2026-11-03 |
| Premium EVA foam, high density, 3 mm | Foam Atelier (order 127445) | 2026-11-03 | ships in 1–3 working days, at most 5 when busy |
