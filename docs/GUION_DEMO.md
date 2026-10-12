# Guion de sustentación DigiBlock · 10 minutos

Todos los registros de la demo son ficticios. Antes de presentar, usa el reset que repuebla cinco certificados, inicia el servidor y comprueba el QR con un teléfono en la misma red local.

## Minuto a minuto

| Tiempo | Acción | Qué decir | Resultado esperado |
|---|---|---|---|
| 00:00–01:00 | Presentar el problema de la verificación manual de diplomas | “La verificación tradicional depende de llamadas, correos y trámites que pueden tardar. El prototipo busca ofrecer una comprobación rápida y repetible.” | Contexto del problema sin afirmar que elimina todo fraude |
| 01:00–02:00 | Mostrar el resumen DigiBlock | “La universidad emite un documento digital; una empresa puede contrastar su contenido, firma y vigencia.” | Tablero con contadores y cadena de trazabilidad |
| 02:00–04:00 | Abrir **Alcance** y describir el diagrama | “SHA-256 detecta cambios; ML-DSA-65 firma. SQLite guarda eventos encadenados, pero la cadena es simulada y no prueba que los datos originales fueran verdaderos.” | Componentes y límites reales/simulados claramente visibles |
| 04:00–05:00 | **Escenario 1:** entrar como universidad, abrir **Emitir**, completar los datos ficticios y pulsar **Emitir certificado** | “El servidor normaliza y serializa los campos firmados, calcula la huella y firma el documento con ML-DSA-65.” | Estado **EMITIDO**, ID, huella SHA-256, QR y enlace de verificación |
| 05:00–06:00 | **Escenario 2:** cerrar sesión; en **Verificar**, introducir el ID o escanear el QR | “La consulta es pública y contrasta huella, firma y vigencia por separado.” | **VALIDO**, las tres comprobaciones positivas y evento `VERIFICACION` |
| 06:00–07:00 | **Escenario 3:** volver a entrar, abrir **Laboratorio**, pulsar **Simular alteración**; verificar por ID y luego subir un JSON con el nombre cambiado; pulsar **Restaurar original** | “La modificación rompe la huella y la firma. El diff solo explica el campo cambiado; la decisión la toma la verificación criptográfica.” | **ALTERADO**, diff de `estudiante_nombre`, evento `ALTERACION_DETECTADA`; tras restaurar vuelve a **VALIDO** |
| 07:00–08:00 | **Escenario 4:** en `/docs`, usar **Try it out** en `POST /api/certificados/{certificado_id}/revocar`, completar motivo y pulsar **Execute**; regresar a **Verificar** | “La revocación no cambia la firma histórica. El verificador conserva `firma_valida=True`, pero informa que el certificado ya no está vigente.” | **REVOCADO** con firma válida y evento `REVOCACION` |
| 08:00–09:00 | Mostrar resultados de `python -m pytest` y abrir el benchmark | “El último resultado fue 83 passed y 70 warnings de dependencias. La emisión promedió 106.381 ms y la verificación 26.167 ms en este equipo; no son garantías de producción.” | 83 passed y tabla real N=100 |
| 09:00–10:00 | Cerrar con límites y trabajo futuro | “El prototipo demuestra integridad y procedencia de una firma. No autentica la verdad de los datos, no usa blockchain distribuida y requiere custodia de claves de producción.” | Conclusión honesta y preguntas |

Para una presentación sin consola, sustituye la consulta REST del escenario 4 por una pantalla de `/docs` en el mismo navegador. La sesión universitaria iniciada en DigiBlock se conserva para las llamadas del mismo origen.

### Cifras exactas del informe N=100

| Operación | Promedio (ms) | Mediana (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Emisión completa (firma + SQLite) | 106.381 | 90.974 | 208.664 | 412.912 |
| Verificación completa (firma + SQLite) | 26.167 | 25.565 | 30.993 | 35.978 |

| Algoritmo | Clave pública (B) | Firma (B) | Firmar (ms) | Verificar (ms) |
|---|---:|---:|---:|---:|
| ML-DSA-65 | 1952 | 3309 | 83.820 | 14.655 |
| Ed25519 | 32 | 64 | 0.435 | 0.211 |

## Plan B

- **Falla el acceso del celular:** verifica que `BASE_URL` use la IPv4 privada del PC, arranca Uvicorn con `--host 0.0.0.0`, revisa la regla de Windows Firewall en red privada y confirma que ambos dispositivos estén en la misma Wi-Fi. Continúa en el navegador del PC si hace falta.
- **Falla la aplicación:** conserva la evidencia de `pytest`, abre las capturas de respaldo y explica el flujo con el diagrama de arquitectura. No presentes una captura como una verificación en vivo.
- **Se cuelga el navegador:** espera unos segundos por ML-DSA en Python puro, recarga una sola vez y comprueba el servicio en `/salud`. Si sigue sin responder, usa capturas y resultados guardados; no repitas una emisión varias veces sin revisar el registro.
- **Falla una llamada API:** muestra el ID y explica que una respuesta `ALTERADO`/`REVOCADO` no equivale a un fallo de firma válida; distingue siempre la comprobación criptográfica del estado administrativo.

## Preguntas probables del jurado

1. **¿Por qué blockchain si una firma ya autentica?** La firma comprueba origen e integridad; la capa de trazabilidad aporta un historial de eventos verificable entre varias entidades. Blockchain no reemplaza la criptografía ni garantiza que los datos ingresados sean verdaderos. En esta demo, además, la cadena es simulada en una sola SQLite.
2. **¿SHA-256 es la firma?** No. SHA-256 calcula una huella para detectar cambios; ML-DSA-65 firma los bytes canónicos con la clave privada y la clave pública verifica esa firma.
3. **¿Qué protege ML-DSA-65?** Es un esquema de firma poscuántico estandarizado en NIST FIPS 204. La librería usada aquí es educativa y no auditada; no afirmamos seguridad de producción.
4. **¿Por qué comparar con Ed25519?** Es una referencia clásica compacta y rápida en este equipo. Se incluye para contrastar tamaños y tiempos; no está diseñada para resistir un computador cuántico criptográficamente relevante.
5. **¿Dónde está la clave privada?** En el prototipo se guarda en un archivo local dentro de `keys/`, no se devuelve por API y no se registra en logs. En producción se movería a un HSM o gestor de secretos con controles de acceso.
6. **¿Qué ocurre si alguien modifica la base de datos?** La verificación recalcula la huella y comprueba la firma. Incluso si se altera también la huella en SQLite, una firma que no corresponde a la clave pública falla. La cadena local ayuda a detectar cambios de eventos, no evita por sí sola una reescritura completa sin ancla externa.
7. **¿La revocación invalida la firma?** No. La firma puede continuar siendo válida; el estado administrativo se consulta aparte y el resultado final es `REVOCADO`.
8. **¿Cómo saben que el título emitido es verdadero?** No lo sabemos automáticamente. El prototipo verifica integridad y origen respecto a la clave de la universidad; la institución sigue siendo responsable de comprobar los datos antes de firmarlos.
9. **¿Qué tan rápido es?** En el benchmark N=100 de este PC, la emisión con SQLite promedió 106.381 ms y la verificación 26.167 ms. Son mediciones locales, no una promesa de rendimiento para otros equipos.
10. **¿Puede usarlo cualquier universidad hoy?** No. Faltan identidad institucional verificable, gestión de claves de producción, despliegue distribuido, políticas legales/privacidad, auditoría de la implementación y operación entre entidades.

## Checklist previa

- [ ] Ejecutar `python scripts/reset_demo.py` desde el entorno virtual; confirma cinco registros ficticios.
- [ ] Revisar `.env`: credenciales de demo, `SECRET_KEY` aleatoria y `BASE_URL` correcta.
- [ ] Arrancar `python -m uvicorn app.main:app --reload` y comprobar `/salud`.
- [ ] Abrir el navegador en pantalla completa y dejar preparada la cuenta universitaria.
- [ ] Probar el QR desde un teléfono conectado a la misma red.
- [ ] Revisar que la cadena aparezca válida y que no haya errores visibles en la consola.
- [ ] Guardar capturas de resumen, emisión, válido, alterado, revocado, trazabilidad y laboratorio.
- [ ] Tener disponible `docs/resultados_benchmark.md` y la salida de `python -m pytest`.
- [ ] Cerrar terminales o páginas que muestren secretos; no incluir `.env` en capturas.
