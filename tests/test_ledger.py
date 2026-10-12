"""Pruebas del registro de trazabilidad encadenado."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import app.database as database
from app.services.ledger import HASH_GENESIS, listar_eventos, registrar_evento, verificar_cadena


def _registrar_cinco_eventos() -> None:
	"""Crea una cadena de cinco eventos de demostración."""
	for numero in range(1, 6):
		registrar_evento(
			f"DGB-2026-{numero:06d}",
			"EMISION" if numero == 1 else "VERIFICACION",
			f"Evento ficticio {numero}",
		)


def test_cadena_de_cinco_eventos_es_valida(ruta_base_datos: Path) -> None:
	"""Una cadena intacta valida sus cinco registros."""
	_registrar_cinco_eventos()

	assert verificar_cadena() == {"valida": True, "total": 5, "primer_error": None}


def test_detecta_detalle_modificado(ruta_base_datos: Path) -> None:
	"""Cambiar un detalle invalida el hash de ese evento."""
	_registrar_cinco_eventos()
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE eventos SET detalle = ? WHERE id = ?",
			("detalle manipulado", 3),
		)

	resultado = verificar_cadena()

	assert resultado == {"valida": False, "total": 5, "primer_error": 3}


def test_detecta_eliminacion_de_evento_intermedio(ruta_base_datos: Path) -> None:
	"""El enlace del evento siguiente revela que falta el evento intermedio."""
	_registrar_cinco_eventos()
	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute("DELETE FROM eventos WHERE id = ?", (3,))

	resultado = verificar_cadena()

	assert resultado == {"valida": False, "total": 4, "primer_error": 4}


def test_usa_hash_genesis_en_el_primer_evento(ruta_base_datos: Path) -> None:
	"""El primer registro enlaza el valor génesis de 64 ceros."""
	registrar_evento("DGB-2026-ABC123", "EMISION", "Emisión de prueba")
	with database.conectar(ruta_base_datos) as conexion:
		evento = conexion.execute(
			"SELECT hash_previo FROM eventos WHERE id = ?",
			(1,),
		).fetchone()

	assert HASH_GENESIS == "0" * 64
	assert evento["hash_previo"] == HASH_GENESIS


def test_marca_de_tiempo_esta_en_utc(ruta_base_datos: Path) -> None:
	"""Cada marca de tiempo contiene una zona horaria UTC explícita."""
	evento = registrar_evento("DGB-2026-ABC123", "EMISION", "Emisión de prueba")
	marca = datetime.fromisoformat(evento["marca_tiempo"])

	assert marca.tzinfo is not None
	assert marca.utcoffset() == timedelta(0)


def test_filtro_de_certificado_no_permite_inyeccion_sql(ruta_base_datos: Path) -> None:
	"""El identificador malicioso se trata como un valor literal."""
	registrar_evento("CERTIFICADO-REAL", "EMISION", "Evento ficticio")

	assert listar_eventos(10, "' OR 1=1 --") == []
	assert len(listar_eventos(10, "CERTIFICADO-REAL")) == 1


def test_init_db_repetida_preserva_los_datos(ruta_base_datos: Path) -> None:
	"""Inicializar varias veces no duplica ni elimina eventos."""
	registrar_evento("DGB-2026-ABC123", "EMISION", "Emisión de prueba")

	database.init_db(ruta_base_datos)
	database.init_db()

	assert len(listar_eventos(10)) == 1


@pytest.mark.parametrize("limite", [-1, 1.5, True])
def test_limite_invalido_se_rechaza(ruta_base_datos: Path, limite: object) -> None:
	"""Un límite inválido no se envía directamente a SQLite."""
	with pytest.raises(ValueError, match="límite"):
		listar_eventos(limite)  # type: ignore[arg-type]
