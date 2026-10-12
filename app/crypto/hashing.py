"""Funciones SHA-256 para datos y documentos canónicos."""

import hashlib
from typing import Any

from app.crypto.canonical import canonicalizar


def sha256_hex(datos: bytes) -> str:
	"""Devuelve el resumen SHA-256 de los bytes recibidos en hexadecimal."""
	return hashlib.sha256(datos).hexdigest()


def huella_documento(documento: dict[str, Any]) -> str:
	"""Calcula la huella SHA-256 de la serialización canónica."""
	return sha256_hex(canonicalizar(documento))
