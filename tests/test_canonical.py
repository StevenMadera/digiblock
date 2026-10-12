"""Pruebas de serialización canónica de certificados."""

import unicodedata

from app.crypto.canonical import canonicalizar


def test_el_orden_de_claves_no_cambia_los_bytes(documento_demo: dict[str, str]) -> None:
	"""Ordenar las mismas claves debe producir bytes idénticos."""
	documento_invertido = dict(reversed(list(documento_demo.items())))

	assert canonicalizar(documento_demo) == canonicalizar(documento_invertido)


def test_un_caracter_distinto_cambia_los_bytes(documento_demo: dict[str, str]) -> None:
	"""Un cambio de contenido debe cambiar la serialización."""
	alterado = dict(documento_demo, titulo="Ingeniero de Sistemas")

	assert canonicalizar(documento_demo) != canonicalizar(alterado)


def test_los_acentos_y_la_enie_se_conservan(documento_demo: dict[str, str]) -> None:
	"""La salida UTF-8 conserva caracteres españoles legibles."""
	serializado = canonicalizar(documento_demo)

	assert "María José Muñoz".encode("utf-8") in serializado


def test_normaliza_unicode_y_espacios(documento_demo: dict[str, str]) -> None:
	"""NFC y espacios repetidos no crean documentos distintos."""
	equivalente = dict(documento_demo)
	equivalente["estudiante_nombre"] = unicodedata.normalize(
		"NFD", "  María   José Muñoz  "
	)

	assert canonicalizar(documento_demo) == canonicalizar(equivalente)
