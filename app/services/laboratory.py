"""Operaciones explícitamente simuladas del laboratorio académico."""

from statistics import mean
from threading import Lock
from time import perf_counter

from app.crypto.canonical import canonicalizar
from app.crypto.hashing import sha256_hex
from app.crypto.signer import Ed25519Signer, MLDSASigner, Signer
from app.database import conectar
from app.services.certificates import obtener_certificado
from app.services.ledger import registrar_evento

_ALTERACIONES: dict[str, tuple[str, str]] = {}
_BLOQUEO = Lock()


def simular_alteracion(certificado_id: str, campo: str = "estudiante_nombre") -> None:
	"""Modifica un campo permitido y conserva su original en memoria para restaurar."""
	if campo not in {"estudiante_nombre", "fecha_expedicion"}:
		raise ValueError("El laboratorio solo permite alterar nombre o fecha.")
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		raise LookupError(f"No existe el certificado {certificado_id}.")

	with _BLOQUEO:
		if certificado_id in _ALTERACIONES:
			raise ValueError("El certificado ya tiene una alteración de laboratorio activa.")
		valor_original = getattr(certificado, campo)
		valor_alterado = (
			f"{valor_original} [ALTERADO]"
			if campo == "estudiante_nombre"
			else "2099-01-01"
		)
		with conectar() as conexion:
			conexion.execute(
				f"UPDATE certificados SET {campo} = ? WHERE id = ?",
				(valor_alterado, certificado_id),
			)
		_ALTERACIONES[certificado_id] = (campo, valor_original)

	registrar_evento(
		certificado_id,
		"ALTERACION_DETECTADA",
		f"Simulación de laboratorio: se alteró el campo {campo}.",
	)


def restaurar_alteracion(certificado_id: str) -> None:
	"""Restaura el valor anterior guardado para una simulación activa."""
	with _BLOQUEO:
		alteracion = _ALTERACIONES.get(certificado_id)
		if alteracion is None:
			raise ValueError("No hay una alteración de laboratorio que restaurar.")
		campo, valor_original = alteracion
		with conectar() as conexion:
			conexion.execute(
				f"UPDATE certificados SET {campo} = ? WHERE id = ?",
				(valor_original, certificado_id),
			)
		_ALTERACIONES.pop(certificado_id)

	registrar_evento(
		certificado_id,
		"ALTERACION_DETECTADA",
		f"Simulación de laboratorio: se restauró el campo {campo}.",
	)


def reiniciar_datos_demo() -> int:
	"""Borra los certificados y eventos locales, preservando el par de claves."""
	with conectar() as conexion:
		conexion.execute("BEGIN IMMEDIATE")
		cantidad = conexion.execute("SELECT COUNT(*) FROM certificados").fetchone()[0]
		conexion.execute("DELETE FROM eventos")
		conexion.execute("DELETE FROM certificados")
	with _BLOQUEO:
		_ALTERACIONES.clear()
	return cantidad


def _medir_firmante(firmante: Signer) -> dict[str, float | int | str]:
	"""Mide una firma y verificación, junto con los tamaños de claves y firma."""
	clave_publica, _ = firmante.generar_claves()
	mensaje = canonicalizar({"demo": "certificado ficticio DigiBlock"})
	inicio_firma = perf_counter()
	firma = firmante.firmar(mensaje)
	tiempo_firma = (perf_counter() - inicio_firma) * 1000
	inicio_verificacion = perf_counter()
	valida = firmante.verificar(mensaje, firma, clave_publica)
	tiempo_verificacion = (perf_counter() - inicio_verificacion) * 1000
	if not valida:
		raise RuntimeError(f"La verificación de {firmante.nombre_algoritmo} falló.")
	return {
		"algoritmo": firmante.nombre_algoritmo,
		"clave_publica_bytes": len(clave_publica),
		"firma_bytes": len(firma),
		"firma_ms": round(tiempo_firma, 3),
		"verificacion_ms": round(tiempo_verificacion, 3),
	}


def medir_comparacion_firmas() -> list[dict[str, float | int | str]]:
	"""Mide ML-DSA-65 y Ed25519 en el equipo que ejecuta la demo."""
	return [_medir_firmante(MLDSASigner()), _medir_firmante(Ed25519Signer())]


def ejecutar_mini_benchmark(cantidad: int = 50) -> dict[str, float | int | str]:
	"""Mide cincuenta operaciones del núcleo criptográfico sin SQLite ni HTTP."""
	if not isinstance(cantidad, int) or cantidad < 1 or cantidad > 1000:
		raise ValueError("La cantidad del benchmark debe estar entre 1 y 1000.")
	firmante = MLDSASigner()
	clave_publica, _ = firmante.generar_claves()
	tiempos_emision: list[float] = []
	tiempos_verificacion: list[float] = []

	for numero in range(cantidad):
		documento = {"id": f"DGB-DEMO-{numero:04d}", "programa": "Sistemas"}
		inicio = perf_counter()
		mensaje = canonicalizar(documento)
		sha256_hex(mensaje)
		firma = firmante.firmar(mensaje)
		tiempos_emision.append((perf_counter() - inicio) * 1000)

		inicio = perf_counter()
		sha256_hex(mensaje)
		valida = firmante.verificar(mensaje, firma, clave_publica)
		tiempos_verificacion.append((perf_counter() - inicio) * 1000)
		if not valida:
			raise RuntimeError("Falló una verificación durante el mini-benchmark.")

	return {
		"cantidad": cantidad,
		"algoritmo": firmante.nombre_algoritmo,
		"emision_promedio_ms": round(mean(tiempos_emision), 3),
		"emision_maximo_ms": round(max(tiempos_emision), 3),
		"verificacion_promedio_ms": round(mean(tiempos_verificacion), 3),
		"verificacion_maximo_ms": round(max(tiempos_verificacion), 3),
	}