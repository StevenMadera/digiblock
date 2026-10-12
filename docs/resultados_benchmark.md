# Resultados del benchmark DigiBlock

- Fecha de ejecución (UTC): `2026-10-12T03:16:55.009611+00:00`
- Entorno: Python `3.14.8` · `Windows-11-10.0.26200-SP0`
- Muestras de emisión y verificación: **N = 100**
- SQLite temporal; no se modificó la base de datos de la demostración.

## Emisión y verificación ML-DSA-65

| Operación | Promedio (ms) | Mediana (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Emisión completa (firma + SQLite) | 106.381 | 90.974 | 208.664 | 412.912 |
| Verificación completa (firma + SQLite) | 26.167 | 25.565 | 30.993 | 35.978 |

## Comparación puntual de firmas

Una firma y verificación por algoritmo en este equipo; no es una evaluación estadística.

| Algoritmo | Clave pública (B) | Firma (B) | Firmar (ms) | Verificar (ms) |
|---|---:|---:|---:|---:|
| ML-DSA-65 | 1952 | 3309 | 83.820 | 14.655 |
| Ed25519 | 32 | 64 | 0.435 | 0.211 |

## Alcance de la medición

Las operaciones ML-DSA-65 incluyen firma/verificación y persistencia en SQLite temporal. La comparación de firmas mide una operación en vivo. El resultado describe este equipo y esta ejecución; no predice rendimiento de producción.
