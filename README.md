# DigiBlock

DigiBlock es un prototipo académico de certificados digitales verificables. Una universidad de demostración emite un documento ficticio, calcula su huella SHA-256 y lo firma con ML-DSA-65. Una empresa puede comprobar el código, QR o archivo JSON y consultar si el certificado fue revocado.

> **Prototipo académico.** No es un sistema de producción ni usa una blockchain distribuida. Todos los nombres y documentos de las instrucciones de demo son ficticios.

## Alcance y limitaciones

**Implementado:** serialización canónica con normalización Unicode, SHA-256, firma y verificación ML-DSA-65, comparación Ed25519, persistencia SQLite, revocación y registro de eventos encadenado por hashes. El verificador decide con la firma, la huella y el estado del registro; el módulo de diferencias solo describe campos modificados.

**Simulado:** consenso y replicación de blockchain, identidad de una universidad real y datos de estudiantes reales. La cadena SQLite local no demuestra que los datos ingresados sean verdaderos y no reemplaza la criptografía.

`dilithium-py` es una implementación educativa y no está auditada para producción. Las claves privadas del prototipo se guardan como archivos locales bajo `keys/`; la carpeta está ignorada por Git, pero esto no equivale a un HSM ni a un gestor de secretos. En producción se requiere custodia y control de acceso adecuados.

SHA-256 detecta cambios, pero no es una firma. La autenticidad la comprueba la firma digital con la clave pública. ML-DSA es poscuántico; no vuelve invulnerable el resto del sistema.

## Requisitos

- Windows 10/11 y PowerShell.
- Python 3.11 o superior.
- No se requiere Node.js ni compilación local de C/C++ para las dependencias fijadas en `requirements.txt`.

## Instalación en Windows

Desde PowerShell, sitúate en la carpeta del proyecto:

```powershell
Set-Location "C:\ruta\a\Prototipo\digiblock"
python --version
python -m venv .venv
```

Activa el entorno. Si la política de ejecución bloquea el script, permite scripts solo en el proceso actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Instala dependencias y crea la configuración local:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` antes de iniciar una demo compartida. Cambia `ADMIN_PASSWORD` y reemplaza `SECRET_KEY` por un valor aleatorio. Puedes generar uno localmente con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

La salida es una clave secreta: pégala directamente en `.env` y no la publiques ni la incluyas en capturas.

## Ejecutar

```powershell
python -m uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/`. La comprobación de salud está en `http://127.0.0.1:8000/salud`; la documentación interactiva de la API, en `http://127.0.0.1:8000/docs`.

El primer arranque crea el esquema SQLite. La primera emisión o consulta de clave pública genera el par local si aún no existe.

### Demostrar desde el celular

`127.0.0.1` solo es accesible desde el propio PC. Para que un teléfono de la misma red abra el QR, configura `BASE_URL` en `.env` con la IPv4 privada del PC, por ejemplo `http://192.168.1.34:8000`, y arranca el servidor escuchando en la red local:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Permite el puerto 8000 únicamente en el perfil de red privada si Windows Firewall lo solicita. Mantén el PC y el celular en la misma red; no expongas este prototipo a Internet.

## Despliegue en Render

El Blueprint está en `render.yaml`. Al crear el servicio, define `ADMIN_PASSWORD`, `SECRET_KEY` y `BASE_URL` en el panel de Render; el servicio usa `APP_ENV=produccion`. `BASE_URL` debe ser la URL HTTPS pública asignada al servicio, sin una barra final. Render Free usa almacenamiento efímero para el sistema de archivos: un reinicio o redeploy puede borrar `data/` y `keys/`. El arranque volverá a sembrar la demo y generará claves nuevas, pero certificados anteriores dejarán de verificar. Este plan sirve para demostración, no para conservar registros; persistencia real requiere almacenamiento durable y gestión de claves externa.

## Acceso y flujos

Las credenciales se leen de `.env`. El archivo de ejemplo usa `ADMIN_USER=universidad` y `ADMIN_PASSWORD=cambiar-antes-de-usar`; son valores de desarrollo y deben sustituirse antes de una demostración compartida.

- **Resumen:** contadores de emisión, verificación, revocación y estado de la cadena local.
- **Emitir:** formulario universitario, diploma, QR, huella y descarga JSON.
- **Verificar:** código, QR o archivo JSON; muestra huella, firma, vigencia y tiempo.
- **Trazabilidad:** eventos y verificación de la cadena simulada.
- **Laboratorio:** alteración/restauración, efecto avalancha, comparación de firmas y mini-benchmark.
- **Alcance:** componentes reales frente a simulados y limitaciones.

La sesión universitaria se protege con cookie firmada, `HttpOnly` y `SameSite=Lax`. Los intentos de acceso se limitan temporalmente. Las operaciones de emisión, revocación, laboratorio y reinicio requieren sesión.

## Datos de demostración

Carga cinco estudiantes ficticios; la operación es idempotente:

```powershell
python scripts/seed_demo.py
```

Para borrar la base y las claves locales de demostración y volver a cargar los cinco registros:

```powershell
python scripts/reset_demo.py
```

El reset invalida cualquier certificado firmado con el par de claves anterior. No lo ejecutes mientras una demo en vivo dependa de esos certificados.

## Pruebas y benchmark

```powershell
python -m pytest
python scripts/benchmark.py
```

La última salida de `python -m pytest` fue **83 passed, 70 warnings**. Las 70 advertencias son de dependencias bajo Python 3.14: 69 menciones de `asyncio.iscoroutinefunction` en FastAPI y una de `anyio.abc.BlockingPortal` en Starlette; no son fallos de DigiBlock.

El benchmark N=100 mide emisión y verificación reales con SQLite temporal. Estas cifras deben coincidir con [docs/resultados_benchmark.md](docs/resultados_benchmark.md) y describen esta máquina, no un SLA:

| Operación | Promedio (ms) | Mediana (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Emisión completa (firma + SQLite) | 106.381 | 90.974 | 208.664 | 412.912 |
| Verificación completa (firma + SQLite) | 26.167 | 25.565 | 30.993 | 35.978 |

Comparación puntual de una firma y verificación por algoritmo:

| Algoritmo | Clave pública (B) | Firma (B) | Firmar (ms) | Verificar (ms) |
|---|---:|---:|---:|---:|
| ML-DSA-65 | 1952 | 3309 | 83.820 | 14.655 |
| Ed25519 | 32 | 64 | 0.435 | 0.211 |

## Estructura

```text
app/
	crypto/       Canonicalización, SHA-256, firmas y almacén de claves
	routers/      Páginas Jinja y API JSON
	services/     Autenticación, certificados, verificación, QR, ledger y laboratorio
	templates/    Vistas HTML escapadas por Jinja
	static/       CSS propio y JavaScript mínimo
tests/          Pruebas unitarias, API, seguridad, escenarios y rendimiento
scripts/        Seed, reset y benchmark
docs/           Arquitectura, plan de pruebas, guion y resultados
keys/           Claves locales; ignorada por Git
data/           SQLite local; ignorada por Git
```

## Capturas sugeridas

Guarda imágenes locales para la sustentación de: tablero inicial, certificado emitido con QR, resultado válido, resultado alterado con su diff, advertencia de revocación, integridad de la cadena y tabla comparativa ML-DSA-65/Ed25519. Usa solo registros ficticios y oculta cualquier secreto de `.env`.
