#include <Arduino.h>
#include <DHT.h>
#include <math.h>
#include <string.h>
#include "../models/model_data.h"
#include "../models/rules_data.h"

// 0: árvore TinyML; 1: reprodução exata das regras, alternativa para operação.
#ifndef USE_EXACT_RULES
#define USE_EXACT_RULES 0
#endif

// Diagnostico temporario: compile com -DDHT_DIAGNOSTICS=0 para desativar.
#ifndef DHT_DIAGNOSTICS
#define DHT_DIAGNOSTICS 1
#endif

// GPIO externos: ajuste para sua ligação real. Numeração GPIO, não pino físico.
constexpr int DHT_PIN = 2, IR_PIN = 14, LED_PIN = 16, BUZZER_PIN = 17;
DHT dht(DHT_PIN, DHT11);
void setup() {
  Serial.begin(115200);
  dht.begin();
  pinMode(IR_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
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
  }
  int ir = digitalRead(IR_PIN);
  float presence = (ir == LOW) ? 1.0f : 0.0f;
  int prediction = USE_EXACT_RULES ? rules_predict(temperature, humidity, presence)
                                   : model_predict(temperature, humidity, presence);
  if (prediction < 0) {
    digitalWrite(LED_PIN, LOW); noTone(BUZZER_PIN);
    Serial.println("Leitura invalida; inferencia suspensa");
  } else {
    // Print de float independe do suporte a %f na biblioteca printf do build.
    Serial.print("T="); Serial.print(temperature, 1);
    Serial.print(" U="); Serial.print(humidity, 1);
    Serial.print(" IR="); Serial.print(ir);
    Serial.print(" presenca="); Serial.print(presence, 0);
    Serial.print(" classe="); Serial.println(MODEL_CLASSES[prediction]);
    bool alert = strcmp(MODEL_CLASSES[prediction], "alerta") == 0 || strcmp(MODEL_CLASSES[prediction], "critico") == 0;
    digitalWrite(LED_PIN, alert ? HIGH : LOW);
    if (alert) tone(BUZZER_PIN, 2000); else noTone(BUZZER_PIN);
  }
  delay(2000);
}
