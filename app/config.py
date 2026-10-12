"""Configuración central de DigiBlock."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ADMIN_USER = os.getenv("ADMIN_USER", "universidad")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "cambiar-antes-de-usar")
SECRET_KEY = os.getenv("SECRET_KEY", "clave-local-solo-para-desarrollo")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "Universidad Demo DigiBlock")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "digiblock.sqlite3")))