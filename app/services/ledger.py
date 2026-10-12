"""Registro de trazabilidad encadenado por hashes."""

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.database import conectar

HASH_GENESIS = "0" * 64
TIPOS_EVENTO = {
	"EMISION",
	"VERIFICACION",
	"REVOCACION",
	"ALTERACION_DETECTADA",
}


def _hash_evento(
	hash_previo: str,
	certificado_id: str,
	tipo: str,
	detalle: str,
	marca_tiempo: str,
) -> str:
	"""Calcula el SHA-256 encadenado de los campos de un evento."""
	contenido = "".join((hash_previo, certificado_id, tipo, detalle, marca_tiempo))
	return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def registrar_evento(certificado_id: str, tipo: str, detalle: str) -> dict[str, Any]:
	"""Añade un evento enlazado con el último hash almacenado."""
	if tipo not in TIPOS_EVENTO:
		raise ValueError(f"Tipo de evento no permitido: {tipo}")

	marca_tiempo = datetime.now(timezone.utc).isoformat()
	with conectar() as conexion:
		conexion.execute("BEGIN IMMEDIATE")
		anterior = conexion.execute(
			"SELECT hash_evento FROM eventos ORDER BY id DESC LIMIT 1"
		).fetchone()
		hash_previo = anterior["hash_evento"] if anterior is not None else HASH_GENESIS
		hash_actual = _hash_evento(
			hash_previo,
			certificado_id,
			tipo,
			detalle,
			marca_tiempo,
		)
		cursor = conexion.execute(
			"""
			INSERT INTO eventos (
				certificado_id, tipo, detalle, marca_tiempo, hash_previo, hash_evento
			) VALUES (?, ?, ?, ?, ?, ?)
			""",
			(certificado_id, tipo, detalle, marca_tiempo, hash_previo, hash_actual),
		)
		evento_id = cursor.lastrowid

	return {
		"id": evento_id,
		"certificado_id": certificado_id,
		"tipo": tipo,
		"detalle": detalle,
		"marca_tiempo": marca_tiempo,
		"hash_previo": hash_previo,
		"hash_evento": hash_actual,
	}


def verificar_cadena() -> dict[str, Any]:
	"""Comprueba enlaces y hashes y devuelve el primer evento inconsistente."""
	with conectar() as conexion:
		eventos = conexion.execute(
			"""
			SELECT id, certificado_id, tipo, detalle, marca_tiempo,
				   hash_previo, hash_evento
			FROM eventos
			ORDER BY id ASC
			"""
		).fetchall()

	hash_anterior = HASH_GENESIS
	primer_error: int | None = None
	for evento in eventos:
		hash_calculado = _hash_evento(
			evento["hash_previo"],
			evento["certificado_id"],
			evento["tipo"],
			evento["detalle"],
			evento["marca_tiempo"],
		)
		if evento["hash_previo"] != hash_anterior or hash_calculado != evento["hash_evento"]:
			primer_error = evento["id"]
			break
		hash_anterior = evento["hash_evento"]

	return {
		"valida": primer_error is None,
		"total": len(eventos),
		"primer_error": primer_error,
	}


def listar_eventos(limite: int, certificado_id: str | None = None) -> list[dict[str, Any]]:
	"""Lista eventos recientes usando parámetros SQL para todos los valores."""
	if not isinstance(limite, int) or isinstance(limite, bool) or limite < 0:
		raise ValueError("El límite debe ser un entero mayor o igual a cero.")

	with conectar() as conexion:
		if certificado_id is None:
			eventos = conexion.execute(
				"SELECT * FROM eventos ORDER BY id DESC LIMIT ?",
				(limite,),
			).fetchall()
		else:
			eventos = conexion.execute(
				"""
				SELECT * FROM eventos
				WHERE certificado_id = ?
				ORDER BY id DESC
				LIMIT ?
				""",
				(certificado_id, limite),
			).fetchall()
	return [dict(evento) for evento in eventos]
