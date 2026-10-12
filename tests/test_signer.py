"""Pruebas de firmantes y del almacén de claves."""

import logging

import pytest

from app.crypto.keystore import KeyStore
from app.crypto.signer import Ed25519Signer, MLDSASigner, Signer


@pytest.mark.parametrize("tipo_firmante", [MLDSASigner, Ed25519Signer])
def test_firma_valida_y_falla_si_cambia_el_mensaje(tipo_firmante: type[Signer]) -> None:
	"""Cada algoritmo verifica su firma y rechaza otro mensaje."""
	firmante = tipo_firmante()
	clave_publica, _ = firmante.generar_claves()
	firma = firmante.firmar(b"certificado de prueba")

	assert firmante.verificar(b"certificado de prueba", firma, clave_publica)
	assert not firmante.verificar(b"certificado alterado", firma, clave_publica)


@pytest.mark.parametrize("tipo_firmante", [MLDSASigner, Ed25519Signer])
def test_rechaza_firma_alterada(tipo_firmante: type[Signer]) -> None:
	"""Modificar un byte de la firma invalida la verificación."""
	firmante = tipo_firmante()
	clave_publica, _ = firmante.generar_claves()
	firma = bytearray(firmante.firmar(b"mensaje"))
	firma[0] ^= 1

	assert not firmante.verificar(b"mensaje", bytes(firma), clave_publica)


@pytest.mark.parametrize("tipo_firmante", [MLDSASigner, Ed25519Signer])
def test_rechaza_clave_de_otro_par(tipo_firmante: type[Signer]) -> None:
	"""Una clave pública ajena no valida la firma original."""
	firmante = tipo_firmante()
	clave_publica, _ = firmante.generar_claves()
	firma = firmante.firmar(b"mensaje")
	otro_firmante = tipo_firmante()
	otra_clave_publica, _ = otro_firmante.generar_claves()

	assert clave_publica != otra_clave_publica
	assert not firmante.verificar(b"mensaje", firma, otra_clave_publica)


@pytest.mark.parametrize("tipo_firmante", [MLDSASigner, Ed25519Signer])
def test_firma_de_longitud_incorrecta_no_lanza_excepcion(
	tipo_firmante: type[Signer],
) -> None:
	"""Una firma truncada se informa como inválida sin propagar errores."""
	firmante = tipo_firmante()
	clave_publica, _ = firmante.generar_claves()

	assert firmante.verificar(b"mensaje", b"x", clave_publica) is False


def test_almacen_reutiliza_claves_y_no_expone_la_privada(
	tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
	"""Dos instancias comparten el par persistido sin revelar la clave privada."""
	with caplog.at_level(logging.DEBUG):
		primero = KeyStore(tmp_path, MLDSASigner())
		clave_publica = primero.obtener_clave_publica()
		firma = primero.firmar_con_clave_universidad(b"mensaje de prueba")
		segundo = KeyStore(tmp_path, MLDSASigner())
		firma_segunda_instancia = segundo.firmar_con_clave_universidad(
			b"mensaje segunda instancia"
		)

	ruta_privada = next(tmp_path.glob("*privada.bin"))
	clave_privada = ruta_privada.read_bytes()
	representacion_privada = repr(clave_privada)
	verificador = MLDSASigner()

	assert segundo.obtener_clave_publica() == clave_publica
	assert verificador.verificar(
		b"mensaje segunda instancia", firma_segunda_instancia, clave_publica
	)
	assert verificador.verificar(b"mensaje de prueba", firma, clave_publica)
	assert clave_privada.hex() not in repr(primero)
	assert representacion_privada not in repr(primero)
	assert clave_privada.hex() not in caplog.text
	assert representacion_privada not in caplog.text
