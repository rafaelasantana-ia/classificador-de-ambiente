#pragma once
#include <math.h>
// Ordem: temperatura C, umidade %, presenca (1 = presente).
constexpr int MODEL_CLASS_COUNT = 4;
static const char* const MODEL_CLASSES[] = {"alerta","critico","normal","presenca"};
inline int model_predict(float temperatura, float umidade, float presenca) {
  const float x[3] = {temperatura, umidade, presenca};
  if (!isfinite(temperatura) || !isfinite(umidade) || temperatura < 0 || temperatura > 50 || umidade < 0 || umidade > 100 || (presenca != 0 && presenca != 1)) return -1;
  if ((double)x[2] <= 0.5) {
    if ((double)x[0] <= 29.949999809265137) {
      if ((double)x[1] <= 79.900001525878906) {
        return 2;
      } else {
        if ((double)x[1] <= 89.5) {
          return 0;
        } else {
          return 1;
        }
      }
    } else {
      if ((double)x[1] <= 89.75) {
        if ((double)x[0] <= 34.950000762939453) {
          return 0;
        } else {
          return 1;
        }
      } else {
        return 1;
      }
    }
  } else {
    if ((double)x[0] <= 29.949999809265137) {
      if ((double)x[1] <= 79.900001525878906) {
        return 3;
      } else {
        if ((double)x[1] <= 85.25) {
          return 0;
        } else {
          return 1;
        }
      }
    } else {
      if ((double)x[0] <= 31.5) {
        if ((double)x[1] <= 85) {
          return 0;
        } else {
          return 1;
        }
      } else {
        return 1;
      }
    }
  }
}
