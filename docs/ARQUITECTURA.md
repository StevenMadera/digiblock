# Arquitectura DigiBlock

## Componentes

```mermaid
flowchart LR
	Persona[Universidad / empresa]
	Navegador[Navegador]
	Web[FastAPI + Jinja2]
	API[API JSON]
	Sesion[Cookie firmada + scrypt]
	Servicios[Servicios de certificados y verificación]
	Crypto[Canonicalización + SHA-256 + Signer]
	Keystore[Claves locales ignoradas por Git]
	QR[Generador QR local]
	Ledger[Ledger hash-chain simulado]
	SQLite[(SQLite)]
	CSS[CSS propio + JavaScript mínimo]

	Persona --> Navegador
	Navegador -->|HTML / formularios| Web
	Navegador -->|JSON / API| API
	Navegador --> CSS
	Web --> Sesion
	API --> Sesion
	Web --> Servicios
	API --> Servicios
	Servicios --> Crypto
	Crypto --> Keystore
	Servicios --> SQLite
	Servicios --> Ledger
	Ledger --> SQLite
	Servicios --> QR
```

FastAPI integra las rutas y crea el esquema SQLite al arrancar. Jinja2 renderiza las páginas con autoescape; los datos de usuario no se marcan como HTML seguro. El middleware de sesión firma la cookie y limita el cuerpo de solicitudes API. SQLite se accede mediante `sqlite3` y consultas parametrizadas.

## Emisión

```mermaid
sequenceDiagram
	actor U as Universidad
	participant W as Web / API
	participant S as Servicio de certificados
	participant C as Canonicalización + Signer
	participant K as Keystore local
	participant D as SQLite
	participant L as Ledger simulado

	U->>W: Datos ficticios
	W->>S: Validar campos y fecha UTC
	S->>C: Documento con campos firmados
	C->>C: JSON canónico + SHA-256
	C->>K: Firmar bytes canónicos con ML-DSA-65
	K-->>C: Firma
	S->>D: Guardar documento, huella, firma y estado vigente
	S->>L: Registrar EMISION
	W-->>U: ID, QR y descarga JSON
```

El documento firmado contiene `id`, `estudiante_nombre`, `estudiante_documento`, `programa`, `titulo`, `fecha_expedicion`, `universidad` y `version_esquema`. SHA-256 solo produce la huella; la clave privada firma los bytes canónicos.

## Verificación

```mermaid
sequenceDiagram
	actor C as Empresa / estudiante
	participant W as Web / API
	participant V as Servicio de verificación
	participant D as SQLite
	participant K as Clave pública
	participant L as Ledger simulado

	C->>W: Código, QR o diploma JSON
	W->>V: Documento y/o identificador
	V->>D: Consultar certificado y estado
	alt Código no existe
		V->>L: Registrar VERIFICACION
		V-->>W: NO_ENCONTRADO
	else Registro disponible
		V->>V: Recalcular huella SHA-256
		V->>K: Verificar firma del documento
		alt Huella o firma incorrecta
			V->>L: VERIFICACION + ALTERACION_DETECTADA
			V-->>W: ALTERADO
		else Firma y huella correctas, revocado
			V->>L: Registrar VERIFICACION
			V-->>W: REVOCADO (firma válida)
		else Firma y huella correctas, vigente
			V->>L: Registrar VERIFICACION
			V-->>W: VALIDO
		end
	end
	W-->>C: Estado, comprobaciones y tiempo
```

La prioridad de decisión es `NO_ENCONTRADO`, después `ALTERADO`, luego `REVOCADO` y finalmente `VALIDO`. El diff es complementario: no sustituye la verificación criptográfica.

## Revocación

```mermaid
sequenceDiagram
	actor U as Universidad autenticada
	participant API as API protegida
	participant S as Servicio de certificados
	participant D as SQLite
	participant L as Ledger simulado

	U->>API: POST de revocación + motivo
	API->>S: Comprobar sesión y estado actual
	S->>D: Cambiar vigente a revocado
	S->>L: Registrar REVOCACION
	API-->>U: Estado revocado
	Note over D,L: La firma no se modifica; la próxima verificación informa REVOCADO
```

## Decisiones y límites

- **ML-DSA-65 (FIPS 204):** firma por defecto detrás de `Signer`. `dilithium-py` es pura en Python, educativa y no auditada para producción.
- **Ed25519:** comparación clásica del laboratorio; no se presenta como resistente a ataques cuánticos.
- **SQLite:** módulo estándar, ruta configurable y operaciones SQL parametrizadas. Los datos de demo son ficticios.
- **Hash chain:** cada evento referencia el hash anterior. Es una simulación local en SQLite: no hay nodos independientes, consenso ni anclaje externo; no garantiza la verdad de los datos.
- **Claves:** `keys/` está ignorada por Git. El prototipo no reemplaza un HSM o gestor de secretos ni implementa custodia de producción.
- **Autenticación:** scrypt, comparación en tiempo constante, bloqueo temporal y cookie firmada `HttpOnly` / `SameSite=Lax`.
- **Interfaz:** Jinja2, CSS propio y JavaScript vanilla; no depende de CDNs para la demo.
