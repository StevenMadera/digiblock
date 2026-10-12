"""Verificación criptográfica y control del estado de certificados."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.crypto.canonical import canonicalizar
from app.crypto.hashing import huella_documento
from app.crypto.keystore import KeyStore
from app.crypto.signer import Ed25519Signer, MLDSASigner, Signer
from app.services.certificates import (
	CAMPOS_FIRMADOS,
	Certificado,
	obtener_certificado,
)
from app.services.ledger import registrar_evento


@dataclass(frozen=True)
class ResultadoVerificacion:
	"""Resultado legible de una verificación criptográfica."""

	estado: str
	mensaje_humano: str
	detalles: dict[str, bool]
	algoritmo: str | None
	huella_calculada: str | None
	huella_registrada: str | None
	tiempo_ms: float


def _documento_de_certificado(certificado: Certificado) -> dict[str, str]:
	"""Reconstruye solo los campos que fueron firmados al emitir."""
	return {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}


def _firmante_para_algoritmo(algoritmo: str) -> Signer | None:
	"""Selecciona el verificador asociado al algoritmo registrado."""
	if algoritmo == MLDSASigner.nombre_algoritmo:
		return MLDSASigner()
	if algoritmo == Ed25519Signer.nombre_algoritmo:
		return Ed25519Signer()
	return None


def _registrar_resultado(certificado_id: str, estado: str) -> None:
	"""Añade los eventos de verificación y, si aplica, de alteración."""
	registrar_evento(
		certificado_id,
		"VERIFICACION",
		f"Resultado de verificación: {estado}.",
	)
	if estado == "ALTERADO":
		registrar_evento(
			certificado_id,
			"ALTERACION_DETECTADA",
			"La huella o la firma del documento no coincide.",
		)


def _resultado_no_encontrado(certificado_id: str, inicio: float) -> ResultadoVerificacion:
	"""Crea el resultado para un código que no figura en el registro."""
	_registrar_resultado(certificado_id, "NO_ENCONTRADO")
	return ResultadoVerificacion(
		estado="NO_ENCONTRADO",
		mensaje_humano="NO ENCONTRADO: el código no existe en el registro.",
		detalles={
			"huella_coincide": False,
			"firma_valida": False,
			"estado_vigente": False,
		},
		algoritmo=None,
		huella_calculada=None,
		huella_registrada=None,
		tiempo_ms=round((perf_counter() - inicio) * 1000, 3),
	)


def _evaluar_documento(
	certificado: Certificado,
	documento: dict[str, Any],
	firma_hex: str,
	almacen_claves: KeyStore,
	inicio: float,
) -> ResultadoVerificacion:
	"""Aplica huella, firma y estado en el orden de prioridad definido."""
	try:
		huella_calculada: str | None = huella_documento(documento)
	except (TypeError, ValueError):
		huella_calculada = None
	huella_coincide = huella_calculada == certificado.huella_sha256

	firmante = _firmante_para_algoritmo(certificado.algoritmo)
	firma_valida = False
	if firmante is not None and isinstance(firma_hex, str):
		try:
			firma = bytes.fromhex(firma_hex)
			firma_valida = firmante.verificar(
				canonicalizar(documento),
				firma,
				almacen_claves.obtener_clave_publica(),
			)
		except (TypeError, ValueError):
			firma_valida = False

	estado_vigente = certificado.estado == "vigente"
	if not huella_coincide or not firma_valida:
		estado = "ALTERADO"
		mensaje = "DOCUMENTO ALTERADO: la huella o la firma no coincide."
	elif not estado_vigente:
		estado = "REVOCADO"
		mensaje = "CERTIFICADO REVOCADO: la firma es válida, pero fue revocado."
	else:
		estado = "VALIDO"
		mensaje = "AUTÉNTICO Y VIGENTE: la huella y la firma son válidas."

	_registrar_resultado(certificado.id, estado)
	return ResultadoVerificacion(
		estado=estado,
		mensaje_humano=mensaje,
		detalles={
			"huella_coincide": huella_coincide,
			"firma_valida": firma_valida,
			"estado_vigente": estado_vigente,
		},
		algoritmo=certificado.algoritmo,
		huella_calculada=huella_calculada,
		huella_registrada=certificado.huella_sha256,
		tiempo_ms=round((perf_counter() - inicio) * 1000, 3),
	)


def verificar_por_codigo(
	certificado_id: str,
	almacen_claves: KeyStore | None = None,
) -> ResultadoVerificacion:
	"""Verifica el contenido registrado, la firma y la vigencia del código."""
	inicio = perf_counter()
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		return _resultado_no_encontrado(certificado_id, inicio)
	almacen = almacen_claves if almacen_claves is not None else KeyStore()
	return _evaluar_documento(
		certificado,
		_documento_de_certificado(certificado),
		certificado.firma_hex,
		almacen,
		inicio,
	)


def verificar_documento_presentado(
	documento: dict[str, Any],
	firma_hex: str,
	almacen_claves: KeyStore | None = None,
) -> ResultadoVerificacion:
	"""Verifica un documento aportado frente al registro y la clave pública."""
	inicio = perf_counter()
	if not isinstance(documento, dict):
		raise ValueError("El documento presentado debe ser un objeto.")
	certificado_id = documento.get("id")
	if not isinstance(certificado_id, str) or not certificado_id:
		return _resultado_no_encontrado(str(certificado_id or ""), inicio)
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		return _resultado_no_encontrado(certificado_id, inicio)
	almacen = almacen_claves if almacen_claves is not None else KeyStore()
	return _evaluar_documento(certificado, documento, firma_hex, almacen, inicio)
