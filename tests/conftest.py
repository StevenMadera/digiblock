"""Fixtures compartidos para las pruebas de DigiBlock."""

import pytest
from pathlib import Path
from typing import Iterator

import app.database as database
import app.main as main
import app.routers.api as api
import app.services.auth as auth
import app.services.certificates as certificates
import app.services.verification as verification
from app.crypto.keystore import KeyStore
from app.main import app as aplicacion
from fastapi.testclient import TestClient


@pytest.fixture
def documento_demo() -> dict[str, str]:
	"""Devuelve un certificado ficticio con todos los campos firmados."""
	return {
		"id": "DGB-2026-ABC123",
		"estudiante_nombre": "María José Muñoz",
		"estudiante_documento": "DOC-000001",
		"programa": "Ingeniería de Sistemas",
		"titulo": "Ingeniera de Sistemas",
		"fecha_expedicion": "2026-06-15",
		"universidad": "Universidad Demo DigiBlock",
		"version_esquema": "1.0",
	}


@pytest.fixture
def datos_emision_demo(documento_demo: dict[str, str]) -> dict[str, str]:
	"""Devuelve solo los campos que puede enviar el formulario de emisión."""
	campos = (
		"estudiante_nombre",
		"estudiante_documento",
		"programa",
		"titulo",
		"fecha_expedicion",
	)
	return {campo: documento_demo[campo] for campo in campos}


@pytest.fixture
def ruta_base_datos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Aísla cada prueba en una base SQLite temporal."""
	ruta = tmp_path / "digiblock.sqlite3"
	monkeypatch.setattr(database, "DATABASE_PATH", ruta)
	database.init_db()
	return ruta


@pytest.fixture
def ruta_claves(tmp_path: Path) -> Path:
	"""Devuelve un directorio de claves temporal para cada prueba."""
	return tmp_path / "keys"


@pytest.fixture
def almacen_claves(ruta_claves: Path) -> KeyStore:
	"""Crea claves aisladas para no tocar las claves locales del prototipo."""
	return KeyStore(ruta_claves)


@pytest.fixture
def cliente_api(
	ruta_base_datos: Path,
	almacen_claves: KeyStore,
	monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
	"""Crea un cliente con base y claves aisladas y ejecuta el ciclo de vida."""
	monkeypatch.setattr(certificates, "KeyStore", lambda: almacen_claves)
	monkeypatch.setattr(verification, "KeyStore", lambda: almacen_claves)
	monkeypatch.setattr(api, "KeyStore", lambda: almacen_claves)
	monkeypatch.setattr(main, "inicializar_entorno", lambda **_: {})
	auth.limpiar_intentos()
	with TestClient(aplicacion) as cliente:
		yield cliente
	auth.limpiar_intentos()
