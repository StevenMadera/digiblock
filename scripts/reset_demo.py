"""Reinicia la base y las claves locales antes de volver a sembrar la demo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import BASE_DIR
from app.crypto.keystore import KeyStore
import app.database as database
from scripts.seed_demo import sembrar_demo


def reiniciar_demo(directorio_claves: str | Path | None = None) -> dict[str, int]:
	"""Elimina solo la base y archivos de claves DigiBlock, y carga cinco ficticios."""
	ruta_bd = Path(database.DATABASE_PATH)
	for ruta in (ruta_bd, Path(f"{ruta_bd}-wal"), Path(f"{ruta_bd}-shm")):
		if ruta.is_file():
			ruta.unlink()

	ruta_claves = Path(directorio_claves) if directorio_claves is not None else BASE_DIR / "keys"
	if ruta_claves.is_dir():
		for patron in ("universidad_*_privada.bin", "universidad_*_publica.bin"):
			for archivo in ruta_claves.glob(patron):
				archivo.unlink()

	database.init_db()
	almacen = KeyStore(ruta_claves)
	return sembrar_demo(almacen)


def main() -> None:
	"""Ejecuta el reinicio de demostración desde la línea de comandos."""
	resultado = reiniciar_demo()
	print(f"Demo reiniciada: {resultado['creados']} certificados ficticios cargados.")


if __name__ == "__main__":
	main()
