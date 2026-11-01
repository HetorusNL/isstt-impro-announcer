# Bill of materials

Shipping takes 2-4 weeks, so order early.

| Qty | Part | Reason |
|-----|------|--------|
| 10 | MG90S metal-gear micro servos — **ordered** | 4 needed (SC1, SC2, SC3, SPREKEN); 6 spare or for extra buttons (firmware drives up to 8 channels) |
| 1 | 5 V, ≥ 4 A regulated wall adapter with barrel jack (closed unit, e.g. Mean Well GST25E05; no open-frame mains supply) | Powers the servos and the Nucleo (E5V). 4 servos move one at a time in normal use; worst case all 4 return to rest at once (~3–4 A peak, buffered by the 1000 µF cap). A closed adapter avoids exposed mains terminals at the venue. Budget more if running all 8 servos with simultaneous moves |
| 1 | 5.5/2.1 mm female DC jack to screw-terminal adapter | Feeds the servo rail and the Nucleo E5V/GND from the adapter (candidate adapter: TinyTronics XSG-0504000HEU, 5.0 V 4 A, 5.5/2.1 mm). Check the voltage under load stays within 4.75–5.25 V |
| 10 | Servo extension leads, 30 cm — **ordered** | Reach from the controller to the servos on the desk |
| 1 set | Jumper wires (Dupont), perfboard, pin headers — **on hand** | Servo rail on perfboard: a 3-pin header per servo (GND / +5 V / signal), signal pins to the Nucleo header by jumper. Tape or hot-glue connections for transport |
| 1 | 1000 uF electrolytic capacitor, ≥ 10 V (16 V preferred) — **on hand** | Across the servo rail (+5 V / GND, mind polarity) close to the servo headers, to absorb current spikes |
| 1 | Earson ER-151 speaker (Tim's own; triangular, ~150×56×56 mm, 2× 1.5" drivers) on the laptop's 3.5 mm output — **on hand** | Plays the announcement at the paging desk mic. No USB sound card: previews also come out of this speaker, which is harmless because the desk mic is only live while Spreken is held. Battery lasts ~5 h, so power it from a separate USB wall charger (not the laptop) during the day; check for hum and for auto power-off in AUX mode |
| 2 | 20x20 aluminium extrusion, 400 mm | Stiff backbone; the printed parts clip onto it |
| 1 set | T-nuts and M3/M4 bolts | Mount the extrusion and printed parts |
| 1 | EVA foam or rubber sheet | Clamp pads |

## Order status / expected delivery

| Part | Supplier | Ordered on | Expected delivery |
|------|----------|------------|-------------------|
| MG90S servos ×10 | TinyTronics (000263) | 2026-11-01 | TBD |
| Power adapter XSG-0504000HEU 5 V 4 A + DC jack to terminal block | TinyTronics (006405, 000287) | 2026-11-01 | TBD |
| Servo extension cable 30 cm ×10 | product code KW-2640 (mailbox package, 48 h) | 2026-11-01 | ~2026-11-03 |
| Extrusion, T-nuts, bolts | **not ordered yet** | | |
| EVA foam / rubber sheet | **not ordered yet** | | |
