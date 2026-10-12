# Plan de pruebas DigiBlock

## Matriz acumulada

| ID | Descripción | Tipo | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|
| T-00 | Endpoint de salud | Funcional | HTTP 200 y `{"estado":"ok"}` | Pasó en `tests/test_api.py` |
| T-01 | Canonicalización, NFC y espacios | Integridad | Bytes deterministas; cambios distinguidos | Pasó: 4 pruebas |
| T-02 | SHA-256 y huella | Integridad | Vector conocido, longitud 64 y avalancha | Pasó: 4 pruebas |
| T-03 | ML-DSA-65, Ed25519 y keystore | Seguridad | Firma válida; alteraciones rechazadas; claves reutilizadas | Pasó: 9 pruebas |
| T-04 | SQLite y hash chain | Integridad / SQL | Idempotencia, alteración, borrado e inyección detectados | Pasó: 10 pruebas |
| T-05 | Emisión, QR y revocación | Funcional | Campos validados; emisión y errores esperados | Pasó: 8 pruebas |
| T-06 | Verificación y diff | Integridad | Cuatro estados y prioridad de firma sobre hash | Pasó: 10 pruebas |
| T-07 | API y seguridad | Seguridad / funcional | Sesiones, permisos, límites y ausencia de clave privada | Pasó: 12 pruebas de seguridad y 7 de API |
| T-08 | Seed, reset y benchmark | Funcional / rendimiento | Idempotencia, reset reproducible e informe escrito | Pasó: 3 pruebas |
| T-09 | Escenarios de sustentación | Funcional / integridad | Cuatro escenarios y cadena final válida | Pasó: 5 pruebas |
| T-10 | Umbrales de rendimiento | Rendimiento | Promedios < 1 s y 50 verificaciones estables | Pasó: 3 pruebas |
| T-11 | Páginas, escape HTML y laboratorio | Funcional / seguridad | Sesión, estados, XSS y alteración/restauración | Pasó: 8 pruebas web |

**Resultado acumulado final:** `python -m pytest` → **83 passed**. Se reportaron 70 advertencias de dependencias, no fallos de DigiBlock.

## Resultados automatizados

| ID | Descripción | Tipo | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|
| W-01 | Dashboard, acceso, verificación, trazabilidad y acerca responden | Funcional | HTTP 200 | Pasó en `tests/test_web.py` |
| W-02 | Emisión y laboratorio redirigen a login sin sesión | Seguridad | HTTP 303 | Pasó en `tests/test_web.py` |
| W-03 | Login permite emitir y operar el laboratorio | Funcional | HTTP 200 / 201 | Pasó en `tests/test_web.py` |
| W-04 | Nombre con etiquetas script se escapa en HTML | Seguridad | Sin etiqueta ejecutable | Pasó en `tests/test_web.py` |
| W-05 | Los cuatro estados aparecen en la verificación web | Funcional | NO_ENCONTRADO, VALIDO, ALTERADO y REVOCADO | Pasó en `tests/test_web.py` |
| W-06 | La simulación de alteración puede restaurarse | Integridad | ALTERADO y luego VALIDO | Pasó en `tests/test_web.py` y recorrido local |

**Resultado al cierre de Fase 5:** `pytest` terminó con **70 passed** y 64 advertencias de dependencias.

## Fase 6: escenarios y rendimiento

| ID | Descripción | Tipo | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|
| S-01 | Los cuatro escenarios de sustentación por API | Funcional / integridad | Emisión, válido, alterado, revocado | Pasó: `tests/test_scenarios_demo.py` (5 pruebas) |
| S-02 | Hash chain después de los cuatro escenarios | Integridad | Cadena válida | Pasó: `test_cadena_valida_despues_de_los_cuatro_escenarios` |
| D-01 | Seed de cinco estudiantes y verificaciones iniciales | Funcional | Segunda ejecución no añade eventos ni certificados | Pasó: `tests/test_demo_scripts.py` |
| D-02 | Reset de base y claves, seguido de seed | Funcional / integridad | Cinco certificados nuevos, cadena válida | Pasó: `tests/test_demo_scripts.py` |
| P-01 | Verificación bajo un segundo de promedio | Rendimiento | Menos de 1 s | Pasó: `tests/test_performance.py` |
| P-02 | Cincuenta verificaciones consecutivas | Rendimiento | Sin degradación notable | Pasó: `tests/test_performance.py` |
| B-01 | Benchmark real de 100 emisiones y verificaciones | Rendimiento | Informe con promedio, mediana, p95 y máximo | Emisión: 106.381 / 90.974 / 208.664 / 412.912 ms; verificación: 26.167 / 25.565 / 30.993 / 35.978 ms. Generado: [resultados_benchmark.md](resultados_benchmark.md) |

Comparación puntual del mismo informe: ML-DSA-65, clave pública 1952 B, firma 3309 B, firmar 83.820 ms y verificar 14.655 ms; Ed25519, clave pública 32 B, firma 64 B, firmar 0.435 ms y verificar 0.211 ms.

**Suite completa al cierre de Fase 6:** `python -m pytest` terminó con **83 passed** y 70 advertencias de dependencias: 69 menciones de `asyncio.iscoroutinefunction` obsoleto en FastAPI y una de `anyio.abc.BlockingPortal` en Starlette. No son errores de DigiBlock.

## Recorrido visual manual
Recorrido exploratorio realizado con el navegador integrado a 1440 × 1000 y 390 × 844: resumen, emisión, certificado, verificación, trazabilidad, laboratorio y alcance. Se comprobó en vivo la simulación y restauración. Las casillas siguen pendientes porque no se completaron todas las páginas a 125 % ni la revisión integral de consola.

| Página | 100 % | 125 % | Ventana angosta | Consola sin errores |
|---|---:|---:|---:|---:|
| Resumen | [ ] | [ ] | [ ] | [ ] |
| Acceso | [ ] | [ ] | [ ] | [ ] |
| Emisión | [ ] | [ ] | [ ] | [ ] |
| Vista del certificado | [ ] | [ ] | [ ] | [ ] |
| Verificación | [ ] | [ ] | [ ] | [ ] |
| Trazabilidad | [ ] | [ ] | [ ] | [ ] |
| Laboratorio | [ ] | [ ] | [ ] | [ ] |
| Alcance | [ ] | [ ] | [ ] | [ ] |
| Error 404 | [ ] | [ ] | [ ] | [ ] |

Antes de la sustentación, completar el recorrido con un navegador Chromium a 100 % y 125 %, y repetir cada página en una ventana angosta. Confirmar foco visible, lectura de estados sin depender solo del color, descarga y lectura del QR en un celular conectado a la misma red.
