"""Adaptadores de firma ML-DSA-65 y Ed25519."""

from abc import ABC, abstractmethod

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
	Ed25519PrivateKey,
	Ed25519PublicKey,
)
from dilithium_py.ml_dsa import ML_DSA_65


class Signer(ABC):
	"""Interfaz común para los algoritmos de firma del prototipo."""

	nombre_algoritmo: str

	@abstractmethod
	def generar_claves(self) -> tuple[bytes, bytes]:
		"""Genera claves y devuelve primero la pública y luego la privada."""

	@abstractmethod
	def cargar_clave_privada(self, clave_privada: bytes) -> None:
		"""Carga internamente una clave privada para firmar."""

	@abstractmethod
	def firmar(self, mensaje: bytes) -> bytes:
		"""Firma un mensaje con la clave privada cargada."""

	@abstractmethod
	def verificar(self, mensaje: bytes, firma: bytes, clave_publica: bytes) -> bool:
		"""Verifica una firma sin propagar errores de entrada inválida."""


class MLDSASigner(Signer):
	"""Firmante ML-DSA-65 de la implementación educativa dilithium-py."""

	nombre_algoritmo = "ML-DSA-65"

	def __init__(self) -> None:
		self._clave_privada: bytes | None = None

	def generar_claves(self) -> tuple[bytes, bytes]:
		"""Genera un par ML-DSA-65 y conserva la clave privada internamente."""
		clave_publica, clave_privada = ML_DSA_65.keygen()
		self._clave_privada = clave_privada
		return clave_publica, clave_privada

	def cargar_clave_privada(self, clave_privada: bytes) -> None:
		"""Carga la clave privada ML-DSA-65 sin incluirla en representaciones."""
		if not isinstance(clave_privada, bytes) or not clave_privada:
			raise ValueError("La clave privada ML-DSA-65 no es válida.")
		self._clave_privada = clave_privada

	def firmar(self, mensaje: bytes) -> bytes:
		"""Firma el mensaje con la clave privada cargada."""
		if self._clave_privada is None:
			raise RuntimeError("Primero debe generarse o cargarse una clave privada.")
		return ML_DSA_65.sign(self._clave_privada, mensaje)

	def verificar(self, mensaje: bytes, firma: bytes, clave_publica: bytes) -> bool:
		"""Verifica ML-DSA-65 y devuelve falso ante entradas inválidas."""
		try:
			return bool(ML_DSA_65.verify(clave_publica, mensaje, firma))
		except Exception:
			return False


class Ed25519Signer(Signer):
	"""Firmante Ed25519 clásico para comparación en el laboratorio."""

	nombre_algoritmo = "Ed25519"

	def __init__(self) -> None:
		self._clave_privada: bytes | None = None

	def generar_claves(self) -> tuple[bytes, bytes]:
		"""Genera claves Ed25519 codificadas en formato raw."""
		clave = Ed25519PrivateKey.generate()
		clave_privada = clave.private_bytes(
			encoding=serialization.Encoding.Raw,
			format=serialization.PrivateFormat.Raw,
			encryption_algorithm=serialization.NoEncryption(),
		)
		clave_publica = clave.public_key().public_bytes(
			encoding=serialization.Encoding.Raw,
			format=serialization.PublicFormat.Raw,
		)
		self._clave_privada = clave_privada
		return clave_publica, clave_privada

	def cargar_clave_privada(self, clave_privada: bytes) -> None:
		"""Valida y carga una clave privada Ed25519 raw."""
		try:
			Ed25519PrivateKey.from_private_bytes(clave_privada)
		except (TypeError, ValueError) as error:
			raise ValueError("La clave privada Ed25519 no es válida.") from error
		self._clave_privada = clave_privada

	def firmar(self, mensaje: bytes) -> bytes:
		"""Firma el mensaje con la clave privada Ed25519 cargada."""
		if self._clave_privada is None:
			raise RuntimeError("Primero debe generarse o cargarse una clave privada.")
		clave = Ed25519PrivateKey.from_private_bytes(self._clave_privada)
		return clave.sign(mensaje)

	def verificar(self, mensaje: bytes, firma: bytes, clave_publica: bytes) -> bool:
		"""Verifica Ed25519 y devuelve falso ante firmas o claves inválidas."""
		try:
			clave = Ed25519PublicKey.from_public_bytes(clave_publica)
			clave.verify(firma, mensaje)
			return True
		except (InvalidSignature, TypeError, ValueError):
			return False
