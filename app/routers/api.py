"""Endpoints JSON públicos y de administración universitaria."""

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.crypto.keystore import KeyStore
from app.database import conectar
from app.services.auth import (
	AccesoTemporalmenteBloqueadoError,
	CredencialesInvalidasError,
	autenticar,
)
from app.services.certificates import (
	CAMPOS_FIRMADOS,
	Certificado,
	CertificadoNoEncontradoError,
	CertificadoYaRevocadoError,
	emitir_certificado,
	listar_certificados,
	obtener_certificado,
	revocar_certificado,
)
from app.services.diff import AVISO_ANALISIS_COMPLEMENTARIO, Cambio, comparar, puntaje_riesgo
from app.services.ledger import listar_eventos, verificar_cadena
from app.services.laboratory import reiniciar_datos_demo, restaurar_alteracion, simular_alteracion
from app.services.qr import generar_qr
from app.services.verification import (
	ResultadoVerificacion,
	verificar_documento_presentado,
	verificar_por_codigo,
)

router = APIRouter(prefix="/api", tags=["api"])


class EntradaLogin(BaseModel):
	"""Credenciales de acceso de la universidad."""

	model_config = ConfigDict(extra="forbid")

	usuario: str = Field(min_length=1, max_length=80)
	contrasena: str = Field(min_length=1, max_length=256)


class EntradaCertificado(BaseModel):
	"""Campos editables al emitir un certificado."""

	model_config = ConfigDict(extra="forbid")

	estudiante_nombre: str = Field(min_length=1, max_length=120)
	estudiante_documento: str = Field(min_length=1, max_length=40)
	programa: str = Field(min_length=1, max_length=160)
	titulo: str = Field(min_length=1, max_length=160)
	fecha_expedicion: str = Field(min_length=10, max_length=10)


class EntradaRevocacion(BaseModel):
	"""Motivo de revocación enviado por la universidad."""

	model_config = ConfigDict(extra="forbid")

	motivo: str = Field(min_length=1, max_length=500)


class EntradaAlteracionLaboratorio(BaseModel):
	"""Campo permitido para una alteración didáctica protegida."""

	model_config = ConfigDict(extra="forbid")

	certificado_id: str = Field(min_length=1, max_length=64)
	campo: Literal["estudiante_nombre", "fecha_expedicion"] = "estudiante_nombre"


class EntradaRestauracionLaboratorio(BaseModel):
	"""Identificador del certificado cuya simulación se restaurará."""

	model_config = ConfigDict(extra="forbid")

	certificado_id: str = Field(min_length=1, max_length=64)


class EntradaVerificacionDocumento(BaseModel):
	"""Documento y firma aportados para una verificación pública."""

	model_config = ConfigDict(extra="forbid")

	documento: dict[str, Any] | None = None
	firma_hex: str = Field(min_length=1, max_length=20_000)
	huella_sha256: str | None = Field(default=None, max_length=64)
	algoritmo: str | None = Field(default=None, max_length=80)
	clave_publica_hex: str | None = Field(default=None, max_length=10_000)
	id: str | None = Field(default=None, max_length=64)
	estudiante_nombre: str | None = Field(default=None, max_length=120)
	estudiante_documento: str | None = Field(default=None, max_length=40)
	programa: str | None = Field(default=None, max_length=160)
	titulo: str | None = Field(default=None, max_length=160)
	fecha_expedicion: str | None = Field(default=None, max_length=10)
	universidad: str | None = Field(default=None, max_length=160)
	version_esquema: str | None = Field(default=None, max_length=20)

	@model_validator(mode="after")
	def validar_documento_plano(self) -> "EntradaVerificacionDocumento":
		"""Exige un objeto anidado o todos los campos del certificado plano."""
		if self.documento is None:
			faltantes = [
				campo
				for campo in CAMPOS_FIRMADOS
				if getattr(self, campo) is None
			]
			if faltantes:
				raise ValueError("El documento plano debe incluir todos los campos firmados.")
		return self


def exigir_sesion_universidad(request: Request) -> str:
	"""Exige una sesión firmada de la universidad."""
	usuario = request.session.get("usuario")
	if not isinstance(usuario, str):
		raise HTTPException(status_code=401, detail="Se requiere una sesión universitaria.")
	return usuario


def _documento_certificado(certificado: Certificado) -> dict[str, str]:
	"""Construye el documento con exactamente los campos firmados."""
	return {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}


def _certificado_publico(certificado: Certificado) -> dict[str, Any]:
	"""Devuelve datos públicos sin número de documento ni firma."""
	return {
		"id": certificado.id,
		"estudiante_nombre": certificado.estudiante_nombre,
		"programa": certificado.programa,
		"titulo": certificado.titulo,
		"fecha_expedicion": certificado.fecha_expedicion,
		"universidad": certificado.universidad,
		"version_esquema": certificado.version_esquema,
		"huella_sha256": certificado.huella_sha256,
		"algoritmo": certificado.algoritmo,
		"estado": certificado.estado,
		"url_verificacion": certificado.url_verificacion,
	}


def _resultado_a_dict(resultado: ResultadoVerificacion) -> dict[str, Any]:
	"""Serializa un resultado de verificación como JSON."""
	return asdict(resultado)


@router.post("/login")
def iniciar_sesion(entrada: EntradaLogin, request: Request) -> dict[str, Any]:
	"""Valida credenciales y establece la sesión firmada."""
	identificador = request.client.host if request.client is not None else "desconocido"
	try:
		autenticar(entrada.usuario, entrada.contrasena, identificador)
	except AccesoTemporalmenteBloqueadoError as error:
		raise HTTPException(
			status_code=429,
			detail=str(error),
			headers={"Retry-After": str(error.segundos_restantes)},
		) from error
	except CredencialesInvalidasError as error:
		raise HTTPException(status_code=401, detail=str(error)) from error

	request.session.clear()
	request.session["usuario"] = entrada.usuario
	return {"autenticado": True, "usuario": entrada.usuario}


@router.post("/logout")
def cerrar_sesion(request: Request) -> dict[str, bool]:
	"""Elimina la sesión actual."""
	request.session.clear()
	return {"autenticado": False}


@router.post("/certificados", status_code=status.HTTP_201_CREATED)
def crear_certificado(
	entrada: EntradaCertificado,
	_: str = Depends(exigir_sesion_universidad),
) -> dict[str, Any]:
	"""Emite un certificado; solo la universidad puede usar esta ruta."""
	try:
		certificado = emitir_certificado(entrada.model_dump())
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error
	return asdict(certificado)


@router.get("/certificados")
def obtener_certificados(
	_: str = Depends(exigir_sesion_universidad),
) -> list[dict[str, Any]]:
	"""Lista certificados para la universidad autenticada."""
	return [asdict(certificado) for certificado in listar_certificados()]


@router.get("/certificados/{certificado_id}/qr.png")
def obtener_qr(certificado_id: str) -> Response:
	"""Devuelve el código QR público de verificación."""
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		raise HTTPException(status_code=404, detail="Certificado no encontrado.")
	png, _ = generar_qr(certificado.url_verificacion)
	return Response(content=png, media_type="image/png")


@router.get("/certificados/{certificado_id}/descarga")
def descargar_certificado(certificado_id: str) -> dict[str, Any]:
	"""Descarga el documento firmado y la clave pública verificadora."""
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		raise HTTPException(status_code=404, detail="Certificado no encontrado.")
	return {
		"documento": _documento_certificado(certificado),
		"huella_sha256": certificado.huella_sha256,
		"firma_hex": certificado.firma_hex,
		"algoritmo": certificado.algoritmo,
		"clave_publica_hex": KeyStore().obtener_clave_publica().hex(),
	}


@router.get("/certificados/{certificado_id}")
def consultar_certificado(certificado_id: str) -> dict[str, Any]:
	"""Consulta la ficha pública mínima de un certificado."""
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		raise HTTPException(status_code=404, detail="Certificado no encontrado.")
	return _certificado_publico(certificado)


@router.post("/certificados/{certificado_id}/revocar")
def revocar(
	certificado_id: str,
	entrada: EntradaRevocacion,
	_: str = Depends(exigir_sesion_universidad),
) -> dict[str, Any]:
	"""Revoca un certificado; solo la universidad puede usar esta ruta."""
	try:
		certificado = revocar_certificado(certificado_id, entrada.motivo)
	except CertificadoNoEncontradoError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except CertificadoYaRevocadoError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error
	return asdict(certificado)


@router.get("/verificar/{certificado_id}")
def verificar(certificado_id: str) -> dict[str, Any]:
	"""Verifica públicamente la huella, firma y vigencia de un código."""
	return _resultado_a_dict(verificar_por_codigo(certificado_id))


@router.post("/verificar-documento")
def verificar_documento(entrada: EntradaVerificacionDocumento) -> dict[str, Any]:
	"""Verifica una descarga JSON y adjunta un diff solo explicativo."""
	if entrada.documento is not None:
		documento = entrada.documento
	else:
		documento = {
			campo: getattr(entrada, campo)
			for campo in CAMPOS_FIRMADOS
		}
	resultado = verificar_documento_presentado(documento, entrada.firma_hex)
	certificado_id = documento.get("id")
	certificado = (
		obtener_certificado(certificado_id)
		if isinstance(certificado_id, str)
		else None
	)
	if certificado is None:
		cambios: list[Cambio] = []
	else:
		original = _documento_certificado(certificado)
		cambios = comparar(original, documento)
	return {
		**_resultado_a_dict(resultado),
		"cambios": [asdict(cambio) for cambio in cambios],
		"puntaje_riesgo": puntaje_riesgo(cambios),
		"aviso_analisis": AVISO_ANALISIS_COMPLEMENTARIO,
	}


@router.get("/trazabilidad")
def obtener_trazabilidad(
	limite: int = 100,
	certificado_id: str | None = None,
) -> dict[str, Any]:
	"""Lista los eventos recientes del registro simulado."""
	try:
		eventos = listar_eventos(limite, certificado_id)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error
	return {"eventos": eventos, "simulacion": True}


@router.get("/trazabilidad/verificar-cadena")
def comprobar_cadena() -> dict[str, Any]:
	"""Comprueba la integridad del registro de trazabilidad local."""
	return verificar_cadena()


@router.post("/laboratorio/alterar")
def alterar_en_laboratorio(
	entrada: EntradaAlteracionLaboratorio,
	_: str = Depends(exigir_sesion_universidad),
) -> dict[str, str]:
	"""Simula una alteración; solo una sesión universitaria puede ejecutarla."""
	try:
		simular_alteracion(entrada.certificado_id, entrada.campo)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error
	return {
		"certificado_id": entrada.certificado_id,
		"campo": entrada.campo,
		"estado": "ALTERACION_SIMULADA",
	}


@router.post("/laboratorio/restaurar")
def restaurar_desde_laboratorio(
	entrada: EntradaRestauracionLaboratorio,
	_: str = Depends(exigir_sesion_universidad),
) -> dict[str, str]:
	"""Restaura una alteración didáctica bajo sesión universitaria."""
	try:
		restaurar_alteracion(entrada.certificado_id)
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error
	return {"certificado_id": entrada.certificado_id, "estado": "RESTAURADO"}


@router.post("/demo/reiniciar")
def reiniciar_registros_demo(
	_: str = Depends(exigir_sesion_universidad),
) -> dict[str, Any]:
	"""Limpia certificados y eventos sin borrar las claves del almacén."""
	return {"certificados_eliminados": reiniciar_datos_demo(), "claves_preservadas": True}


@router.get("/clave-publica")
def obtener_clave_publica() -> dict[str, str]:
	"""Publica solo la clave verificadora y el nombre del algoritmo."""
	almacen = KeyStore()
	return {
		"algoritmo": almacen.nombre_algoritmo,
		"clave_publica_hex": almacen.obtener_clave_publica().hex(),
	}


@router.get("/estadisticas")
def obtener_estadisticas() -> dict[str, Any]:
	"""Devuelve contadores y eventos recientes sin exponer claves privadas."""
	with conectar() as conexion:
		certificados = conexion.execute("SELECT COUNT(*) FROM certificados").fetchone()[0]
		revocados = conexion.execute(
			"SELECT COUNT(*) FROM certificados WHERE estado = ?",
			("revocado",),
		).fetchone()[0]
		verificaciones = conexion.execute(
			"SELECT COUNT(*) FROM eventos WHERE tipo = ?",
			("VERIFICACION",),
		).fetchone()[0]
	return {
		"certificados_emitidos": certificados,
		"verificaciones_realizadas": verificaciones,
		"revocados": revocados,
		"eventos_recientes": listar_eventos(10),
	}
