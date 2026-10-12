"""Pruebas de las funciones SHA-256."""

from app.crypto.hashing import huella_documento, sha256_hex


def test_vector_sha256_conocido() -> None:
	"""Comprueba el vector estándar SHA-256 para abc."""
	assert sha256_hex(b"abc") == (
		"ba7816bf8f01cfea414140de5dae2223"
		"b00361a396177a9cb410ff61f20015ad"
	)


def test_huella_tiene_64_digitos_hexadecimales(documento_demo: dict[str, str]) -> None:
	"""La huella de un documento es un SHA-256 hexadecimal."""
	huella = huella_documento(documento_demo)

	assert len(huella) == 64
	assert all(caracter in "0123456789abcdef" for caracter in huella)


def test_huella_es_determinista(documento_demo: dict[str, str]) -> None:
	"""El mismo documento canónico siempre produce la misma huella."""
	assert huella_documento(documento_demo) == huella_documento(documento_demo)


def test_cambio_de_un_caracter_cambia_la_huella(documento_demo: dict[str, str]) -> None:
	"""Un cambio mínimo modifica ampliamente el resumen criptográfico."""
	alterado = dict(documento_demo, titulo="Ingeniero de Sistemas")
	original = huella_documento(documento_demo)
	modificada = huella_documento(alterado)
	bits_distintos = (int(original, 16) ^ int(modificada, 16)).bit_count()

	assert original != modificada
	assert bits_distintos > 96
