# D009 — Fallar al arrancar si PostgreSQL no está disponible

## Status

Accepted para M2.

## Problem and decision

`GET /health` comprueba que el proceso responde, pero no tenemos todavía
readiness para expresar una dependencia de datos inaccesible. Si la API
arrancase con PostgreSQL caído, parecería sana mientras sus endpoints
principales fallan. El desarrollador considera razonable arrancar en modo
degradado cuando exista readiness; para M2 acuerda fallar temprano.

Durante startup se ejecuta `SELECT 1` sobre una conexión real. Si falla,
Uvicorn no acepta tráfico y el Engine se cierra. Las migraciones siguen siendo
una operación explícita separada del arranque.

## Trade-offs

Una caída temporal de PostgreSQL durante startup impide levantar la API.
Más adelante, M14 puede introducir readiness, recuperación y una política
de disponibilidad parcial. Esta decisión no obliga a tratar igual una caída
que ocurra después del arranque.
