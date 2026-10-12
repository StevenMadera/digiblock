"""Comparación explicable de campos; no decide la validez criptográfica."""

from dataclasses import dataclass
from typing import Any

AVISO_ANALISIS_COMPLEMENTARIO = (
	"Análisis complementario; no sustituye la verificación criptográfica."
)
PESOS_RIESGO = {
	"estudiante_nombre": 25,
	"estudiante_documento": 35,
	"fecha_expedicion": 25,
	"universidad": 20,
	"id": 35,
	"titulo": 15,
	"programa": 10,
}


@dataclass(frozen=True)
class Cambio:
	"""Representa un campo cuyo valor difiere entre dos documentos."""

	campo: str
	valor_original: Any
	valor_presentado: Any


def comparar(original: dict[str, Any], presentado: dict[str, Any]) -> list[Cambio]:
	"""Devuelve diferencias ordenadas campo a campo entre dos documentos."""
	cambios: list[Cambio] = []
	for campo in sorted(set(original) | set(presentado)):
		valor_original = original.get(campo)
		valor_presentado = presentado.get(campo)
		if valor_original != valor_presentado:
			cambios.append(Cambio(campo, valor_original, valor_presentado))
	return cambios


def puntaje_riesgo(cambios: list[Cambio]) -> int:
	"""Calcula un puntaje explicable y acotado de 0 a 100."""
	return min(100, sum(PESOS_RIESGO.get(cambio.campo, 5) for cambio in cambios))
