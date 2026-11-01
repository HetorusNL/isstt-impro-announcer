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
static const uint32_t MAX_TIMER_MS = 3600000UL;

// EEPROM layout: [0] magic/version, [1..8] rest angle per channel (0xFF=none)
static const uint8_t EE_MAGIC = 0xA1;
static const uint8_t REST_NONE = 0xFF;

// ---- state ----------------------------------------------------------------
static Servo servos[NUM_CH];
static bool attached[NUM_CH];
static uint8_t restDeg[NUM_CH];       // REST_NONE if not stored
static uint8_t curDeg[NUM_CH];
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

// ---- EEPROM ---------------------------------------------------------------
static void loadRest() {
  eeprom_buffer_fill();
  bool valid = eeprom_buffered_read_byte(0) == EE_MAGIC;
  for (uint8_t i = 0; i < NUM_CH; i++) {
    uint8_t v = valid ? eeprom_buffered_read_byte(1 + i) : REST_NONE;
    restDeg[i] = (v <= 180) ? v : REST_NONE;
  }
}

// Writes only if the stored value differs: flash sector erase is slow.
static void storeRest(uint8_t ch, uint8_t deg) {
  bool dirty = false;
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
  if (!dirty) return;
  // Sector erase can take > 500 ms: relax IWDG just for the flush.
  IWatchdog.set(IWDG_FLASH_US);
  eeprom_buffer_flush();
  IWatchdog.set(IWDG_US);
  IWatchdog.reload();
}

// ---- servo helpers --------------------------------------------------------
static void moveTo(uint8_t ch, uint8_t deg) {
  if (!attached[ch]) {
    servos[ch].attach(PINS[ch]);
    attached[ch] = true;
  }
  servos[ch].write(deg);
  curDeg[ch] = deg;
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
    storeRest(ch, deg);
    moveTo(ch, deg);
    Serial.println(F("OK"));
  } else if (!strcmp(cmd, "ANGLE")) {
    if (n != 3) { Serial.println(F("ERR args")); return; }
    if (!parseChannel(tok[1], ch)) { Serial.println(F("ERR channel")); return; }
    if (!parseDeg(tok[2], deg)) { Serial.println(F("ERR degrees")); return; }
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
    if (!parseUInt(tok[1], ms) || ms < 1 || ms > MAX_TIMER_MS) {
      Serial.println(F("ERR value"));
      return;
    }
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
