import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.config import FRONTEND_ORIGIN
from app.api.video import router
from app.services.jobs import manager
from app.services.video_service import ServiceError

@asynccontextmanager
async def lifespan(app):
    async def sweep():
        while True:
            manager.cleanup()
            await asyncio.sleep(60)
    task = asyncio.create_task(sweep())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    manager.pool.shutdown(wait=False, cancel_futures=True)

app = FastAPI(title='ClipPer API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN.rstrip('/')],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
app.include_router(router)

@app.exception_handler(ServiceError)
async def service_error(request: Request, exc: ServiceError):
    return JSONResponse(status_code=400, content={'detail': str(exc)})

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={'detail': '; '.join(e['msg'] for e in exc.errors())})

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={'detail': 'An unexpected error occurred. Please try again.'})

@app.get('/health')
def health():
    return {'status': 'ok'}
