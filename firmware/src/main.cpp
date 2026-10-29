// ledwall: thin client for a 64x32 HUB75 panel.
// pigate renders every frame and streams it over TCP; this only blits pixels.
//
// Server -> ESP32:  'F' + 16384 B (128x64 RGB565 LE)  |  'B' + 1 B brightness  |  'P' ping
// ESP32 -> server:  'H' + JSON hello + '\n' on connect
#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <ESP32-HUB75-MatrixPanel-DMA.h>
#include <Fonts/TomThumb.h>
#include "secrets.h"

// Sold as "P2.5 64x32" but the panel is 128x64, 1/32 scan (needs the E line).
#define PANEL_W 128
#define PANEL_H 64
#define FW_VERSION "0.1"

static MatrixPanel_DMA *panel;

static inline uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}

static void setupPanel(bool doubleBuf) {
  // Waveshare devkit wiring (wiki 64x64 diagram); note B is GPIO22, E is GPIO32.
  hub75_cfg_t cfg = {
    .mx_width = PANEL_W,
    .mx_height = PANEL_H,
    .mx_count_width = 1,
    .mx_count_height = 1,
    .gpio = {
      .r1 = 25, .g1 = 26, .b1 = 27, .r2 = 14, .g2 = 12, .b2 = 13,
      .a = 23, .b = 22, .c = 5, .d = 17, .e = 32,
      .lat = 4, .oe = 15, .clk = 16,
    },
    .driver = FM6353,
    // The ISR needs ~690 us to build a 128 px row; at 5 MHz the DMA cycle (~1.5 ms) left too
    // little slack and the left (far) end of the panel showed garbage. 2.5 MHz doubles it.
    .clk_freq = (clk_freq_t)2500000,
    .clk_phase = CLK_POZITIVE,
    .color_depth = COLORx16,
    .double_buff = doubleBuf,
    .double_dma_buff = false,
    .decoder_INT595 = false,
  };
  panel = new MatrixPanel_DMA(cfg);
  if (!panel->begin()) Serial.println("panel: DMA memory allocation failed");
  panel->setBrightness8(255);
  panel->clearScreen();
}

#ifdef PANEL_TEST

static void drawPattern(int n) {
  panel->clearScreen();
  switch (n) {
    case 0: {  // colour bars + RGB ramps
      const uint16_t bars[8] = {
        rgb(255, 255, 255), rgb(255, 255, 0),
        rgb(0, 255, 255),   rgb(0, 255, 0),
        rgb(255, 0, 255),   rgb(255, 0, 0),
        rgb(0, 0, 255),     rgb(0, 0, 0)};
      for (int x = 0; x < PANEL_W; x++)
        for (int y = 0; y < PANEL_H / 2; y++) panel->drawPixel(x, y, bars[x * 8 / PANEL_W]);
      for (int x = 0; x < PANEL_W; x++) {
        uint8_t v = x * 256 / PANEL_W;
        const int h = PANEL_H / 6;  // three ramps in the bottom half
        for (int y = PANEL_H / 2; y < PANEL_H / 2 + h; y++) panel->drawPixel(x, y, rgb(v, 0, 0));
        for (int y = PANEL_H / 2 + h; y < PANEL_H / 2 + 2 * h; y++) panel->drawPixel(x, y, rgb(0, v, 0));
        for (int y = PANEL_H / 2 + 2 * h; y < PANEL_H; y++) panel->drawPixel(x, y, rgb(0, 0, v));
      }
      break;
    }
    case 1: {  // 8 px grid + coloured corners: R top-left, G top-right, B bottom-left, W bottom-right
      uint16_t dim = rgb(60, 60, 60);
      for (int x = 0; x < PANEL_W; x += 8) panel->drawFastVLine(x, 0, PANEL_H, dim);
      for (int y = 0; y < PANEL_H; y += 8) panel->drawFastHLine(0, y, PANEL_W, dim);
      panel->drawRect(0, 0, PANEL_W, PANEL_H, rgb(120, 120, 120));
      panel->fillRect(0, 0, 3, 3, rgb(255, 0, 0));
      panel->fillRect(PANEL_W - 3, 0, 3, 3, rgb(0, 255, 0));
      panel->fillRect(0, PANEL_H - 3, 3, 3, rgb(0, 0, 255));
      panel->fillRect(PANEL_W - 3, PANEL_H - 3, 3, 3, rgb(255, 255, 255));
      break;
    }
    case 2:
      panel->setFont(&TomThumb);
      panel->setTextColor(rgb(255, 160, 0));
      panel->setCursor(2, 8);
      panel->print("LEDWALL TEST");
      panel->setTextColor(rgb(0, 200, 255));
      panel->setCursor(2, 18);
      panel->print("64x32 HUB75");
      panel->setTextColor(rgb(0, 255, 0));
      panel->setCursor(2, 28);
      panel->print("ROW 28 OK");
      break;
    case 3:  // full white: power-supply check
      panel->fillScreen(rgb(255, 255, 255));
      break;
  }
  panel->flipDMABuffer();  // FM6353 holds the frame on-chip: nothing shows until it's sent
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
  panel->setTextColor(rgb(255, 120, 0));
  panel->setCursor(1, 7);
  panel->print("LEDWALL " FW_VERSION);
  panel->setTextColor(rgb(200, 0, 0));
  panel->setCursor(1, 16);
  panel->print(line1);
  panel->setTextColor(rgb(0, 150, 255));
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
  WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
    Serial.printf("wifi disconnected, reason %d\n", info.wifi_sta_disconnected.reason);
  }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("ledwall");
  WiFi.setSleep(false);  // no modem sleep: steadier frame latency
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  // Panel after WiFi: at 128x64 its buffers take ~73 KB of internal RAM, and if they
  // are allocated first the WiFi driver can't get its DMA-capable RX/TX buffers.
  setupPanel(true);
  showStatus("WIFI...", WIFI_SSID);

  ArduinoOTA.setHostname("ledwall");
  ArduinoOTA.setPassword(OTA_PASS);
  ArduinoOTA.setTimeout(10000);  // default 1 s aborts on short WiFi stalls
  ArduinoOTA.onStart([] {
    // Stop the frame stream: unread 16 KB frames fill lwIP's buffers and starve the OTA socket.
    client.stop();
    showStatus("OTA...", "UPDATING");
  });
  Serial.println("ledwall " FW_VERSION);
}

void loop() {
  static bool otaUp = false;
  uint32_t now = millis();
  static uint32_t lastHeap = 0;
  if (now - lastHeap > 60000) {
    lastHeap = now;
    Serial.printf("heap: free %u, internal free %u, dma largest %u, min ever %u, rssi %d\n",
                  ESP.getFreeHeap(), heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                  heap_caps_get_largest_free_block(MALLOC_CAP_DMA), ESP.getMinFreeHeap(), WiFi.RSSI());
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (client.connected()) client.stop();
    if (now - lastStatusDraw > 1000) {
      showStatus("NO WIFI", WIFI_SSID);
      lastStatusDraw = now;
      Serial.printf("wifi status %d\n", WiFi.status());
    }
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
