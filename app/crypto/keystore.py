"""Almacén local de claves de firma de la universidad."""

from pathlib import Path

from app.config import BASE_DIR
from app.crypto.signer import MLDSASigner, Signer


class KeyStore:
	"""Carga o genera claves locales sin exponer la clave privada.

	En producción, la clave privada debe residir en un HSM o gestor de secretos.
	"""

	def __init__(
		self,
		directorio: str | Path | None = None,
		firmante: Signer | None = None,
	) -> None:
		self._directorio = Path(directorio) if directorio is not None else BASE_DIR / "keys"
		self._firmante = firmante if firmante is not None else MLDSASigner()
		nombre_algoritmo = "".join(
			caracter.lower() if caracter.isalnum() else "_"
			for caracter in self._firmante.nombre_algoritmo
		).strip("_")
		self._ruta_clave_privada = self._directorio / f"universidad_{nombre_algoritmo}_privada.bin"
		self._ruta_clave_publica = self._directorio / f"universidad_{nombre_algoritmo}_publica.bin"
		self._clave_publica = b""
		self._cargar_o_generar()

	def _cargar_o_generar(self) -> None:
		"""Carga el par existente o crea uno si todavía no existe."""
		existe_privada = self._ruta_clave_privada.is_file()
		existe_publica = self._ruta_clave_publica.is_file()

		if existe_privada != existe_publica:
			raise RuntimeError("El par de claves está incompleto; revise el directorio keys.")

		if existe_privada:
			clave_privada = self._ruta_clave_privada.read_bytes()
			self._clave_publica = self._ruta_clave_publica.read_bytes()
			if not clave_privada or not self._clave_publica:
				raise RuntimeError("El par de claves almacenado está vacío o dañado.")
			self._firmante.cargar_clave_privada(clave_privada)
			return

		self._directorio.mkdir(parents=True, exist_ok=True)
		clave_publica, clave_privada = self._firmante.generar_claves()
		self._ruta_clave_privada.write_bytes(clave_privada)
		self._ruta_clave_publica.write_bytes(clave_publica)
		self._clave_publica = clave_publica

	def obtener_clave_publica(self) -> bytes:
		"""Devuelve la clave pública de la universidad."""
		return self._clave_publica

	@property
	def nombre_algoritmo(self) -> str:
		"""Devuelve el nombre del algoritmo sin exponer el firmante interno."""
		return self._firmante.nombre_algoritmo

	def firmar_con_clave_universidad(self, mensaje: bytes) -> bytes:
		"""Firma un mensaje sin devolver ni registrar la clave privada."""
		return self._firmante.firmar(mensaje)

	def __repr__(self) -> str:
		"""Describe el almacén sin incluir claves ni rutas sensibles."""
		return f"KeyStore(algoritmo={self._firmante.nombre_algoritmo!r})"
