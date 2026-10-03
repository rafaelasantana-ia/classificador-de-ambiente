#pragma once
#include <math.h>
// Ordem: temperatura C, umidade %, presenca (1 = presente).
constexpr int MODEL_CLASS_COUNT = 4;
static const char* const MODEL_CLASSES[] = {"alerta","critico","normal","presenca"};
inline int model_predict(float temperatura, float umidade, float presenca) {
  const float x[3] = {temperatura, umidade, presenca};
  if (!isfinite(temperatura) || !isfinite(umidade) || temperatura < 0 || temperatura > 50 || umidade < 0 || umidade > 100 || (presenca != 0 && presenca != 1)) return -1;
  if ((double)x[2] <= 0.5) {
    if ((double)x[0] <= 29.5) {
      if ((double)x[1] <= 79) {
        if ((double)x[1] <= 53.5) {
          return 2;
        } else {
          return 2;
        }
      } else {
        if ((double)x[1] <= 89.5) {
          return 0;
        } else {
          return 1;
        }
      }
    } else {
      return 0;
    }
  } else {
    if ((double)x[1] <= 73.5) {
      if ((double)x[0] <= 30) {
        return 3;
      } else {
        if ((double)x[1] <= 68) {
          return 1;
        } else {
          return 1;
        }
      }
    } else {
      return 1;
    }
  }
}
