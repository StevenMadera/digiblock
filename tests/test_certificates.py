"""Pruebas de emisión y revocación de certificados."""

import base64
from datetime import datetime, timedelta, timezone

import pytest

from app.services.certificates import (
	CertificadoNoEncontradoError,
	CertificadoYaRevocadoError,
	emitir_certificado,
	listar_certificados,
	obtener_certificado,
	revocar_certificado,
)
from app.services.qr import generar_qr


def test_emite_certificado_firmado_y_con_url(
	datos_emision_demo: dict[str, str], ruta_base_datos, almacen_claves
) -> None:
	"""La emisión produce un código, una huella, una firma y una URL."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)

	assert certificado.id.startswith("DGB-")
	assert len(certificado.huella_sha256) == 64
	assert certificado.firma_hex
	assert certificado.algoritmo == "ML-DSA-65"
	assert certificado.estado == "vigente"
	assert certificado.url_verificacion.endswith(f"/verificar/{certificado.id}")


def test_rechaza_campo_requerido_vacio(
	datos_emision_demo: dict[str, str], almacen_claves
) -> None:
	"""Los campos obligatorios vacíos no se emiten."""
	datos = dict(datos_emision_demo, estudiante_nombre="   ")

	with pytest.raises(ValueError, match="no puede estar vacío"):
		emitir_certificado(datos, almacen_claves)


def test_rechaza_fecha_futura(datos_emision_demo: dict[str, str], almacen_claves) -> None:
	"""No se acepta una fecha de expedición posterior a hoy."""
	datos = dict(datos_emision_demo)
	hoy_utc = datetime.now(timezone.utc).date()
	datos["fecha_expedicion"] = (hoy_utc + timedelta(days=2)).isoformat()

	with pytest.raises(ValueError, match="futuro"):
		emitir_certificado(datos, almacen_claves)


def test_dos_emisiones_generan_codigos_distintos(
	datos_emision_demo: dict[str, str], ruta_base_datos, almacen_claves
) -> None:
	"""Cada emisión recibe un identificador distinto."""
	primero = emitir_certificado(datos_emision_demo, almacen_claves)
	segundo = emitir_certificado(datos_emision_demo, almacen_claves)

	assert primero.id != segundo.id
	assert len(listar_certificados()) == 2
	assert obtener_certificado(primero.id) == primero


def test_revocar_actualiza_estado_y_registra_fecha(
	datos_emision_demo: dict[str, str], ruta_base_datos, almacen_claves
) -> None:
	"""La revocación conserva el certificado y registra motivo y fecha."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	revocado = revocar_certificado(certificado.id, "Corrección administrativa ficticia")

	assert revocado.estado == "revocado"
	assert revocado.motivo_revocacion == "Corrección administrativa ficticia"
	assert revocado.revocado_en is not None
	assert obtener_certificado(certificado.id) == revocado


def test_revocar_id_inexistente_devuelve_error_claro(ruta_base_datos, almacen_claves) -> None:
	"""La revocación de un código inexistente tiene un error específico."""
	with pytest.raises(CertificadoNoEncontradoError, match="No existe"):
		revocar_certificado("DGB-2026-FFFFFF", "Motivo ficticio")


def test_revocar_dos_veces_devuelve_error_claro(
	datos_emision_demo: dict[str, str], ruta_base_datos, almacen_claves
) -> None:
	"""Una segunda revocación no duplica el evento ni modifica el registro."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	revocar_certificado(certificado.id, "Primera revocación ficticia")

	with pytest.raises(CertificadoYaRevocadoError, match="ya está revocado"):
		revocar_certificado(certificado.id, "Segunda revocación ficticia")


def test_qr_devuelve_png_y_base64(
	datos_emision_demo: dict[str, str], ruta_base_datos, almacen_claves
) -> None:
	"""El QR generado contiene un PNG decodificable."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	png, contenido_base64 = generar_qr(certificado.url_verificacion)

	assert png.startswith(b"\x89PNG\r\n\x1a\n")
	assert base64.b64decode(contenido_base64) == png
