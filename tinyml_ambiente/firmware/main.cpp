#include <Arduino.h>
#include <DHT.h>
#include <math.h>
#include <string.h>
#include "../models/model_data.h"
#include "../models/rules_data.h"
#include "../models/regressor_data.h"

// 0: árvore TinyML; 1: reprodução exata das regras, alternativa para operação.
#ifndef USE_EXACT_RULES
#define USE_EXACT_RULES 0
#endif

#if ENABLE_CLOUD
#include "cloud.h"
#endif

// Diagnostico temporario: compile com -DDHT_DIAGNOSTICS=0 para desativar.
#ifndef DHT_DIAGNOSTICS
#define DHT_DIAGNOSTICS 1
#endif

#ifndef BENCHMARK_MODE
#define BENCHMARK_MODE 0
#endif

// GPIO externos: ajuste para sua ligação real. Numeração GPIO, não pino físico.
constexpr int DHT_PIN = 2, IR_PIN = 14, LED_PIN = 16, BUZZER_PIN = 17;
DHT dht(DHT_PIN, DHT11);

constexpr uint8_t HISTORY_SIZE = 10;
struct SensorHistory {
  float temperature[HISTORY_SIZE]{};
  float humidity[HISTORY_SIZE]{};
  float presence[HISTORY_SIZE]{};
  uint8_t size = 0;
  uint8_t next = 0;

  void push(float temperature_value, float humidity_value, float presence_value) {
    temperature[next] = temperature_value;
    humidity[next] = humidity_value;
    presence[next] = presence_value;
    next = (next + 1) % HISTORY_SIZE;
    if (size < HISTORY_SIZE) size++;
  }
  float mean(const float* values) const {
    float total = 0;
    for (uint8_t i = 0; i < size; i++) total += values[i];
    return size ? total / size : 0;
  }
  float trend(const float* values) const {
    if (size < 2) return 0;
    const uint8_t last = (next + HISTORY_SIZE - 1) % HISTORY_SIZE;
    const uint8_t first = size == HISTORY_SIZE ? next : 0;
    return values[last] - values[first];
  }
  float presenceCount() const {
    float total = 0;
    for (uint8_t i = 0; i < size; i++) total += presence[i] > 0.5f ? 1.0f : 0.0f;
    return total;
  }
};

SensorHistory history;

bool outOfDomain(float temperature, float humidity) {
  // Min/max observados no dataset usado para gerar o firmware.
  return temperature < 20.0f || temperature > 39.8f || humidity < 40.0f || humidity > 98.0f;
}

int classSeverity(int prediction) {
  if (prediction < 0) return 0;
  if (strcmp(MODEL_CLASSES[prediction], "critico") == 0) return 3;
  if (strcmp(MODEL_CLASSES[prediction], "alerta") == 0) return 2;
  if (strcmp(MODEL_CLASSES[prediction], "presenca") == 0) return 1;
  return 0;
}

void printFloatJson(float value) { Serial.print(value, 2); }

void setup() {
  Serial.begin(115200);
  dht.begin();
  pinMode(IR_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
#if ENABLE_CLOUD
  cloudBegin();
#endif
  // Aguarda estabilizacao do DHT11 antes da primeira leitura.
  delay(2000);
}
void loop() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
#if DHT_DIAGNOSTICS
  Serial.print("Temp raw: ");
  Serial.println(temperature, 1);
  Serial.print("Humidity raw: ");
  Serial.println(humidity, 1);
#endif
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT11_READ_ERROR");
    delay(2000);
    return;
  }
  int ir = digitalRead(IR_PIN);
  float presence = (ir == LOW) ? 1.0f : 0.0f;
  history.push(temperature, humidity, presence);
  const bool ood = outOfDomain(temperature, humidity);
  const unsigned long inference_start = micros();
  // OOD nunca confia no modelo: regras determinísticas são o fallback seguro.
  int prediction = (ood || USE_EXACT_RULES) ? rules_predict(temperature, humidity, presence)
                                            : model_predict(temperature, humidity, presence);
  const unsigned long inference_us = micros() - inference_start;
  float regression_features[REGRESSION_FEATURE_COUNT] = {
    temperature, humidity, presence,
    history.mean(history.temperature), history.mean(history.humidity),
    history.trend(history.temperature), history.trend(history.humidity),
    history.size > 1 ? history.trend(history.temperature) / (history.size - 1) : 0.0f,
    history.size > 1 ? history.trend(history.humidity) / (history.size - 1) : 0.0f,
    history.presenceCount()
  };
  const unsigned long regression_start = micros();
  const float forecast = history.size >= 2 ? regression_predict(regression_features) : temperature;
  const unsigned long regression_us = micros() - regression_start;
  const int future_prediction = rules_predict(forecast, humidity, presence);
  if (prediction < 0) {
    digitalWrite(LED_PIN, LOW); noTone(BUZZER_PIN);
    Serial.println("Leitura invalida; inferencia suspensa");
  } else {
    Serial.print("{\"temperatura\":"); printFloatJson(temperature);
    Serial.print(",\"umidade\":"); printFloatJson(humidity);
    Serial.print(",\"presenca\":"); Serial.print(presence, 0);
    Serial.print(",\"classe\":\""); Serial.print(MODEL_CLASSES[prediction]);
    Serial.print("\",\"media_temperatura\":"); printFloatJson(history.mean(history.temperature));
    Serial.print(",\"media_umidade\":"); printFloatJson(history.mean(history.humidity));
    Serial.print(",\"tendencia_temp\":"); printFloatJson(history.trend(history.temperature));
    Serial.print(",\"tendencia_umidade\":"); printFloatJson(history.trend(history.humidity));
    Serial.print(",\"temperatura_prevista_60s\":"); printFloatJson(forecast);
    Serial.print(",\"erro_estimado_mae\":"); printFloatJson(REGRESSION_MAE);
    Serial.print(",\"previsao_pronta\":"); Serial.print(history.size >= 2 ? "true" : "false");
    Serial.print(",\"alerta_futuro\":"); Serial.print(classSeverity(future_prediction) > classSeverity(prediction) ? "true" : "false");
    Serial.print(",\"tempo_regressao_us\":"); Serial.print(regression_us);
    Serial.print(",\"ood\":"); Serial.print(ood ? "true" : "false");
    Serial.print(",\"fallback\":"); Serial.print((ood || USE_EXACT_RULES) ? "true" : "false");
    Serial.print(",\"timestamp_ms\":"); Serial.print(millis());
    Serial.println("}");
#if BENCHMARK_MODE
    static uint16_t benchmark_count = 0;
    static unsigned long benchmark_total = 0, benchmark_min = 0xffffffff, benchmark_max = 0;
    benchmark_count++;
    benchmark_total += inference_us;
    if (inference_us < benchmark_min) benchmark_min = inference_us;
    if (inference_us > benchmark_max) benchmark_max = inference_us;
    if (benchmark_count >= 10) {
      Serial.print("{\"tipo\":\"benchmark\",\"inference_avg_us\":"); Serial.print(benchmark_total / benchmark_count);
      Serial.print(",\"inference_min_us\":"); Serial.print(benchmark_min);
      Serial.print(",\"inference_max_us\":"); Serial.print(benchmark_max);
      Serial.print(",\"regression_us\":"); Serial.print(regression_us);
      Serial.print(",\"ram_free_bytes\":"); Serial.print(rp2040.getFreeHeap());
      Serial.println("}");
      benchmark_count = 0; benchmark_total = 0; benchmark_min = 0xffffffff; benchmark_max = 0;
    }
#endif
    bool alert = strcmp(MODEL_CLASSES[prediction], "alerta") == 0 || strcmp(MODEL_CLASSES[prediction], "critico") == 0;
    digitalWrite(LED_PIN, alert ? HIGH : LOW);
    if (alert) tone(BUZZER_PIN, 2000); else noTone(BUZZER_PIN);
#if ENABLE_CLOUD
    cloudSend(temperature, humidity, (int)presence, MODEL_CLASSES[prediction]);
#endif
  }
  delay(2000);
}
