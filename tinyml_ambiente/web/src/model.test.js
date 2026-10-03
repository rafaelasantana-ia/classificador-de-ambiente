import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tree, exact, parseSerial } from './model.js';
test('prioridades e limites ambientais', () => {
  assert.equal(exact(29,79,0),'normal'); assert.equal(exact(30,60,0),'alerta');
  assert.equal(exact(35,60,0),'critico'); assert.equal(exact(32,60,1),'critico');
  assert.equal(exact(24,85,1),'critico'); assert.equal(exact(24,60,1),'presenca');
  assert.equal(exact(51,60,0),null); assert.equal(tree(NaN,60,0),null);
});
test('árvore preserva limiares do firmware e divergência conhecida', () => {
  assert.equal(tree(35,60,0),'alerta'); assert.equal(tree(29.5,79,0),'normal');
  assert.equal(tree(29.6,79,0),'alerta'); assert.equal(tree(24,89.6,0),'critico');
  assert.equal(tree(30,73.5,1),'presenca'); assert.equal(tree(30.1,73.5,1),'critico');
});
test('serial aceita firmware e ignora diagnósticos e leituras inválidas', () => {
  assert.equal(parseSerial('T=24.0 U=70.0 IR=0 presenca=1 classe=presenca').presenca,1);
  assert.equal(parseSerial('Temp raw: 24.0'),null);
  assert.equal(parseSerial('T=nan U=70.0 IR=1 presenca=0 classe=normal'),null);
  assert.equal(parseSerial('T=24 U=70 IR=0 presenca=0 classe=normal'),null);
});
