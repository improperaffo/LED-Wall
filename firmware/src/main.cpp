// ledwall: thin client for a 64x32 HUB75 panel.
// pigate renders every frame and streams it over TCP; this only blits pixels.
//
// Server -> ESP32:  'F' + 4096 B (64x32 RGB565 LE)  |  'B' + 1 B brightness  |  'P' ping
// ESP32 -> server:  'H' + JSON hello + '\n' on connect
#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <Fonts/TomThumb.h>
#include "secrets.h"

#define PANEL_W 64
#define PANEL_H 32
#define FW_VERSION "0.1"

static MatrixPanel_I2S_DMA *panel;

static void setupPanel(bool doubleBuf) {
  // Default pin map == Waveshare ESP32 wiring:
  // R1 25 G1 26 B1 27 R2 14 G2 12 B2 13 A 23 B 19 C 5 D 17 LAT 4 OE 15 CLK 16
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1);
  cfg.double_buff = doubleBuf;
  panel = new MatrixPanel_I2S_DMA(cfg);
  panel->begin();
  panel->setBrightness8(40);
  panel->clearScreen();
}

#ifdef PANEL_TEST

static void drawPattern(int n) {
  panel->clearScreen();
  switch (n) {
    case 0: {  // colour bars + RGB ramps
      const uint16_t bars[8] = {
        panel->color565(255, 255, 255), panel->color565(255, 255, 0),
        panel->color565(0, 255, 255),   panel->color565(0, 255, 0),
        panel->color565(255, 0, 255),   panel->color565(255, 0, 0),
        panel->color565(0, 0, 255),     panel->color565(0, 0, 0)};
      for (int x = 0; x < PANEL_W; x++)
        for (int y = 0; y < 16; y++) panel->drawPixel(x, y, bars[x / 8]);
      for (int x = 0; x < PANEL_W; x++) {
        uint8_t v = x * 4;
        for (int y = 16; y < 21; y++) panel->drawPixel(x, y, panel->color565(v, 0, 0));
        for (int y = 21; y < 26; y++) panel->drawPixel(x, y, panel->color565(0, v, 0));
        for (int y = 26; y < 32; y++) panel->drawPixel(x, y, panel->color565(0, 0, v));
      }
      break;
    }
    case 1: {  // 8 px grid + coloured corners: R top-left, G top-right, B bottom-left, W bottom-right
      uint16_t dim = panel->color565(60, 60, 60);
      for (int x = 0; x < PANEL_W; x += 8) panel->drawFastVLine(x, 0, PANEL_H, dim);
      for (int y = 0; y < PANEL_H; y += 8) panel->drawFastHLine(0, y, PANEL_W, dim);
      panel->drawRect(0, 0, PANEL_W, PANEL_H, panel->color565(120, 120, 120));
      panel->fillRect(0, 0, 3, 3, panel->color565(255, 0, 0));
      panel->fillRect(61, 0, 3, 3, panel->color565(0, 255, 0));
      panel->fillRect(0, 29, 3, 3, panel->color565(0, 0, 255));
      panel->fillRect(61, 29, 3, 3, panel->color565(255, 255, 255));
      break;
    }
    case 2:
      panel->setFont(&TomThumb);
      panel->setTextColor(panel->color565(255, 160, 0));
      panel->setCursor(2, 8);
      panel->print("LEDWALL TEST");
      panel->setTextColor(panel->color565(0, 200, 255));
      panel->setCursor(2, 18);
      panel->print("64x32 HUB75");
      panel->setTextColor(panel->color565(0, 255, 0));
      panel->setCursor(2, 28);
      panel->print("ROW 28 OK");
      break;
    case 3:  // full white: power-supply check
      panel->fillScreen(panel->color565(255, 255, 255));
      break;
  }
}

void setup() {
  Serial.begin(115200);
  setupPanel(false);
  Serial.println("panel test");
}

void loop() {
  static int n = 0;
  Serial.printf("pattern %d\n", n);
  drawPattern(n);
  n = (n + 1) % 4;
  delay(3000);
}

#else  // normal firmware

static WiFiClient client;
static uint8_t frame[PANEL_W * PANEL_H * 2];
static size_t frameGot = 0;
enum RxState { RX_TYPE, RX_FRAME, RX_BRIGHT };
static RxState rxState = RX_TYPE;
static uint32_t lastRx = 0;          // millis of last byte from server
static uint32_t lastConnectTry = 0;
static uint32_t lastStatusDraw = 0;
static bool haveFrame = false;       // server frame is on screen

static void showFrame() {
  for (int y = 0; y < PANEL_H; y++)
    for (int x = 0; x < PANEL_W; x++) {
      size_t i = (y * PANEL_W + x) * 2;
      panel->drawPixel(x, y, (uint16_t)(frame[i] | (frame[i + 1] << 8)));
    }
  panel->flipDMABuffer();
  haveFrame = true;
}

// Shown when there is no server: who we are and what we're waiting for.
static void showStatus(const char *line1, const char *line2) {
  panel->clearScreen();
  panel->setFont(&TomThumb);
  panel->setTextColor(panel->color565(255, 120, 0));
  panel->setCursor(1, 7);
  panel->print("LEDWALL " FW_VERSION);
  panel->setTextColor(panel->color565(200, 0, 0));
  panel->setCursor(1, 16);
  panel->print(line1);
  panel->setTextColor(panel->color565(0, 150, 255));
  panel->setCursor(1, 25);
  panel->print(line2);
  panel->flipDMABuffer();
  haveFrame = false;
}

static void sendHello() {
  char buf[160];
  snprintf(buf, sizeof buf,
           "H{\"fw\":\"" FW_VERSION "\",\"ip\":\"%s\",\"rssi\":%d,\"mac\":\"%s\"}\n",
           WiFi.localIP().toString().c_str(), WiFi.RSSI(), WiFi.macAddress().c_str());
  client.print(buf);
}

static void pumpServer() {
  while (client.available()) {
    lastRx = millis();
    switch (rxState) {
      case RX_TYPE: {
        int c = client.read();
        if (c == 'F') { rxState = RX_FRAME; frameGot = 0; }
        else if (c == 'B') rxState = RX_BRIGHT;
        // 'P' (ping) and anything unknown: nothing to do
        break;
      }
      case RX_FRAME: {
        int n = client.read(frame + frameGot, sizeof frame - frameGot);
        if (n > 0) frameGot += n;
        if (frameGot == sizeof frame) { showFrame(); rxState = RX_TYPE; }
        break;
      }
      case RX_BRIGHT: {
        int b = client.read();
        if (b >= 0) panel->setBrightness8(b);
        rxState = RX_TYPE;
        break;
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  setupPanel(true);
  showStatus("WIFI...", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.setHostname("ledwall");
  WiFi.setSleep(false);  // no modem sleep: steadier frame latency
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  ArduinoOTA.setHostname("ledwall");
  ArduinoOTA.setPassword(OTA_PASS);
  ArduinoOTA.onStart([] { showStatus("OTA...", "UPDATING"); });
  Serial.println("ledwall " FW_VERSION);
}

void loop() {
  static bool otaUp = false;
  uint32_t now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    if (client.connected()) client.stop();
    if (now - lastStatusDraw > 1000) { showStatus("NO WIFI", WIFI_SSID); lastStatusDraw = now; }
    delay(50);
    return;
  }
  if (!otaUp) {
    ArduinoOTA.begin();
    otaUp = true;
    Serial.printf("wifi up: %s rssi %d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }
  ArduinoOTA.handle();

  if (client.connected() && now - lastRx > 10000) {
    Serial.println("server silent >10s, reconnecting");
    client.stop();
  }

  if (!client.connected()) {
    if (now - lastConnectTry > 2000) {
      lastConnectTry = now;
      Serial.printf("connecting %s:%d\n", SERVER_HOST, SERVER_PORT);
      if (client.connect(SERVER_HOST, SERVER_PORT, 1500)) {
        client.setNoDelay(true);
        rxState = RX_TYPE;
        lastRx = millis();
        sendHello();
        Serial.println("server connected");
      }
    }
    if (now - lastStatusDraw > 1000) {
      showStatus("NO SERVER", WiFi.localIP().toString().c_str());
      lastStatusDraw = now;
    }
    delay(10);
    return;
  }

  pumpServer();
  delay(1);
}

#endif
