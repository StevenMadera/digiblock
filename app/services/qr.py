"""Generación local de códigos QR para enlaces de verificación."""

import base64
from io import BytesIO

import qrcode


def generar_qr(url: str) -> tuple[bytes, str]:
	"""Devuelve el PNG del QR y su representación base64."""
	if not isinstance(url, str) or not url.strip():
		raise ValueError("La URL para el código QR no puede estar vacía.")
	imagen = qrcode.make(url)
	buffer = BytesIO()
	imagen.save(buffer, format="PNG")
	contenido = buffer.getvalue()
	return contenido, base64.b64encode(contenido).decode("ascii")
