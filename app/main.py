import asyncio
import io
import json
import os
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from . import model, source
from .jobs import Jobs

STATIC=Path(__file__).parent/'static'
def create_app(root=None,worker=True):
    root=Path(root or os.getenv('DATA_DIR','data'))
    preview_gate=threading.Lock()
    lock=None
    if worker:
        root.mkdir(parents=True,exist_ok=True)
        lock=open(root/'worker.lock','a+b')
        try:
            if os.name=='nt':
                import msvcrt
                lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            lock.close()
            raise RuntimeError('Der kører allerede en arbejder på dette datavolume.') from None
    jobs=Jobs(root)
    @asynccontextmanager
    async def lifespan(app):
        if worker: jobs.start()
        yield
        jobs.close()
        if lock:lock.close()
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.jobs=jobs

    @app.middleware('http')
    async def protect(request,call_next):
        path=request.url.path
        if request.method not in ('GET','HEAD'):
            if request.headers.get('x-plotter-request')!='1': return JSONResponse({'detail':'Ugyldig anmodning.'},403)
            origin=request.headers.get('origin')
            if origin and urlsplit(origin).netloc!=request.headers.get('host'): return JSONResponse({'detail':'Forkert oprindelse.'},403)
            size=0; chunks=[]
            async for chunk in request.stream():
                size+=len(chunk)
                if size>32768:return JSONResponse({'detail':'Jobfilen er for stor.'},413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob: data: https://tile.openstreetmap.org; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        elif not path.startswith('/vendor/'):
            response.headers['Cache-Control']='no-cache'
        return response

    @app.exception_handler(ValueError)
    async def bad(request,e):return JSONResponse({'detail':str(e)},400)
    @app.exception_handler(KeyError)
    async def missing(request,e):return JSONResponse({'detail':'Jobbet findes ikke.'},404)
    @app.exception_handler(source.SourceError)
    async def upstream(request,e):return JSONResponse({'detail':str(e)},502)

    @app.get('/health')
    def health():
        if worker and (not jobs.thread or not jobs.thread.is_alive()):
            raise HTTPException(503,'Arbejderen svarer ikke.')
        with jobs.db() as c:c.execute('SELECT 1').fetchone()
        return {'status':'ok'}
    @app.get('/api/config')
    def config():return {'profiles':model.PROFILES,'papers':model.PAPERS}
    @app.post('/api/estimate')
    async def estimate(request:Request):
        e=model.estimate(model.validate(await request.json()))
        e['free_disk_bytes']=shutil.disk_usage(root).free
        return e
    @app.post('/api/map-image')
    async def map_image(request:Request):
        box,w,h=model.map_view(await request.json())
        if not preview_gate.acquire(False):raise HTTPException(429,'Et kortbillede hentes allerede. Prøv igen om lidt.')
        try:
            def get():
                a=source.fetch(source.resolve(),box,w,h,crs='EPSG:3857')
                b=io.BytesIO();Image.fromarray(a).save(b,format='PNG');return b.getvalue()
            return Response(await asyncio.to_thread(get),media_type='image/png')
        finally:preview_gate.release()
    @app.post('/api/convert')
    async def convert(request:Request):
        data=await request.json(); points=data.get('points',[])
        if not isinstance(points,list) or not 1<=len(points)<=16:raise ValueError('Ugyldige koordinater.')
        transform=model.TO_UTM if data.get('direction')=='utm' else model.TO_GEO
        try:
            result=[transform.transform(float(x),float(y),errcheck=True) for x,y in points]
            import math
            if not all(math.isfinite(v) for p in result for v in p):raise ValueError()
            return result
        except Exception:raise ValueError('Ugyldige koordinater.') from None
    @app.post('/api/preview')
    async def preview(request:Request):
        j=model.validate(await request.json())
        if not preview_gate.acquire(False):raise HTTPException(429,'Et prøvebillede hentes allerede.')
        try:
            def get():
                w,h=model.dimensions(j); s=min(512/w,512/h)
                a=source.fetch(source.resolve(),j['bbox'],max(1,round(w*s)),max(1,round(h*s)))
                b=io.BytesIO();Image.fromarray(a).save(b,format='PNG');return b.getvalue()
            return Response(await asyncio.to_thread(get),media_type='image/png')
        finally:preview_gate.release()
    @app.get('/api/jobs')
    def listing():return jobs.list()
    @app.post('/api/jobs')
    async def create(request:Request):return jobs.create(await request.json())
    @app.post('/api/jobs/{id}/{action}')
    async def action(id:str,action:str,request:Request):
        if action not in ('cancel','resume','delete'):raise HTTPException(404)
        if action=='delete' and (await request.json()).get('confirm')!=id:raise ValueError('Sletning skal bekræftes.')
        jobs.action(id,action);return {'ok':True}
    @app.get('/api/jobs/{id}/files/{name}')
    def download(id:str,name:str):
        j=jobs.get(id)
        if name not in ('map.tif','map.pdf','preview.png') or j['state']!='done':raise HTTPException(404)
        p=root/id/name
        if not p.is_file():raise HTTPException(404)
        return FileResponse(p,filename=name,media_type={'map.tif':'image/tiff','map.pdf':'application/pdf','preview.png':'image/png'}[name])
    app.mount('/',StaticFiles(directory=STATIC,html=True),name='static')
    return app
