"""Configuración central de DigiBlock."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
if APP_ENV not in {"local", "produccion"}:
	raise RuntimeError("APP_ENV debe ser 'local' o 'produccion'.")

if APP_ENV == "local":
	load_dotenv(BASE_DIR / ".env", override=False)

ADMIN_USER = os.getenv("ADMIN_USER", "universidad")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "Universidad Demo DigiBlock")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "digiblock.sqlite3")))

if APP_ENV == "local":
	ADMIN_PASSWORD = ADMIN_PASSWORD or "cambiar-antes-de-usar"
	SECRET_KEY = SECRET_KEY or "clave-local-solo-para-desarrollo"


def validar_configuracion(
	app_env: str | None = None,
	admin_password: str | None = None,
	secret_key: str | None = None,
) -> None:
	"""Rechaza secretos ausentes o inseguros antes de iniciar en producción."""
	entorno = (app_env or APP_ENV).strip().lower()
	if entorno not in {"local", "produccion"}:
		raise RuntimeError("APP_ENV debe ser 'local' o 'produccion'.")
	if entorno != "produccion":
		return

	contrasena = ADMIN_PASSWORD if admin_password is None else admin_password
	secreto = SECRET_KEY if secret_key is None else secret_key
	faltantes = []
	if not contrasena or contrasena == "cambiar-antes-de-usar":
		faltantes.append("ADMIN_PASSWORD")
	if not secreto or secreto == "clave-local-solo-para-desarrollo":
		faltantes.append("SECRET_KEY")
	if faltantes:
		variables = " y ".join(faltantes)
		raise RuntimeError(
			f"Configuración de producción incompleta: define {variables} en el entorno."
		)