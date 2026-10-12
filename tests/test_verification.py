"""Pruebas de estados de verificación y del análisis complementario."""

from pathlib import Path

import pytest

import app.database as database
from app.crypto.hashing import huella_documento
from app.services.certificates import (
	CAMPOS_FIRMADOS,
	emitir_certificado,
	revocar_certificado,
)
from app.services.diff import comparar, puntaje_riesgo
from app.services.ledger import listar_eventos
from app.services.verification import (
	verificar_documento_presentado,
	verificar_por_codigo,
)


def test_certificado_recién_emitido_es_valido(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Un certificado intacto pasa hash, firma y vigencia."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "VALIDO"
	assert resultado.detalles == {
		"huella_coincide": True,
		"firma_valida": True,
		"estado_vigente": True,
	}


def test_codigo_inexistente_es_no_encontrado(ruta_base_datos: Path) -> None:
	"""Un código no registrado produce NO_ENCONTRADO y deja trazabilidad."""
	resultado = verificar_por_codigo("DGB-2026-FFFFFF")

	assert resultado.estado == "NO_ENCONTRADO"
	assert listar_eventos(10, "DGB-2026-FFFFFF")[0]["tipo"] == "VERIFICACION"


def test_nombre_alterado_en_base_es_detectado(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Cambiar el nombre sin actualizar la huella produce ALTERADO."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET estudiante_nombre = ? WHERE id = ?",
			("Nombre Alterado", certificado.id),
		)

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["huella_coincide"] is False
	assert listar_eventos(10, certificado.id)[0]["tipo"] == "ALTERACION_DETECTADA"


def test_fecha_alterada_en_base_es_detectada(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Cambiar la fecha de expedición rompe la huella y la firma."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET fecha_expedicion = ? WHERE id = ?",
			("2026-01-01", certificado.id),
		)

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["huella_coincide"] is False


def test_atacante_que_actualiza_la_huella_no_puede_falsificar_firma(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Una huella coherente con el dato manipulado no sustituye la firma."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	documento = {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}
	documento["estudiante_nombre"] = "Nombre Alterado"
	nueva_huella = huella_documento(documento)
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"""
			UPDATE certificados
			SET estudiante_nombre = ?, huella_sha256 = ?
			WHERE id = ?
			""",
			("Nombre Alterado", nueva_huella, certificado.id),
		)

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["huella_coincide"] is True
	assert resultado.detalles["firma_valida"] is False


def test_firma_modificada_es_detectada(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Una firma almacenada inválida produce ALTERADO aunque la huella coincida."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET firma_hex = ? WHERE id = ?",
			("00", certificado.id),
		)

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["huella_coincide"] is True
	assert resultado.detalles["firma_valida"] is False


def test_revocado_con_firma_valida_se_reporta_revocado(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""La revocación no invalida la firma, pero sí cambia el estado final."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	revocar_certificado(certificado.id, "Revocación ficticia")

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "REVOCADO"
	assert resultado.detalles["firma_valida"] is True
	assert resultado.detalles["estado_vigente"] is False


def test_alterado_y_revocado_prioriza_alterado(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""La alteración tiene prioridad sobre la revocación."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET titulo = ? WHERE id = ?",
			("Título Alterado", certificado.id),
		)
	revocar_certificado(certificado.id, "Revocación ficticia")

	resultado = verificar_por_codigo(certificado.id, almacen_claves)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["estado_vigente"] is False


def test_documento_presentado_alterado_falla_con_firma_original(
	datos_emision_demo: dict[str, str], ruta_base_datos: Path, almacen_claves
) -> None:
	"""Un archivo alterado no verifica con la firma descargada originalmente."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	documento = {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}
	documento["estudiante_nombre"] = "Nombre Alterado"
	resultado = verificar_documento_presentado(
		documento,
		certificado.firma_hex,
		almacen_claves,
	)

	assert resultado.estado == "ALTERADO"
	assert resultado.detalles["huella_coincide"] is False
	assert resultado.detalles["firma_valida"] is False


def test_diff_informa_exactamente_los_campos_cambiados() -> None:
	"""La comparación complementaria lista solo los campos distintos."""
	original = {"estudiante_nombre": "Nombre Original", "programa": "Sistemas"}
	presentado = {"estudiante_nombre": "Nombre Alterado", "programa": "Sistemas"}
	cambios = comparar(original, presentado)

	assert [(cambio.campo, cambio.valor_original, cambio.valor_presentado) for cambio in cambios] == [
		("estudiante_nombre", "Nombre Original", "Nombre Alterado")
	]
	assert puntaje_riesgo(cambios) > 0
	assert comparar(original, original) == []
