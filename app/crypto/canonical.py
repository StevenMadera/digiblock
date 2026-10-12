"""Serialización determinista de documentos para firma y huella."""

import json
import unicodedata
from typing import Any


def _normalizar_valor(valor: Any) -> Any:
	"""Normaliza texto y estructuras contenidas en un documento."""
	if isinstance(valor, str):
		texto = unicodedata.normalize("NFC", valor)
		return " ".join(texto.split())
	if isinstance(valor, list):
		return [_normalizar_valor(elemento) for elemento in valor]
	if isinstance(valor, tuple):
		return [_normalizar_valor(elemento) for elemento in valor]
	if isinstance(valor, dict):
		return _normalizar_diccionario(valor)
	return valor


def _normalizar_diccionario(documento: dict[str, Any]) -> dict[str, Any]:
	"""Normaliza las claves y los valores de un diccionario."""
	resultado: dict[str, Any] = {}
	for clave, valor in documento.items():
		if not isinstance(clave, str):
			raise TypeError("Las claves del documento deben ser texto.")
		clave_normalizada = unicodedata.normalize("NFC", clave)
		if clave_normalizada in resultado:
			raise ValueError("La normalización produjo claves duplicadas.")
		resultado[clave_normalizada] = _normalizar_valor(valor)
	return resultado


def canonicalizar(documento: dict[str, Any]) -> bytes:
	"""Convierte un documento en JSON UTF-8 canónico y normalizado."""
	if not isinstance(documento, dict):
		raise TypeError("El documento debe ser un diccionario.")

	texto = json.dumps(
		_normalizar_diccionario(documento),
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
		allow_nan=False,
	)
	return texto.encode("utf-8")
