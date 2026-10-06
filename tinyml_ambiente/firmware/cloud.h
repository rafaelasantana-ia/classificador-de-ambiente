#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include "secrets.h"
#include "cloud_ca.h"

inline void cloudBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  NTP.begin("pool.ntp.org", "time.google.com");
}

// Keep inference independent of network availability. Send the current reading
// every 10 seconds; offline readings are not buffered on this first version.
inline void cloudSend(float temperature, float humidity, int presence, const char* prediction) {
  static unsigned long lastConnect = 0, lastSend = 0;
  const unsigned long now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastConnect >= 30000) {
      lastConnect = now;
      WiFi.disconnect(); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
    return;
  }
  if (now - lastSend < 10000 || time(nullptr) < 1700000000) return;
  lastSend = now;
  HTTPClient http;
  http.setCACert(CLOUD_ROOT_CA);
  http.setTimeout(4000);
  if (!http.begin(INGEST_URL)) return;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-device-token", DEVICE_TOKEN);
  String payload = "{\"temperatura_c\":" + String(temperature,1)
    + ",\"umidade_pct\":" + String(humidity,1)
    + ",\"presenca\":" + String(presence)
    + ",\"classe\":\"" + prediction + "\",\"classifier\":\""
    + (USE_EXACT_RULES ? "rules" : "tree") + "\"}";
  const int code = http.POST(payload);
  Serial.print("CLOUD_HTTP="); Serial.println(code);
  http.end();
}
