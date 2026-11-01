# Servo firmware protocol (NUCLEO-F767ZI / NUCLEO-F746ZG)

Build: `pio run -d firmware -e nucleo_f767zi` (or `-e nucleo_f746zg`); flash with `pio run -d firmware -e <env> -t upload`.

## Serial

- `Serial` at 115200 baud, 8N1. In the STM32duino core both Nucleo-144 variants
  (`variant_NUCLEO_F767ZI.h`, `variant_NUCLEO_F7x6ZG.h`) set `SERIAL_UART_INSTANCE 3`
  (USART3, PD8/PD9), which is wired to the ST-Link virtual COM port (`/dev/ttyACM0`).
- One command per line, terminated by `\n`. `\r` is ignored. Commands are case-insensitive.
- Lines longer than 64 characters are discarded and answered with `ERR too long`.
- Every received line, valid or not, counts as host activity for the watchdog.

## Commands

| Command | Reply | Effect |
|---|---|---|
| `PING` | `OK PONG` | Keep-alive. |
| `REST <ch> <deg>` | `OK` | Store rest angle (EEPROM, only if changed), attach channel, move to rest. |
| `ANGLE <ch> <deg>` | `OK` | Move servo (attaches if needed). |
| `RELEASE <ch>` | `OK` / `ERR no rest` | Move channel to its stored rest. |
| `RELEASE ALL` | `OK` | Move every channel with a stored rest to rest. |
| `MAXHOLD <ms>` | `OK` | Max time away from rest (default 60000, 1..3600000). |
| `WATCHDOG <ms>` | `OK` | Keep-alive timeout (default 2000, 1..3600000). |

Channels are 0-7, degrees 0-180. Errors: `ERR args`, `ERR channel`, `ERR degrees`, `ERR value`,
`ERR unknown command`, `ERR empty`, `ERR no rest`, `ERR too long`.

## Events (asynchronous lines)

- `EVT BOOT`: sent once after release-on-boot. `EVT BOOT IWDG` if the reset was caused by the hardware watchdog.
- `EVT WATCHDOG`: no line received for `WATCHDOG` ms. All channels with a stored rest go to rest.
  Fires once; re-armed by the next received line. Active from boot.
- `EVT MAXHOLD <ch>`: channel `<ch>` was away from its stored rest angle for longer than `MAXHOLD` ms
  (timed from when it left rest; further `ANGLE`s do not reset it). It is moved to rest.

A channel with no stored rest is never attached at boot and never driven by any failsafe.

## Failsafe layers

1. Software keep-alive watchdog (above).
2. Per-channel max hold (above).
3. Hardware watchdog (IWDG, about 500 ms), refreshed in `loop()`. If the firmware hangs the MCU resets
   and release-on-boot puts every servo with a stored rest back at rest.

## EEPROM

STM32 EEPROM emulation uses flash; a write erases a whole sector, which is slow (can take well over
500 ms, up to a few seconds on the F7). Layout: byte 0 magic `0xA1`, bytes 1-8 rest angle per channel
(`0xFF` = none). The buffered API (`eeprom_buffer_fill`/`eeprom_buffer_flush`) is used and a flush happens
only when a value actually changes, so the host's `REST` for every actuator on each connect is normally
free. A changing `REST` blocks the main loop during the erase (servos hold position, serial input
buffers in the UART RX interrupt, but a long erase may overrun the RX buffer, so do not send further
commands until `OK`). The IWDG timeout is relaxed to 5 s just around the flush.

## Pin table (one table in `src/main.cpp`, `PINS[]`)

| Channel | Pin |
|---|---|
| 0 | D3 |
| 1 | D5 |
| 2 | D6 |
| 3 | D9 |
| 4 | D10 |
| 5 | D11 |
| 6 | D12 |
| 7 | D13 |

The core's Servo library uses a software timer (TIM7), so it can drive any of these digital pins.

## Power notes

- Run the board from the external 5 V rail via **E5V** with jumper **JP3 set to E5V**. This keeps the
  watchdog running when the laptop USB is unplugged.
- Servo rail ground **must be common** with the board GND.
- Put a **1000 uF** electrolytic capacitor across the servo supply rail (near the servos) to absorb
  current spikes that would otherwise brown out the MCU.

## Bench test (manual, left for Tim)

`picocom -b 115200 /dev/ttyACM0`, one servo on channel 0.

| Step | Expected | Result |
|---|---|---|
| `REST 0 90` | `OK`, servo at 90 | |
| `ANGLE 0 60` | `OK`, servo moves | |
| Stop typing for 2 s | `EVT WATCHDOG`, servo back at 90 | |
| `MAXHOLD 5000`, `ANGLE 0 60`, keep sending `PING` | `EVT MAXHOLD 0` after about 5 s, servo at 90 | |
| Power-cycle | `EVT BOOT`, servo at 90 | |
| Board on E5V: `ANGLE 0 60`, pull USB | Back at 90 within 2 s | |
| `REST 0 90` again (unchanged) | `OK` immediately (no flash write) | |
| Send a 100-char line | `ERR too long` | |
