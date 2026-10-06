#pragma once
// Gerado por training/train_regression.py. Nao edite manualmente.
#include <math.h>

constexpr int REGRESSION_FEATURE_COUNT = 10;
constexpr float REGRESSION_WEIGHTS[REGRESSION_FEATURE_COUNT] = {1.17601271f, 0.0592524264f, 0.0558688561f, -0.166833679f, -0.06325903f, 2.19428337f, -0.00699138117f, 0.24380947f, -0.000776920984f, -0.00582558415f};
constexpr float REGRESSION_BIAS = 0.138456528f;
constexpr float REGRESSION_MAE = 1.015076f;
constexpr float REGRESSION_RMSE = 1.319912f;
constexpr int REGRESSION_HORIZON_SECONDS = 60;

inline float regression_predict(const float features[REGRESSION_FEATURE_COUNT]) {
  float result = REGRESSION_BIAS;
  for (int i = 0; i < REGRESSION_FEATURE_COUNT; ++i) result += REGRESSION_WEIGHTS[i] * features[i];
  return result;
}
