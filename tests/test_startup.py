"""Pruebas del arranque autónomo con almacenamiento aislado."""

from pathlib import Path

import app.database as database
from app.crypto.keystore import KeyStore
from app.main import inicializar_entorno
from app.services.certificates import listar_certificados
from app.services.ledger import listar_eventos, verificar_cadena


def _usar_directorios_temporales(
	tmp_path: Path,
	monkeypatch,
) -> tuple[Path, Path]:
	"""Configura las rutas locales del proceso de prueba bajo tmp_path."""
	directorio_datos = tmp_path / "data"
	directorio_claves = tmp_path / "keys"
	monkeypatch.setattr(database, "DATABASE_PATH", directorio_datos / "digiblock.sqlite3")
	return directorio_datos, directorio_claves


def test_arranque_crea_carpetas_db_claves_y_seed(
	tmp_path: Path,
	monkeypatch,
) -> None:
	"""Un arranque desde cero crea directorios, ML-DSA y cinco certificados."""
	directorio_datos, directorio_claves = _usar_directorios_temporales(
		tmp_path,
		monkeypatch,
	)
	assert not directorio_datos.exists()
	assert not directorio_claves.exists()

	resultado = inicializar_entorno(directorio_datos, directorio_claves)

	assert directorio_datos.is_dir()
	assert directorio_claves.is_dir()
	assert (directorio_claves / "universidad_ml_dsa_65_privada.bin").is_file()
	assert (directorio_claves / "universidad_ml_dsa_65_publica.bin").is_file()
	assert len(listar_certificados()) == 5
	assert resultado["creados"] == 5
	assert verificar_cadena()["valida"] is True


def test_arranque_repetido_es_idempotente(
	tmp_path: Path,
	monkeypatch,
) -> None:
	"""Un segundo arranque conserva claves, certificados y eventos."""
	directorio_datos, directorio_claves = _usar_directorios_temporales(
		tmp_path,
		monkeypatch,
	)
	inicializar_entorno(directorio_datos, directorio_claves)
	clave_publica_inicial = KeyStore(directorio_claves).obtener_clave_publica()
	eventos_iniciales = len(listar_eventos(100))

	resultado_segundo = inicializar_entorno(directorio_datos, directorio_claves)

	assert resultado_segundo == {
		"creados": 0,
		"ya_existian": 5,
		"verificaciones_creadas": 0,
	}
	assert len(listar_certificados()) == 5
	assert len(listar_eventos(100)) == eventos_iniciales
	assert KeyStore(directorio_claves).obtener_clave_publica() == clave_publica_inicial


def test_arranque_no_completa_seed_si_base_ya_tiene_certificado(
	tmp_path: Path,
	monkeypatch,
) -> None:
	"""Una base no vacía no se rellena con los certificados demo faltantes."""
	directorio_datos, directorio_claves = _usar_directorios_temporales(
		tmp_path,
		monkeypatch,
	)
	inicializar_entorno(directorio_datos, directorio_claves)
	with database.conectar() as conexion:
		conexion.execute(
			"DELETE FROM certificados WHERE estudiante_documento <> ?",
			("DEMO-DOC-0001",),
		)

	resultado = inicializar_entorno(directorio_datos, directorio_claves)

	assert resultado == {
		"creados": 0,
		"ya_existian": 1,
		"verificaciones_creadas": 0,
	}
	assert len(listar_certificados()) == 1