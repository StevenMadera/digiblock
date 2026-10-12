"""Carga certificados ficticios de forma idempotente."""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crypto.keystore import KeyStore
from app.database import conectar, init_db
from app.services.certificates import emitir_certificado
from app.services.verification import verificar_por_codigo

ESTUDIANTES_FICTICIOS = (
	{
		"estudiante_nombre": "Lucía Ríos Demo",
		"estudiante_documento": "DEMO-DOC-0001",
		"programa": "Ingeniería de Sistemas",
		"titulo": "Ingeniera de Sistemas",
		"fecha_expedicion": "2025-06-12",
	},
	{
		"estudiante_nombre": "Mateo Salas Demo",
		"estudiante_documento": "DEMO-DOC-0002",
		"programa": "Administración de Empresas",
		"titulo": "Administrador de Empresas",
		"fecha_expedicion": "2025-07-03",
	},
	{
		"estudiante_nombre": "Valentina Pardo Demo",
		"estudiante_documento": "DEMO-DOC-0003",
		"programa": "Ingeniería Ambiental",
		"titulo": "Ingeniera Ambiental",
		"fecha_expedicion": "2025-08-21",
	},
	{
		"estudiante_nombre": "Nicolás Vega Demo",
		"estudiante_documento": "DEMO-DOC-0004",
		"programa": "Contaduría Pública",
		"titulo": "Contador Público",
		"fecha_expedicion": "2025-10-09",
	},
	{
		"estudiante_nombre": "Sara Méndez Demo",
		"estudiante_documento": "DEMO-DOC-0005",
		"programa": "Diseño Industrial",
		"titulo": "Diseñadora Industrial",
		"fecha_expedicion": "2025-11-14",
	},
)
DOCUMENTOS_A_VERIFICAR = {
	"DEMO-DOC-0001",
	"DEMO-DOC-0002",
	"DEMO-DOC-0003",
}


def sembrar_demo(almacen_claves: KeyStore | None = None) -> dict[str, int]:
	"""Crea cinco registros ficticios y algunas verificaciones una sola vez."""
	init_db()
	almacen = almacen_claves if almacen_claves is not None else KeyStore()
	creados = 0
	existentes = 0
	verificados = 0

	for datos in ESTUDIANTES_FICTICIOS:
		with conectar() as conexion:
			fila = conexion.execute(
				"SELECT id FROM certificados WHERE estudiante_documento = ?",
				(datos["estudiante_documento"],),
			).fetchone()
		if fila is None:
			certificado = emitir_certificado(datos, almacen)
			certificado_id = certificado.id
			creados += 1
		else:
			certificado_id = fila["id"]
			existentes += 1

		if datos["estudiante_documento"] not in DOCUMENTOS_A_VERIFICAR:
			continue
		with conectar() as conexion:
			evento = conexion.execute(
				"SELECT 1 FROM eventos WHERE certificado_id = ? AND tipo = ? LIMIT 1",
				(certificado_id, "VERIFICACION"),
			).fetchone()
		if evento is not None:
			continue
		verificar_por_codigo(certificado_id, almacen)
		verificados += 1

	return {"creados": creados, "ya_existian": existentes, "verificaciones_creadas": verificados}


def main() -> None:
	"""Ejecuta la carga idempotente desde la línea de comandos."""
	resultado: dict[str, Any] = sembrar_demo()
	print(
		"Seed de demostración: "
		f"{resultado['creados']} creados, "
		f"{resultado['ya_existian']} existentes, "
		f"{resultado['verificaciones_creadas']} verificaciones nuevas."
	)


if __name__ == "__main__":
	main()
