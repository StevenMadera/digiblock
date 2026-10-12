"""Punto de entrada de la aplicación web DigiBlock."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import BASE_DIR, SECRET_KEY
from app.database import init_db
from app.routers.api import router as api_router
from app.routers.web import plantillas, router as web_router

LIMITE_CUERPO_API_BYTES = 1_000_000


class LimiteCuerpoApi:
    """Rechaza cuerpos de API mayores al límite sin entregarlos a los routers."""

    def __init__(self, aplicacion: ASGIApp, limite_bytes: int = LIMITE_CUERPO_API_BYTES) -> None:
        self._aplicacion = aplicacion
        self._limite_bytes = limite_bytes

    async def __call__(self, alcance: Scope, recibir: Receive, enviar: Send) -> None:
        if (
            alcance["type"] != "http"
            or not alcance["path"].startswith("/api/")
            or alcance["method"] not in {"POST", "PUT", "PATCH"}
        ):
            await self._aplicacion(alcance, recibir, enviar)
            return

        cuerpo = bytearray()
        while True:
            mensaje = await recibir()
            if mensaje["type"] == "http.disconnect":
                return
            if mensaje["type"] != "http.request":
                continue
            cuerpo.extend(mensaje.get("body", b""))
            if len(cuerpo) > self._limite_bytes:
                contenido = '{"detail":"El cuerpo de la solicitud supera el límite permitido."}'.encode("utf-8")
                await enviar(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json; charset=utf-8"),
                            (b"content-length", str(len(contenido)).encode("ascii")),
                        ],
                    }
                )
                await enviar({"type": "http.response.body", "body": contenido})
                return
            if not mensaje.get("more_body", False):
                break

        cuerpo_entregado = False

        async def recibir_cuerpo() -> Message:
            nonlocal cuerpo_entregado
            if not cuerpo_entregado:
                cuerpo_entregado = True
                return {"type": "http.request", "body": bytes(cuerpo), "more_body": False}
            return {"type": "http.disconnect"}

        await self._aplicacion(alcance, recibir_cuerpo, enviar)


@asynccontextmanager
async def ciclo_vida(_: FastAPI):
    """Inicializa el esquema al arrancar el servidor."""
    init_db()
    yield


app = FastAPI(
    title="DigiBlock",
    description="Prototipo académico de certificados verificables",
    lifespan=ciclo_vida,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="digiblock_sesion",
    max_age=3600,
    same_site="lax",
    https_only=False,
)
app.add_middleware(LimiteCuerpoApi)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(BASE_DIR) / "app" / "static")),
    name="static",
)
app.include_router(api_router)
app.include_router(web_router)


@app.exception_handler(RequestValidationError)
async def error_de_validacion(_: Request, __: RequestValidationError) -> JSONResponse:
    """Devuelve un mensaje de validación consistente en español."""
    return JSONResponse(
        status_code=422,
        content={"detail": "Los datos enviados no cumplen el formato esperado."},
    )


@app.exception_handler(StarletteHTTPException)
async def error_http(request: Request, error: StarletteHTTPException) -> Response:
    """Devuelve errores JSON en API y páginas amigables en la web."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": str(error.detail)},
            headers=error.headers,
        )
    return plantillas.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "codigo": error.status_code, "mensaje": str(error.detail)},
        status_code=error.status_code,
    )


@app.exception_handler(Exception)
async def error_interno(request: Request, _: Exception) -> Response:
    """Evita mostrar detalles internos y usa la plantilla de error propia."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error interno al procesar la solicitud."},
        )
    return plantillas.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "codigo": 500,
            "mensaje": "Ocurrió un error interno. Intenta de nuevo.",
        },
        status_code=500,
    )


@app.get("/salud")
def obtener_salud() -> dict[str, str]:
    """Indica que la aplicación está disponible."""
    return {"estado": "ok"}