"""Conexiones y esquema SQLite de DigiBlock."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import DATABASE_PATH


def _ruta_base_datos(ruta: str | Path | None = None) -> Path:
	"""Resuelve la ruta solicitada o la configurada para el proyecto."""
	return Path(ruta) if ruta is not None else DATABASE_PATH


@contextmanager
def conectar(ruta: str | Path | None = None) -> Iterator[sqlite3.Connection]:
	"""Abre una conexión SQLite y garantiza commit, rollback y cierre."""
	ruta_resuelta = _ruta_base_datos(ruta)
	ruta_resuelta.parent.mkdir(parents=True, exist_ok=True)
	conexion = sqlite3.connect(ruta_resuelta, timeout=5.0)
	conexion.row_factory = sqlite3.Row
	conexion.execute("PRAGMA foreign_keys = ON")
	conexion.execute("PRAGMA busy_timeout = 5000")
	try:
		yield conexion
		conexion.commit()
	except Exception:
		conexion.rollback()
		raise
	finally:
		conexion.close()


def init_db(ruta: str | Path | None = None) -> None:
	"""Crea las tablas e índices sin borrar datos existentes."""
	with conectar(ruta) as conexion:
		conexion.executescript(
			"""
			CREATE TABLE IF NOT EXISTS certificados (
				id TEXT PRIMARY KEY,
				estudiante_nombre TEXT NOT NULL,
				estudiante_documento TEXT NOT NULL,
				programa TEXT NOT NULL,
				titulo TEXT NOT NULL,
				fecha_expedicion TEXT NOT NULL,
				universidad TEXT NOT NULL,
				version_esquema TEXT NOT NULL,
				huella_sha256 TEXT NOT NULL,
				firma_hex TEXT NOT NULL,
				algoritmo TEXT NOT NULL,
				estado TEXT NOT NULL DEFAULT 'vigente'
					CHECK (estado IN ('vigente', 'revocado')),
				motivo_revocacion TEXT,
				creado_en TEXT NOT NULL,
				revocado_en TEXT
			);

			CREATE TABLE IF NOT EXISTS eventos (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				certificado_id TEXT NOT NULL,
				tipo TEXT NOT NULL CHECK (
					tipo IN (
						'EMISION',
						'VERIFICACION',
						'REVOCACION',
						'ALTERACION_DETECTADA'
					)
				),
				detalle TEXT NOT NULL,
				marca_tiempo TEXT NOT NULL,
				hash_previo TEXT NOT NULL,
				hash_evento TEXT NOT NULL
			);

			CREATE INDEX IF NOT EXISTS idx_eventos_certificado_id
				ON eventos (certificado_id, id);
			"""
		)
