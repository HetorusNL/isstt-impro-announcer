// ISSTT IMPRO announcer servo firmware (NUCLEO-F767ZI / NUCLEO-F746ZG).
//
// Safety rule: "Spreken must be released under all circumstances". Layers:
//   1. host releases (finally block)
//   2. software keep-alive watchdog (WATCHDOG ms without any received line)
//   3. per-channel max hold (MAXHOLD ms away from the stored rest angle)
//   4. hardware watchdog (IWDG, ~500 ms) -> reset -> release on boot
// See PROTOCOL.md. No delay() in loop(); everything is millis()-driven.

#include <Arduino.h>
#include <EEPROM.h>
#include <IWatchdog.h>
#include <Servo.h>
#include <utility/stm32_eeprom.h>  // buffered EEPROM API

// ---- configuration --------------------------------------------------------
// Channel -> pin table. Change pins here only.
static const uint8_t NUM_CH = 8;
static const uint8_t PINS[NUM_CH] = {D3, D5, D6, D9, D10, D11, D12, D13};

static const uint32_t BAUD = 115200;
static const uint32_t IWDG_US = 500000;        // hardware watchdog timeout
static const uint32_t IWDG_FLASH_US = 5000000;  // while erasing flash sector
static const uint32_t TICK_MS = 10;
static const size_t MAX_LINE = 64;
static const uint32_t DEFAULT_MAXHOLD_MS = 60000;
static const uint32_t DEFAULT_WATCHDOG_MS = 2000;
static const uint32_t MAX_WATCHDOG_MS = 10000;
static const uint32_t MAX_MAXHOLD_MS = 120000;

// Bump PIN_TABLE_VERSION whenever PINS[] changes meaning; it is folded (with
// NUM_CH) into the stored magic so old rests are never carried over.
static const uint8_t PIN_TABLE_VERSION = 1;
static const uint16_t LAYOUT_VERSION = (uint16_t)((NUM_CH << 8) | PIN_TABLE_VERSION);
static const uint8_t EE_MAGIC = (uint8_t)(0xA1 ^ NUM_CH ^ (PIN_TABLE_VERSION * 17));
static const uint8_t REST_NONE = 0xFF;

// ---- state ----------------------------------------------------------------
static Servo servos[NUM_CH];
static bool attached[NUM_CH];
static uint8_t restDeg[NUM_CH];       // REST_NONE if not stored
static bool away[NUM_CH];             // attached, with rest, and angle != rest
static uint32_t awaySince[NUM_CH];

static uint32_t maxHoldMs = DEFAULT_MAXHOLD_MS;
static uint32_t watchdogMs = DEFAULT_WATCHDOG_MS;
static uint32_t lastLineMs;
static bool watchdogFired;
static uint32_t lastTick;

static char lineBuf[MAX_LINE + 1];
static size_t lineLen;
static bool discarding;

// ---- rest storage ---------------------------------------------------------
#ifdef REST_RAM_ONLY
// NUCLEO-F746ZG: the core's flash data sector (11) does not exist on this
// chip, so rests live in RAM only and never touch flash. They are kept in
// .noinit (not zeroed by startup), guarded by a magic word, so they survive an
// IWDG/soft reset but not a power cycle.
// Each rest is also stored complemented; any mismatch invalidates all rests.
static const uint32_t RAM_MAGIC = 0x52455300u ^ LAYOUT_VERSION;  // "RES" + layout
static uint32_t ramMagic __attribute__((section(".noinit")));
static uint8_t ramRest[NUM_CH] __attribute__((section(".noinit")));
static uint8_t ramRestInv[NUM_CH] __attribute__((section(".noinit")));

static bool ramValid() {
  if (ramMagic != RAM_MAGIC) return false;
  for (uint8_t i = 0; i < NUM_CH; i++) {
    if ((uint8_t)~ramRest[i] != ramRestInv[i]) return false;
    if (ramRest[i] > 180 && ramRest[i] != REST_NONE) return false;
  }
  return true;
}

static void loadRest() {
  if (!ramValid()) {
    ramMagic = RAM_MAGIC;
    for (uint8_t i = 0; i < NUM_CH; i++) {
      ramRest[i] = REST_NONE;
      ramRestInv[i] = (uint8_t)~REST_NONE;
    }
  }
  for (uint8_t i = 0; i < NUM_CH; i++) restDeg[i] = ramRest[i];
}

static bool storeRest(uint8_t ch, uint8_t deg) {
  ramRest[ch] = deg;
  ramRestInv[ch] = (uint8_t)~deg;
  restDeg[ch] = deg;
  return true;
}
#else
// EEPROM layout: [0] magic/version, [1..8] rest angle per channel (0xFF=none)
static void loadRest() {
  eeprom_buffer_fill();
  bool valid = eeprom_buffered_read_byte(0) == EE_MAGIC;
  for (uint8_t i = 0; i < NUM_CH; i++) {
    uint8_t v = valid ? eeprom_buffered_read_byte(1 + i) : REST_NONE;
    restDeg[i] = (v <= 180) ? v : REST_NONE;
  }
}

// Writes only if the stored value differs: flash sector erase is slow.
// Returns false if the flash readback does not match (RAM value is kept).
static bool flashDirty;  // last readback mismatched: force a rewrite

static bool storeRest(uint8_t ch, uint8_t deg) {
  bool dirty = flashDirty;
  if (eeprom_buffered_read_byte(0) != EE_MAGIC) {
    eeprom_buffered_write_byte(0, EE_MAGIC);
    for (uint8_t i = 0; i < NUM_CH; i++) eeprom_buffered_write_byte(1 + i, REST_NONE);
    dirty = true;
  }
  if (eeprom_buffered_read_byte(1 + ch) != deg) {
    eeprom_buffered_write_byte(1 + ch, deg);
    dirty = true;
  }
  restDeg[ch] = deg;
  if (!dirty) return true;
  // Sector erase can take > 500 ms: relax IWDG just for the flush.
  IWatchdog.set(IWDG_FLASH_US);
  eeprom_buffer_flush();
  IWatchdog.set(IWDG_US);
  IWatchdog.reload();
  // Verify: re-read flash and compare with what we meant to store.
  uint8_t want[1 + NUM_CH];
  for (uint8_t i = 0; i < 1 + NUM_CH; i++) want[i] = eeprom_buffered_read_byte(i);
#if defined(__DCACHE_PRESENT) && __DCACHE_PRESENT
  // The core enables the D-cache and the flash HAL does no cache maintenance:
  // drop stale lines so the readback sees real flash. Address and size are
  // 32-byte aligned (FLASH_BASE_ADDRESS is a sector start).
  SCB_InvalidateDCache_by_Addr((uint32_t*)FLASH_BASE_ADDRESS,
                               (int32_t)((E2END + 1 + 31) & ~31u));
#endif
  eeprom_buffer_fill();  // buffer now holds the real flash contents
  for (uint8_t i = 0; i < 1 + NUM_CH; i++) {
    if (eeprom_buffered_read_byte(i) != want[i]) {
      // Rebuild the whole buffer from RAM so the next REST rewrites every
      // channel (a bad magic byte would otherwise wipe the other rests).
      eeprom_buffered_write_byte(0, EE_MAGIC);
      for (uint8_t k = 0; k < NUM_CH; k++) eeprom_buffered_write_byte(1 + k, restDeg[k]);
      flashDirty = true;
      return false;
    }
  }
  flashDirty = false;
  return true;
}
#endif

// ---- servo helpers --------------------------------------------------------
static void moveTo(uint8_t ch, uint8_t deg) {
  if (!attached[ch]) {
    servos[ch].attach(PINS[ch], deg);  // first frame already at deg
    attached[ch] = true;
  } else {
    servos[ch].write(deg);
  }
  bool nowAway = restDeg[ch] != REST_NONE && deg != restDeg[ch];
  if (nowAway && !away[ch]) awaySince[ch] = millis();
  away[ch] = nowAway;
}

// Returns false if the channel has no stored rest (never driven).
static bool release(uint8_t ch) {
  if (restDeg[ch] == REST_NONE) return false;
  moveTo(ch, restDeg[ch]);
  return true;
}

static void releaseAll() {
  for (uint8_t i = 0; i < NUM_CH; i++) release(i);
}

// ---- command handling -----------------------------------------------------
static bool parseUInt(const char* s, uint32_t& out) {
  if (!s || !*s) return false;
  uint32_t v = 0;
  for (; *s; s++) {
    if (*s < '0' || *s > '9') return false;
    v = v * 10 + (*s - '0');
    if (v > 100000000UL) return false;
  }
  out = v;
  return true;
}

static bool parseChannel(const char* s, uint8_t& ch) {
  uint32_t v;
  if (!parseUInt(s, v) || v >= NUM_CH) return false;
  ch = (uint8_t)v;
  return true;
}

static bool parseDeg(const char* s, uint8_t& deg) {
  uint32_t v;
  if (!parseUInt(s, v) || v > 180) return false;
  deg = (uint8_t)v;
  return true;
}

static void handleLine(char* line) {
  char* tok[4];
  size_t n = 0;
  for (char* p = strtok(line, " \t"); p && n < 4; p = strtok(NULL, " \t")) {
    for (char* c = p; *c; c++) *c = toupper((unsigned char)*c);
    tok[n++] = p;
  }
  if (n == 0) { Serial.println(F("ERR empty")); return; }
  const char* cmd = tok[0];
  uint8_t ch, deg;
  uint32_t ms;

  if (!strcmp(cmd, "PING")) {
    if (n != 1) { Serial.println(F("ERR args")); return; }
    Serial.println(F("OK PONG"));
  } else if (!strcmp(cmd, "REST")) {
    if (n != 3) { Serial.println(F("ERR args")); return; }
    if (!parseChannel(tok[1], ch)) { Serial.println(F("ERR channel")); return; }
    if (!parseDeg(tok[2], deg)) { Serial.println(F("ERR degrees")); return; }
    bool stored = storeRest(ch, deg);
    moveTo(ch, deg);
    Serial.println(stored ? F("OK") : F("ERR flash"));
  } else if (!strcmp(cmd, "ANGLE")) {
    if (n != 3) { Serial.println(F("ERR args")); return; }
    if (!parseChannel(tok[1], ch)) { Serial.println(F("ERR channel")); return; }
    if (!parseDeg(tok[2], deg)) { Serial.println(F("ERR degrees")); return; }
    // No stored rest means no failsafe could ever release it: refuse.
    if (restDeg[ch] == REST_NONE) { Serial.println(F("ERR no rest")); return; }
    moveTo(ch, deg);
    Serial.println(F("OK"));
  } else if (!strcmp(cmd, "RELEASE")) {
    if (n != 2) { Serial.println(F("ERR args")); return; }
    if (!strcmp(tok[1], "ALL")) {
      releaseAll();
      Serial.println(F("OK"));
    } else if (!parseChannel(tok[1], ch)) {
      Serial.println(F("ERR channel"));
    } else if (!release(ch)) {
      Serial.println(F("ERR no rest"));
    } else {
      Serial.println(F("OK"));
    }
  } else if (!strcmp(cmd, "MAXHOLD") || !strcmp(cmd, "WATCHDOG")) {
    if (n != 2) { Serial.println(F("ERR args")); return; }
    if (!parseUInt(tok[1], ms)) { Serial.println(F("ERR value")); return; }
    uint32_t cap = (cmd[0] == 'M') ? MAX_MAXHOLD_MS : MAX_WATCHDOG_MS;
    if (ms < 1 || ms > cap) { Serial.println(F("ERR range")); return; }
    if (cmd[0] == 'M') maxHoldMs = ms; else watchdogMs = ms;
    Serial.println(F("OK"));
  } else {
    Serial.println(F("ERR unknown command"));
  }
}

static void pollSerial() {
  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c < 0) break;
    if (c == '\r') continue;
    if (c == '\n') {
      lastLineMs = millis();  // any line, valid or not, is host activity
      watchdogFired = false;
      if (discarding) {
        Serial.println(F("ERR too long"));
        discarding = false;
      } else {
        lineBuf[lineLen] = 0;
        handleLine(lineBuf);
      }
      lineLen = 0;
      continue;
    }
    if (discarding) continue;
    if (lineLen >= MAX_LINE) { discarding = true; lineLen = 0; continue; }
    lineBuf[lineLen++] = (char)c;
  }
}

// ---- failsafes ------------------------------------------------------------
static void checkFailsafes() {
  uint32_t now = millis();
  if (!watchdogFired && (uint32_t)(now - lastLineMs) >= watchdogMs) {
    watchdogFired = true;
    releaseAll();
    Serial.println(F("EVT WATCHDOG"));
  }
  for (uint8_t i = 0; i < NUM_CH; i++) {
    if (away[i] && (uint32_t)(now - awaySince[i]) >= maxHoldMs) {
      release(i);
      Serial.print(F("EVT MAXHOLD "));
      Serial.println(i);
    }
  }
}

void setup() {
  bool iwdgReset = IWatchdog.isReset(true);
  Serial.begin(BAUD);
  loadRest();
  // Release on boot: only channels with a stored rest are attached/driven.
  releaseAll();
  lastLineMs = millis();
  lastTick = lastLineMs;
  IWatchdog.begin(IWDG_US);
  Serial.println(iwdgReset ? F("EVT BOOT IWDG") : F("EVT BOOT"));
}

void loop() {
  IWatchdog.reload();
  pollSerial();
  uint32_t now = millis();
  if ((uint32_t)(now - lastTick) >= TICK_MS) {
    lastTick = now;
    checkFailsafes();
  }
}
