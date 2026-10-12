"""Páginas HTML de DigiBlock renderizadas con Jinja2."""

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from jinja2 import select_autoescape
from starlette.templating import Jinja2Templates

from app.config import BASE_DIR
from app.crypto.canonical import canonicalizar
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
from app.services.diff import AVISO_ANALISIS_COMPLEMENTARIO, comparar
from app.services.laboratory import (
	ejecutar_mini_benchmark,
	medir_comparacion_firmas,
	reiniciar_datos_demo,
	restaurar_alteracion,
	simular_alteracion,
)
from app.services.ledger import listar_eventos, verificar_cadena
from app.services.qr import generar_qr
from app.services.verification import (
	ResultadoVerificacion,
	verificar_documento_presentado,
	verificar_por_codigo,
)

router = APIRouter()
plantillas = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
plantillas.env.autoescape = select_autoescape(
	enabled_extensions=("html", "xml"),
	default_for_string=True,
)


def _contexto(
	request: Request,
	titulo: str,
	seccion: str,
	**valores: Any,
) -> dict[str, Any]:
	"""Construye el contexto común de las plantillas."""
	return {"request": request, "titulo": titulo, "seccion": seccion, **valores}


def _renderizar(
	request: Request,
	plantilla: str,
	titulo: str,
	seccion: str,
	status_code: int = 200,
	**valores: Any,
) -> Response:
	"""Renderiza una plantilla con escape automático habilitado."""
	return plantillas.TemplateResponse(
		request=request,
		name=plantilla,
		context=_contexto(request, titulo, seccion, **valores),
		status_code=status_code,
	)


def _autorizado(request: Request) -> bool:
	"""Indica si la sesión firmada corresponde a la universidad."""
	return isinstance(request.session.get("usuario"), str)


def _redirigir_login(destino: str) -> RedirectResponse:
	"""Redirige a login sin permitir destinos externos."""
	return RedirectResponse(f"/login?next={quote(destino)}", status_code=303)


def _resultado_contexto(resultado: ResultadoVerificacion) -> dict[str, Any]:
	"""Adapta el resultado criptográfico para su representación visual."""
	clases = {
		"VALIDO": ("estado--valido", "✓"),
		"ALTERADO": ("estado--alterado", "!"),
		"REVOCADO": ("estado--revocado", "↻"),
		"NO_ENCONTRADO": ("estado--desconocido", "?"),
	}
	clase, simbolo = clases[resultado.estado]
	return {"resultado": resultado, "estado_clase": clase, "estado_simbolo": simbolo}


def _datos_firmados(certificado: Certificado) -> dict[str, str]:
	"""Obtiene solo los campos incorporados en la firma del certificado."""
	return {campo: getattr(certificado, campo) for campo in CAMPOS_FIRMADOS}


def _medir_avalancha() -> dict[str, Any]:
	"""Prepara dos textos ficticios y su diferencia de bits SHA-256."""
	texto_original = "Ingeniera de Sistemas"
	texto_alterado = "Ingeniera de sistemaS"
	hash_original = sha256(texto_original.encode("utf-8")).hexdigest()
	hash_alterado = sha256(texto_alterado.encode("utf-8")).hexdigest()
	bits_distintos = sum(
		(binario_a ^ binario_b).bit_count()
		for binario_a, binario_b in zip(bytes.fromhex(hash_original), bytes.fromhex(hash_alterado))
	)
	return {
		"texto_original": texto_original,
		"texto_alterado": texto_alterado,
		"hash_original": hash_original,
		"hash_alterado": hash_alterado,
		"bits_distintos": bits_distintos,
		"porcentaje_bits_distintos": round(bits_distintos / 256 * 100, 2),
	}


def _eventos_dashboard() -> tuple[dict[str, int], list[dict[str, Any]], dict[str, Any]]:
	"""Consulta contadores, eventos recientes e integridad de la trazabilidad."""
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
	return (
		{
			"certificados": certificados,
			"verificaciones": verificaciones,
			"revocados": revocados,
		},
		listar_eventos(8),
		verificar_cadena(),
	)


@router.get("/", name="inicio")
def inicio(request: Request) -> Response:
	"""Muestra el tablero operativo y el estado del registro."""
	estadisticas, eventos, cadena = _eventos_dashboard()
	total = max(estadisticas["certificados"], estadisticas["verificaciones"], 1)
	return _renderizar(
		request,
		"dashboard.html",
		"Resumen",
		"Resumen",
		estadisticas=estadisticas,
		eventos=eventos,
		cadena=cadena,
		porcentaje_emisiones=round(estadisticas["certificados"] / total * 100),
		porcentaje_verificaciones=round(estadisticas["verificaciones"] / total * 100),
	)


@router.get("/login", name="login")
def pagina_login(request: Request, next: str = "/") -> Response:
	"""Presenta el formulario de acceso de la universidad."""
	if _autorizado(request):
		return RedirectResponse("/", status_code=303)
	return _renderizar(request, "login.html", "Acceso", "Acceso", next=next)


@router.post("/login", name="procesar_login")
def procesar_login(
	request: Request,
	usuario: str = Form(...),
	contrasena: str = Form(...),
	next: str = Form("/"),
) -> Response:
	"""Valida credenciales y guarda solo el nombre en la cookie firmada."""
	identificador = request.client.host if request.client is not None else "desconocido"
	try:
		autenticar(usuario, contrasena, identificador)
	except AccesoTemporalmenteBloqueadoError as error:
		return _renderizar(
			request,
			"login.html",
			"Acceso",
			"Acceso",
			status_code=429,
			error=str(error),
			next=next,
		)
	except CredencialesInvalidasError as error:
		return _renderizar(
			request,
			"login.html",
			"Acceso",
			"Acceso",
			status_code=401,
			error=str(error),
			next=next,
		)

	request.session.clear()
	request.session["usuario"] = usuario
	destino = next if next.startswith("/") and not next.startswith("//") else "/"
	return RedirectResponse(destino, status_code=303)


@router.post("/logout", name="logout")
def cerrar_sesion(request: Request) -> RedirectResponse:
	"""Cierra la sesión de la universidad."""
	request.session.clear()
	return RedirectResponse("/", status_code=303)


@router.get("/emitir", name="emitir")
def pagina_emision(request: Request) -> Response:
	"""Muestra el formulario protegido de emisión."""
	if not _autorizado(request):
		return _redirigir_login("/emitir")
	return _renderizar(
		request,
		"emitir.html",
		"Emitir certificado",
		"Emisión",
		fecha_hoy=datetime.now(timezone.utc).date().isoformat(),
	)


@router.post("/emitir", name="procesar_emision")
def procesar_emision(
	request: Request,
	estudiante_nombre: str = Form(...),
	estudiante_documento: str = Form(...),
	programa: str = Form(...),
	titulo: str = Form(...),
	fecha_expedicion: str = Form(...),
) -> Response:
	"""Emite y muestra un diploma con QR tras validar la sesión."""
	if not _autorizado(request):
		return _redirigir_login("/emitir")
	datos = {
		"estudiante_nombre": estudiante_nombre,
		"estudiante_documento": estudiante_documento,
		"programa": programa,
		"titulo": titulo,
		"fecha_expedicion": fecha_expedicion,
	}
	try:
		certificado = emitir_certificado(datos)
	except ValueError as error:
		return _renderizar(
			request,
			"emitir.html",
			"Emitir certificado",
			"Emisión",
			status_code=422,
			error=str(error),
			fecha_hoy=datetime.now(timezone.utc).date().isoformat(),
			datos=datos,
		)
	png, qr_base64 = generar_qr(certificado.url_verificacion)
	return _renderizar(
		request,
		"emitir.html",
		"Certificado emitido",
		"Emisión",
		certificado=certificado,
		qr_base64=qr_base64,
		qr_png=png,
	)


@router.get("/certificado/{certificado_id}", name="certificado")
def pagina_certificado(request: Request, certificado_id: str) -> Response:
	"""Presenta la vista pública del estudiante con QR y estado actualizado."""
	certificado = obtener_certificado(certificado_id)
	if certificado is None:
		raise HTTPException(status_code=404, detail="No se encontró ese certificado.")
	resultado = verificar_por_codigo(certificado_id)
	_, qr_base64 = generar_qr(certificado.url_verificacion)
	return _renderizar(
		request,
		"certificado.html",
		"Certificado digital",
		"Certificados",
		certificado=certificado,
		qr_base64=qr_base64,
		resultado=resultado,
		estado_clase=_resultado_contexto(resultado)["estado_clase"],
	)


@router.get("/verificar", name="verificar_formulario")
def pagina_verificacion(request: Request, codigo: str | None = None) -> Response:
	"""Muestra el formulario público y, si se indica, verifica un código."""
	resultado = verificar_por_codigo(codigo) if codigo else None
	contexto = _resultado_contexto(resultado) if resultado is not None else {}
	return _renderizar(
		request,
		"verificar.html",
		"Verificar certificado",
		"Verificación",
		codigo=codigo,
		cambios=[],
		aviso_analisis=AVISO_ANALISIS_COMPLEMENTARIO,
		**contexto,
	)


@router.get("/verificar/{certificado_id}", name="verificar_codigo")
def verificar_codigo(request: Request, certificado_id: str) -> Response:
	"""Verifica públicamente por código y muestra las comprobaciones."""
	resultado = verificar_por_codigo(certificado_id)
	return _renderizar(
		request,
		"verificar.html",
		"Resultado de verificación",
		"Verificación",
		codigo=certificado_id,
		cambios=[],
		aviso_analisis=AVISO_ANALISIS_COMPLEMENTARIO,
		**_resultado_contexto(resultado),
	)


@router.post("/verificar", name="procesar_verificacion")
async def procesar_verificacion(
	request: Request,
	codigo: str = Form(""),
	archivo: UploadFile | None = File(default=None),
) -> Response:
	"""Verifica por código o carga JSON sin confiar en análisis complementarios."""
	if archivo is not None and archivo.filename:
		contenido = await archivo.read(1_000_001)
		if len(contenido) > 1_000_000:
			raise HTTPException(status_code=413, detail="El archivo supera 1 MB.")
		try:
			presentado = json.loads(contenido.decode("utf-8"))
		except (UnicodeDecodeError, json.JSONDecodeError):
			return _renderizar(
				request,
				"verificar.html",
				"Verificar certificado",
				"Verificación",
				error="El archivo debe ser un JSON válido en UTF-8.",
				cambios=[],
			)
		if not isinstance(presentado, dict):
			return _renderizar(
				request,
				"verificar.html",
				"Verificar certificado",
				"Verificación",
				error="El contenido del archivo debe ser un objeto JSON.",
				cambios=[],
			)
		documento = presentado.get("documento", presentado)
		firma_hex = presentado.get("firma_hex", "")
		if not isinstance(documento, dict) or not isinstance(firma_hex, str):
			return _renderizar(
				request,
				"verificar.html",
				"Verificar certificado",
				"Verificación",
				error="El archivo no contiene un documento y una firma válidos.",
				cambios=[],
			)
		resultado = verificar_documento_presentado(documento, firma_hex)
		certificado = obtener_certificado(documento.get("id", ""))
		cambios = (
			comparar(_datos_firmados(certificado), documento)
			if certificado is not None
			else []
		)
		return _renderizar(
			request,
			"verificar.html",
			"Resultado de verificación",
			"Verificación",
			codigo=documento.get("id", ""),
			cambios=cambios,
			aviso_analisis=AVISO_ANALISIS_COMPLEMENTARIO,
			**_resultado_contexto(resultado),
		)

	if codigo.strip():
		return RedirectResponse(f"/verificar/{quote(codigo.strip())}", status_code=303)
	return _renderizar(
		request,
		"verificar.html",
		"Verificar certificado",
		"Verificación",
		error="Ingresa un código o selecciona un diploma JSON.",
		cambios=[],
	)


@router.get("/trazabilidad", name="trazabilidad")
def pagina_trazabilidad(
	request: Request,
	certificado_id: str | None = None,
	comprobar: bool = False,
) -> Response:
	"""Lista eventos y permite comprobar la cadena local."""
	eventos = listar_eventos(100, certificado_id)
	cadena = verificar_cadena() if comprobar else None
	return _renderizar(
		request,
		"trazabilidad.html",
		"Trazabilidad",
		"Trazabilidad",
		eventos=eventos,
		certificado_id=certificado_id or "",
		cadena=cadena,
	)


@router.get("/laboratorio", name="laboratorio")
def pagina_laboratorio(request: Request, mensaje: str | None = None) -> Response:
	"""Muestra las demostraciones de seguridad, solo para la universidad."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	return _renderizar_laboratorio(request, mensaje=mensaje)


def _renderizar_laboratorio(
	request: Request,
	mensaje: str | None = None,
	error: str | None = None,
	benchmark: dict[str, Any] | None = None,
) -> Response:
	"""Construye las mediciones y datos del laboratorio."""
	certificados = listar_certificados()
	mediciones = medir_comparacion_firmas()
	return _renderizar(
		request,
		"laboratorio.html",
		"Laboratorio de seguridad",
		"Laboratorio",
		certificados=certificados,
		mediciones=mediciones,
		avalancha=_medir_avalancha(),
		benchmark=benchmark,
		mensaje=mensaje,
		error=error,
	)


@router.post("/laboratorio/alterar", name="laboratorio_alterar")
def laboratorio_alterar(
	request: Request,
	certificado_id: str = Form(...),
	campo: str = Form("estudiante_nombre"),
) -> Response:
	"""Ejecuta una alteración identificada como simulación."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	try:
		simular_alteracion(certificado_id, campo)
	except (LookupError, ValueError) as error:
		return _renderizar_laboratorio(request, error=str(error))
	return RedirectResponse("/laboratorio?mensaje=Alteración+simulada", status_code=303)


@router.post("/laboratorio/restaurar", name="laboratorio_restaurar")
def laboratorio_restaurar(request: Request, certificado_id: str = Form(...)) -> Response:
	"""Restaura el valor anterior de la simulación activa."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	try:
		restaurar_alteracion(certificado_id)
	except ValueError as error:
		return _renderizar_laboratorio(request, error=str(error))
	return RedirectResponse("/laboratorio?mensaje=Certificado+restaurado", status_code=303)


@router.post("/laboratorio/revocar", name="laboratorio_revocar")
def laboratorio_revocar(
	request: Request,
	certificado_id: str = Form(...),
	motivo: str = Form(...),
	confirmacion: str = Form(""),
) -> Response:
	"""Revoca un certificado mediante el laboratorio universitario protegido."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	if confirmacion != "REVOCAR":
		return _renderizar_laboratorio(
			request,
			error="Confirma la revocación antes de continuar.",
		)
	try:
		revocar_certificado(certificado_id, motivo)
	except (CertificadoNoEncontradoError, CertificadoYaRevocadoError, ValueError) as error:
		return _renderizar_laboratorio(request, error=str(error))
	return RedirectResponse(
		"/laboratorio?mensaje=Certificado+revocado%3B+la+firma+se+conserva+v%C3%A1lida",
		status_code=303,
	)


@router.post("/laboratorio/benchmark", name="laboratorio_benchmark")
def laboratorio_benchmark(request: Request) -> Response:
	"""Ejecuta el mini-benchmark local de cincuenta operaciones."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	return _renderizar_laboratorio(request, benchmark=ejecutar_mini_benchmark(50))


@router.post("/laboratorio/reiniciar", name="laboratorio_reiniciar")
def laboratorio_reiniciar(
	request: Request,
	confirmacion: str = Form(""),
) -> Response:
	"""Reinicia registros de demostración tras confirmación explícita."""
	if not _autorizado(request):
		return _redirigir_login("/laboratorio")
	if confirmacion != "REINICIAR":
		return _renderizar_laboratorio(
			request,
			error="Confirma el reinicio para borrar certificados y eventos de demostración.",
		)
	cantidad = reiniciar_datos_demo()
	return RedirectResponse(
		f"/laboratorio?mensaje=Demo+reiniciada:+{cantidad}+certificados+eliminados",
		status_code=303,
	)


@router.get("/acerca", name="acerca")
def pagina_acerca(request: Request) -> Response:
	"""Explica alcance, limitaciones y arquitectura de DigiBlock."""
	return _renderizar(request, "acerca.html", "Alcance y limitaciones", "Acerca")