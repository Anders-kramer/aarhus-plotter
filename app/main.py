import asyncio
import hashlib
import hmac
import io
import json
import os
import secrets
import threading
import time
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
def create_app(root=None,password=None,worker=True):
    root=Path(root or os.getenv('DATA_DIR','data'))
    password=password or os.getenv('APP_PASSWORD','')
    secret_file=os.getenv('APP_PASSWORD_FILE')
    if secret_file: password=Path(secret_file).read_text().strip()
    if len(password)<16: raise RuntimeError('APP_PASSWORD skal indeholde mindst 16 tegn. Ingen standardadgangskode.')
    sessions={}; attempts={}; preview_gate=threading.Lock()
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
        if path.startswith('/api/') and path!='/api/login':
            token=request.cookies.get('plotter','')
            expires=sessions.get(hashlib.sha256(token.encode()).hexdigest(),0)
            if expires<time.time(): return JSONResponse({'detail':'Log ind for at fortsætte.'},401)
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
    @app.post('/api/login')
    async def login(request:Request):
        now=time.time(); addr=request.client.host
        # Bounded global throttling also limits distributed LAN attempts.
        for k in list(attempts):
            if now-attempts[k][0]>300: del attempts[k]
        bucket=attempts.setdefault(addr,[now,0]); bucket[1]+=1
        if bucket[1]>10 or sum(v[1] for v in attempts.values())>100:raise HTTPException(429,'Vent fem minutter før næste loginforsøg.')
        data=await request.json()
        if not isinstance(data,dict):raise ValueError('Ugyldig loginanmodning.')
        supplied=data.get('password','')
        if not isinstance(supplied,str) or not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(),hashlib.sha256(password.encode()).digest()):raise HTTPException(401,'Forkert adgangskode.')
        attempts.pop(addr,None)
        for k in list(sessions):
            if sessions[k]<now:del sessions[k]
        if len(sessions)>100:sessions.clear()
        token=secrets.token_urlsafe(32); sessions[hashlib.sha256(token.encode()).hexdigest()]=now+43200
        response=JSONResponse({'ok':True})
        response.set_cookie('plotter',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=43200)
        return response
    @app.post('/api/logout')
    def logout(request:Request):
        sessions.pop(hashlib.sha256(request.cookies.get('plotter','').encode()).hexdigest(),None)
        r=JSONResponse({'ok':True}); r.delete_cookie('plotter'); return r
    @app.get('/api/config')
    def config():return {'profiles':model.PROFILES,'papers':model.PAPERS}
    @app.post('/api/estimate')
    async def estimate(request:Request):return model.estimate(model.validate(await request.json()))
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
