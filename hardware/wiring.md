# Wiring

Power goes one way: the 5 V 4 A adapter feeds a servo rail on perfboard, and the rail feeds the servos and the Nucleo. The speaker has nothing to do with this rail.

## Diagram

```
 mains
   |
 [5 V 4 A adapter]
   |  5.5/2.1 mm barrel
 [DC jack to terminal block]
   |  + and -
   v
 +5 V ===+=========+=========+=========+======> Nucleo E5V (JP3 on E5V)
         |         |         |         |
       (+)|        |         |         |
     [1000 uF]   [CH0]     [CH1] ... [CH7]    3-pin header per servo:
       (-)|        |         |         |      GND / +5 V / signal
         |         |         |         |
  GND ===+=========+=========+=========+======> Nucleo GND

  Nucleo D3  ---- signal CH0 ---- extension lead ---- servo SC1
  Nucleo D5  ---- signal CH1 ---- extension lead ---- servo SC2
  Nucleo D6  ---- signal CH2 ---- extension lead ---- servo SC3
  Nucleo D9  ---- signal CH3 ---- extension lead ---- servo SPREKEN
  Nucleo D10 ---- signal CH4 (spare)
  Nucleo D11 ---- signal CH5 (spare)
  Nucleo D12 ---- signal CH6 (spare)
  Nucleo D13 ---- signal CH7 (spare)

  Laptop USB ---- Nucleo ST-Link USB (serial, /dev/ttyACM0)

  Laptop 3.5 mm jack ---- Earson ER-151 AUX in
  USB wall charger   ---- Earson ER-151 USB power (separate from the laptop)
```

## Power

1. The adapter plugs into the DC jack to terminal block. Check `+` and `-` on the block with a meter before connecting anything else.
2. The block feeds the perfboard servo rail. The rail carries up to 4 A, so use short, thick wire for `+5 V` and `GND`, not a Dupont jumper.
3. Put the **1000 uF, at least 10 V** capacitor across `+5 V` and `GND`, close to the servo headers. **Mind the polarity**: the stripe on the can is the negative lead and goes to `GND`.
4. Each servo gets a 3-pin header on the rail: `GND` / `+5 V` / signal.
5. Run `+5 V` to the Nucleo **E5V** pin and `GND` to a Nucleo **GND** pin, and set **JP3 to E5V**. The board then keeps running, and its watchdog keeps working, if the laptop USB is unplugged.
6. Ground is common: the rail, the Nucleo and the servos all share one `GND`. Without it the signal pulses have no reference.

Power up in this order: rail first, then the laptop USB. Check the Nucleo-144 manual (UM1974) on external power if the ST-Link does not come up.

At power-on the firmware drives every servo to the rest in its flash, before the host sends any config. Keep the plungers out until one connect with the final rest has happened: see "Last bench step" in the [README](../README.md#last-bench-step).

The rail also powers the Nucleo, so losing the adapter during a hold stops every failsafe at once. That is an accepted risk: see section 0.5 of the [checklist](../docs/onsite-checklist.md).

## Signal pins

From the pin table in `firmware/PROTOCOL.md`. The button mapping is the default in `config.example.toml`.

| Channel | Nucleo pin | Default button |
|---|---|---|
| 0 | D3 | SC1 |
| 1 | D5 | SC2 |
| 2 | D6 | SC3 |
| 3 | D9 | SPREKEN |
| 4 | D10 | spare |
| 5 | D11 | spare |
| 6 | D12 | spare |
| 7 | D13 | spare |

Run a jumper from each Nucleo pin to the signal pin of that channel's header. Tape or hot-glue the jumpers for transport. Label each lead with its channel number at both ends.

## Servo leads

Servos connect to the rail through the 30 cm extension leads.

| Wire colour | Function | Header pin |
|---|---|---|
| Brown | GND | GND |
| Red | +5 V | +5 V |
| Orange | Signal | signal |

**Routing rule: never run a lead across or above the two covered buttons** (*Ontruimingsalarm*, *Koppel ruimtes*). The hand volume above them stays free. Run leads along the rail and away from the covers, and fix them so they cannot sag into that volume.

## Speaker

There is no USB sound card. The Earson ER-151 takes audio from the laptop's 3.5 mm jack, and its USB power from a separate wall charger, because its battery lasts about 5 hours. Don't power it from the laptop or from the servo rail. Listen for hum, and check that it does not power off by itself in AUX mode.

## Pre-power checklist

Do this with the servos unplugged, then again with them plugged in.

- [ ] **Polarity:** `+5 V` and `GND` on the terminal block match the rail, the capacitor stripe is on `GND`, and brown is on `GND` on every header.
- [ ] **No short:** with the adapter unplugged, the meter shows no short between `+5 V` and `GND`. It will rise slowly while the capacitor charges from the meter.
- [ ] **JP3 is on E5V**, and `GND` from the rail reaches the Nucleo.
- [ ] **Adapter voltage under load:** measure at the rail with all four servos moving. It must stay within **4.75 to 5.25 V**.
- [ ] Each channel moves the servo on the button its label says (`REST` and `ANGLE` from a terminal, see `firmware/PROTOCOL.md`), before any servo module is on the desk.
