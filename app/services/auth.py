"""Autenticación de la universidad y limitación de intentos."""

import hashlib
import hmac
import threading
import time
from dataclasses import dataclass

from app.config import ADMIN_PASSWORD, ADMIN_USER, SECRET_KEY

MAX_INTENTOS = 5
DURACION_BLOQUEO_SEGUNDOS = 60
_SAL_SCRYPT = hashlib.sha256(f"digiblock:{SECRET_KEY}".encode("utf-8")).digest()[:16]
_BLOQUEO = threading.Lock()


@dataclass
class _EstadoIntentos:
	"""Estado temporal de fallos para un cliente."""

	fallos: int = 0
	bloqueado_hasta: float = 0.0


class CredencialesInvalidasError(Exception):
	"""Indica que el usuario o la contraseña son incorrectos."""


class AccesoTemporalmenteBloqueadoError(Exception):
	"""Indica que el cliente debe esperar antes de volver a intentar."""

	def __init__(self, segundos_restantes: int) -> None:
		self.segundos_restantes = segundos_restantes
		super().__init__("Demasiados intentos fallidos; vuelva a intentarlo más tarde.")


_intentos: dict[str, _EstadoIntentos] = {}


def _hash_contrasena(contrasena: str) -> bytes:
	"""Deriva una clave de contraseña con scrypt y una sal de configuración."""
	return hashlib.scrypt(
		contrasena.encode("utf-8"),
		salt=_SAL_SCRYPT,
		n=2**14,
		r=8,
		p=1,
		dklen=32,
	)


def _credenciales_validas(usuario: str, contrasena: str) -> bool:
	"""Compara usuario y hashes sin comparación de cadenas en tiempo variable."""
	usuario_valido = hmac.compare_digest(
		usuario.encode("utf-8"),
		ADMIN_USER.encode("utf-8"),
	)
	contrasena_valida = hmac.compare_digest(
		_hash_contrasena(contrasena),
		_hash_contrasena(ADMIN_PASSWORD),
	)
	return usuario_valido & contrasena_valida


def autenticar(usuario: str, contrasena: str, identificador: str = "local") -> None:
	"""Valida credenciales y bloquea temporalmente tras varios fallos."""
	ahora = time.monotonic()
	with _BLOQUEO:
		estado = _intentos.get(identificador)
		if estado is not None and estado.bloqueado_hasta > ahora:
			restantes = max(1, int(estado.bloqueado_hasta - ahora + 0.999))
			raise AccesoTemporalmenteBloqueadoError(restantes)
		if estado is not None and estado.bloqueado_hasta:
			_intentos.pop(identificador, None)
			estado = None

		if _credenciales_validas(usuario, contrasena):
			_intentos.pop(identificador, None)
			return

		estado = _intentos.setdefault(identificador, _EstadoIntentos())
		estado.fallos += 1
		if estado.fallos >= MAX_INTENTOS:
			estado.bloqueado_hasta = ahora + DURACION_BLOQUEO_SEGUNDOS
		raise CredencialesInvalidasError("Usuario o contraseña incorrectos.")


def limpiar_intentos() -> None:
	"""Limpia el limitador; se usa en pruebas y al reiniciar la aplicación."""
	with _BLOQUEO:
		_intentos.clear()
