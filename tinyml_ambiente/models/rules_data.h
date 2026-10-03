#pragma once
// Inclua model_data.h antes deste arquivo.
inline int rules_predict(float temperatura, float umidade, float presenca) {
  if (!isfinite(temperatura) || !isfinite(umidade) || temperatura < 0 || temperatura > 50 || umidade < 0 || umidade > 100 || (presenca != 0 && presenca != 1)) return -1;
  if ((temperatura >= 35) || (umidade >= 90)) return 1;
  if ((presenca == 1) && (temperatura >= 32)) return 1;
  if ((presenca == 1) && (umidade >= 85)) return 1;
  if ((temperatura >= 30) || (umidade >= 80)) return 0;
  if ((presenca == 1)) return 3;
  return 2;
}
