"""Servicios de emisión, consulta y revocación de certificados."""

import sqlite3
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from secrets import token_hex
from typing import Any

from app.config import BASE_URL, UNIVERSITY_NAME
from app.crypto.canonical import canonicalizar
from app.crypto.hashing import huella_documento
from app.crypto.keystore import KeyStore
from app.database import conectar
from app.services.ledger import registrar_evento

VERSION_ESQUEMA = "1.0"
CAMPOS_FIRMADOS = (
	"id",
	"estudiante_nombre",
	"estudiante_documento",
	"programa",
	"titulo",
	"fecha_expedicion",
	"universidad",
	"version_esquema",
)
CAMPOS_ENTRADA = (
	"estudiante_nombre",
	"estudiante_documento",
	"programa",
	"titulo",
	"fecha_expedicion",
)
LONGITUDES_MAXIMAS = {
	"estudiante_nombre": 120,
	"estudiante_documento": 40,
	"programa": 160,
	"titulo": 160,
}


@dataclass(frozen=True)
class Certificado:
	"""Representa un certificado persistido y su material de verificación."""

	id: str
	estudiante_nombre: str
	estudiante_documento: str
	programa: str
	titulo: str
	fecha_expedicion: str
	universidad: str
	version_esquema: str
	huella_sha256: str
	firma_hex: str
	algoritmo: str
	estado: str
	motivo_revocacion: str | None
	creado_en: str
	revocado_en: str | None
	url_verificacion: str


class CertificadoNoEncontradoError(LookupError):
	"""Indica que el código solicitado no existe."""


class CertificadoYaRevocadoError(ValueError):
	"""Indica que se intentó revocar de nuevo un certificado revocado."""


def _normalizar_texto(campo: str, valor: Any, longitud_maxima: int) -> str:
	"""Valida y normaliza un campo de texto de entrada."""
	if not isinstance(valor, str):
		raise ValueError(f"El campo {campo} debe ser texto.")
	normalizado = unicodedata.normalize("NFC", " ".join(valor.split()))
	if not normalizado:
		raise ValueError(f"El campo {campo} no puede estar vacío.")
	if len(normalizado) > longitud_maxima:
		raise ValueError(f"El campo {campo} supera {longitud_maxima} caracteres.")
	return normalizado


def _validar_datos(datos: Mapping[str, Any]) -> dict[str, str]:
	"""Valida los campos requeridos para emitir un certificado ficticio."""
	if not isinstance(datos, Mapping):
		raise ValueError("Los datos del certificado deben ser un objeto.")
	desconocidos = set(datos) - set(CAMPOS_ENTRADA)
	if desconocidos:
		raise ValueError(f"Campos no permitidos: {', '.join(sorted(desconocidos))}.")

	resultado = {
		campo: _normalizar_texto(campo, datos.get(campo), LONGITUDES_MAXIMAS[campo])
		for campo in LONGITUDES_MAXIMAS
	}
	fecha_texto = _normalizar_texto("fecha_expedicion", datos.get("fecha_expedicion"), 10)
	try:
		fecha = date.fromisoformat(fecha_texto)
	except ValueError as error:
		raise ValueError("La fecha de expedición debe usar el formato AAAA-MM-DD.") from error
	if fecha > datetime.now(timezone.utc).date():
		raise ValueError("La fecha de expedición no puede estar en el futuro.")
	resultado["fecha_expedicion"] = fecha.isoformat()
	return resultado


def _documento_firmado(certificado: Certificado) -> dict[str, str]:
	"""Extrae exclusivamente los campos cubiertos por la firma."""
	return {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}


def _desde_fila(fila: Mapping[str, Any]) -> Certificado:
	"""Convierte una fila SQLite a un objeto de dominio."""
	return Certificado(
		id=fila["id"],
		estudiante_nombre=fila["estudiante_nombre"],
		estudiante_documento=fila["estudiante_documento"],
		programa=fila["programa"],
		titulo=fila["titulo"],
		fecha_expedicion=fila["fecha_expedicion"],
		universidad=fila["universidad"],
		version_esquema=fila["version_esquema"],
		huella_sha256=fila["huella_sha256"],
		firma_hex=fila["firma_hex"],
		algoritmo=fila["algoritmo"],
		estado=fila["estado"],
		motivo_revocacion=fila["motivo_revocacion"],
		creado_en=fila["creado_en"],
		revocado_en=fila["revocado_en"],
		url_verificacion=f"{BASE_URL.rstrip('/')}/verificar/{fila['id']}",
	)


def emitir_certificado(
	datos: Mapping[str, Any],
	almacen_claves: KeyStore | None = None,
) -> Certificado:
	"""Valida, firma, almacena y registra un certificado académico."""
	datos_validados = _validar_datos(datos)
	almacen = almacen_claves if almacen_claves is not None else KeyStore()
	anio_actual = datetime.now(timezone.utc).year

	for _ in range(5):
		certificado_id = f"DGB-{anio_actual}-{token_hex(3).upper()}"
		documento = {
			"id": certificado_id,
			**datos_validados,
			"universidad": UNIVERSITY_NAME,
			"version_esquema": VERSION_ESQUEMA,
		}
		contenido = canonicalizar(documento)
		huella = huella_documento(documento)
		firma_hex = almacen.firmar_con_clave_universidad(contenido).hex()
		creado_en = datetime.now(timezone.utc).isoformat()

		try:
			with conectar() as conexion:
				conexion.execute(
					"""
					INSERT INTO certificados (
						id, estudiante_nombre, estudiante_documento, programa, titulo,
						fecha_expedicion, universidad, version_esquema, huella_sha256,
						firma_hex, algoritmo, estado, motivo_revocacion, creado_en,
						revocado_en
					) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'vigente', NULL, ?, NULL)
					""",
					(
						documento["id"],
						documento["estudiante_nombre"],
						documento["estudiante_documento"],
						documento["programa"],
						documento["titulo"],
						documento["fecha_expedicion"],
						documento["universidad"],
						documento["version_esquema"],
						huella,
						firma_hex,
						almacen.nombre_algoritmo,
						creado_en,
					),
				)
		except sqlite3.IntegrityError:
			if obtener_certificado(certificado_id) is not None:
				continue
			raise

		registrar_evento(certificado_id, "EMISION", "Certificado emitido.")
		certificado = obtener_certificado(certificado_id)
		if certificado is None:
			raise RuntimeError("El certificado emitido no pudo recuperarse de la base de datos.")
		return certificado

	raise RuntimeError("No fue posible generar un identificador único para el certificado.")


def obtener_certificado(certificado_id: str) -> Certificado | None:
	"""Recupera un certificado por su identificador."""
	with conectar() as conexion:
		fila = conexion.execute(
			"SELECT * FROM certificados WHERE id = ?",
			(certificado_id,),
		).fetchone()
	return _desde_fila(fila) if fila is not None else None


def listar_certificados() -> list[Certificado]:
	"""Devuelve los certificados en orden de emisión descendente."""
	with conectar() as conexion:
		filas = conexion.execute(
			"SELECT * FROM certificados ORDER BY creado_en DESC, id DESC"
		).fetchall()
	return [_desde_fila(fila) for fila in filas]


def revocar_certificado(certificado_id: str, motivo: str) -> Certificado:
	"""Revoca un certificado vigente y registra el motivo en trazabilidad."""
	motivo_normalizado = _normalizar_texto("motivo", motivo, 500)
	fecha_revocacion = datetime.now(timezone.utc).isoformat()

	with conectar() as conexion:
		conexion.execute("BEGIN IMMEDIATE")
		fila = conexion.execute(
			"SELECT * FROM certificados WHERE id = ?",
			(certificado_id,),
		).fetchone()
		if fila is None:
			raise CertificadoNoEncontradoError(
				f"No existe el certificado {certificado_id}."
			)
		if fila["estado"] == "revocado":
			raise CertificadoYaRevocadoError(
				f"El certificado {certificado_id} ya está revocado."
			)
		conexion.execute(
			"""
			UPDATE certificados
			SET estado = 'revocado', motivo_revocacion = ?, revocado_en = ?
			WHERE id = ?
			""",
			(motivo_normalizado, fecha_revocacion, certificado_id),
		)
		fila_actualizada = conexion.execute(
			"SELECT * FROM certificados WHERE id = ?",
			(certificado_id,),
		).fetchone()

	registrar_evento(
		certificado_id,
		"REVOCACION",
		f"Certificado revocado. Motivo: {motivo_normalizado}",
	)
	return _desde_fila(fila_actualizada)
