import io
import json
import sqlite3
from pathlib import Path
import numpy as np
import pytest
import rasterio
import requests
from PIL import Image
from pypdf import PdfReader
from fastapi.testclient import TestClient
from app import model, source, export
from app.jobs import Jobs, Cancelled
from app.main import create_app

def config(**kw):
    return model.validate({'bbox':[573300,6221700,573820,6221960], 'paper':'A1','dpi':150,**kw})

def synthetic(endpoint,box,w,h,**kw):
    # Geospatial gradient makes adjoining tile discontinuities measurable.
    xs=np.linspace(box[0],box[2],w,endpoint=False)
    ys=np.linspace(box[3],box[1],h,endpoint=False)
    a=np.zeros((h,w,3),dtype=np.uint8)
    a[:,:,0]=np.round(xs-573300).astype(np.uint8)[None,:]
    a[:,:,1]=np.round(6221960-ys).astype(np.uint8)[:,None]
    a[:,:,2]=80
    return a

def test_projection_roundtrip_and_known_location():
    x,y=model.TO_UTM.transform(10.2039,56.1629)
    assert 574000<x<575000 and 6224000<y<6226000
    lon,lat=model.TO_GEO.transform(x,y)
    assert lon==pytest.approx(10.2039,abs=1e-8)
    assert lat==pytest.approx(56.1629,abs=1e-8)

@pytest.mark.parametrize('change',[
    {'bbox':[float('nan'),6221700,573556,6221956]}, {'bbox':[0,0,1,1]},
    {'endpoint':'http://127.0.0.1/admin'}, {'endpoint':'https://services.hxgncontent.com/streaming/wms?token=secret'},
    {'extra_params':{'token':'secret'}},{'password':'secret'}, {'title':'bad\nname'},
    {'meters_per_pixel':True},{'margin_mm':float('inf')},{'dpi':400}, {'path':'../../etc/passwd'},
    {'bbox':[555000,6200000,595000,6250000]}, {'bbox':[573300,6221700,573300,6221960]}])
def test_reject_invalid_import(change):
    with pytest.raises(ValueError):config(**change)

def test_legacy_safe_import():
    j=config(source_profile='dmp_1954',endpoint='https://services.hxgncontent.com/streaming/wms',layer=source.LAYER)
    assert 'endpoint' not in j

def png(w=32,h=32,flat=False):
    a=np.zeros((h,w,3),dtype=np.uint8) if flat else synthetic('',[573300,6221700,573556,6221956],w,h)
    b=io.BytesIO(); Image.fromarray(a).save(b,format='PNG');return b.getvalue()

class Response:
    def __init__(self,status,content):
        self.status_code=status;self.content=content;self.headers={'Retry-After':'0'}
    def iter_content(self,n):yield self.content
    def close(self):pass

@pytest.mark.parametrize('body',[b'<ServiceExceptionReport>SECRET</ServiceExceptionReport>',b'<html>bad</html>',b'',png(16,16),png(flat=True)])
def test_decode_errors_no_upstream_disclosure(body):
    with pytest.raises(source.SourceError) as e:source.decode(body,32,32)
    assert 'SECRET' not in str(e.value)

def test_fetch_timeout_retries(monkeypatch):
    monkeypatch.setattr(source.time,'sleep',lambda x:None)
    class Session:
        count=0
        def get(self,*a,**kw):self.count+=1;raise requests.Timeout('token=SECRET')
    s=Session()
    with pytest.raises(source.SourceError) as e:source.fetch('unused',[1,2,3,4],32,32,session=s)
    assert s.count==3 and 'SECRET' not in str(e.value)

def test_http200_xml_rejected():
    class S:
        def get(self,*a,**kw):return Response(200,b'<ServiceException>SECRET</ServiceException>')
    with pytest.raises(source.SourceError):source.fetch('',[],32,32,session=S())

def test_rate_limit_then_success(monkeypatch):
    monkeypatch.setattr(source.time,'sleep',lambda x:None)
    class S:
        n=0
        def get(self,*a,**kw):
            self.n+=1
            return Response(429 if self.n==1 else 200,png())
    s=S();assert source.fetch('',[],32,32,session=s).shape==(32,32,3);assert s.n==2

def test_tiles_exact_shared_boundaries():
    j=config(); t=list(model.tiles(j))
    assert t[0][4][2]==t[1][4][0]
    assert t[0][4][1]==t[3][4][3]

@pytest.mark.parametrize('paper,expected',[('A0',(841,1189)),('A1',(594,841))])
def test_export_georeferencing_pdf_size_and_attribution(tmp_path,paper,expected):
    j=config(paper=paper,bbox=[573300,6221700,573820,6221960]);events=[]
    export.run(j,tmp_path,lambda *p:events.append(p),lambda:None,fetch=synthetic,resolve=lambda:'memory-only')
    with rasterio.open(tmp_path/'map.tif') as ds:
        assert ds.crs.to_epsg()==25832
        assert tuple(ds.bounds)==tuple(j['bbox'])
        assert ds.width==2080 and ds.height==1040
        assert abs(int(ds.read(1)[0,1023])-int(ds.read(1)[0,1024]))<=1
        assert 'memory-only' not in json.dumps(ds.tags())
    pdf=PdfReader(tmp_path/'map.pdf');page=pdf.pages[0]
    assert float(page.mediabox.width)*25.4/72==pytest.approx(expected[1],abs=.01)
    assert float(page.mediabox.height)*25.4/72==pytest.approx(expected[0],abs=.01)
    assert 'Hexagon' in page.extract_text() and '100 %' in page.extract_text()
    assert events[-1]==('done',1,1)

@pytest.mark.parametrize('phase',['downloading','pdf'])
def test_interrupt_resume_uses_committed_tiles(tmp_path,phase):
    j=config();calls=[]
    def fetch(*a,**kw):calls.append(1);return synthetic(*a,**kw)
    def progress(state,done,total):
        if state==phase and done==1:raise Cancelled()
    with pytest.raises(Cancelled):export.run(j,tmp_path,progress,lambda:None,fetch=fetch,resolve=lambda:'first-credentials')
    assert not (tmp_path/'map.pdf').exists()
    first=len(calls)
    export.run(j,tmp_path,lambda *a:None,lambda:None,fetch=fetch,resolve=lambda:'rotated-credentials')
    assert len(calls)==len(list(model.tiles(j)))
    assert first>=1

def test_corrupt_cached_tile_refetched(tmp_path):
    j=config(bbox=[573300,6221700,573316,6221716]);(tmp_path/'tiles').mkdir()
    (tmp_path/'tiles/0_0.png').write_bytes(b'broken')
    export.run(j,tmp_path,lambda *a:None,lambda:None,fetch=synthetic,resolve=lambda:'')
    assert (tmp_path/'map.tif').exists()

def test_disk_guard(monkeypatch,tmp_path):
    monkeypatch.setattr(export.shutil,'disk_usage',lambda p:type('D',(),{'free':0})())
    with pytest.raises(ValueError):export.disk(tmp_path)

def test_jobs_recovery_cancel_and_immutable_settings(tmp_path):
    jobs=Jobs(tmp_path);j=jobs.create(config());id=j['id']
    with jobs.db() as c:c.execute("UPDATE jobs SET state='pdf' WHERE id=?",(id,))
    jobs=Jobs(tmp_path);assert jobs.get(id)['state']=='interrupted'
    jobs.action(id,'resume');assert jobs.get(id)['config']==j['config']
    jobs.action(id,'cancel');assert jobs.get(id)['state']=='cancelled'
    jobs.action(id,'resume')
    def runner(config,folder,progress,check):
        jobs.action(id,'cancel');check()
    jobs.once(runner);assert jobs.get(id)['state']=='cancelled'
    jobs.action(id,'delete');assert not jobs.list()

def test_auth_csrf_import_download_and_delete(tmp_path):
    app=create_app(tmp_path,password='a-long-test-password',worker=False)
    with TestClient(app) as c:
        assert c.get('/api/jobs').status_code==401
        assert c.post('/api/login',json={'password':'a-long-test-password'}).status_code==403
        c.headers['X-Plotter-Request']='1'
        assert c.post('/api/login',json={'password':'bad'}).status_code==401
        assert c.post('/api/login',json={'password':'a-long-test-password'}).status_code==200
        assert c.post('/api/jobs',json=config(),headers={'Origin':'https://evil.test'}).status_code==403
        assert c.post('/api/jobs',json={'endpoint':'http://localhost/'}).status_code==400
        j=c.post('/api/jobs',json=config()).json();id=j['id']
        assert c.get(f'/api/jobs/{id}/files/map.pdf').status_code==404
        assert c.post(f'/api/jobs/{id}/delete',json={}).status_code==400
        assert c.post(f'/api/jobs/{id}/delete',json={'confirm':id}).status_code==400
        assert c.post(f'/api/jobs/{id}/cancel',json={}).status_code==200
        assert c.post(f'/api/jobs/{id}/delete',json={'confirm':id}).status_code==200
        assert c.get('/api/jobs/invalid/files/map.tif').status_code==404
        assert c.post('/api/jobs',content='x'*33000).status_code==413
        c.post('/api/logout',json={});assert c.get('/api/jobs').status_code==401

def test_no_default_password(tmp_path):
    with pytest.raises(RuntimeError):create_app(tmp_path,password='short')

def test_bounded_upstream_body():
    with pytest.raises(source.SourceError):
        source.bounded_body(Response(200,b'x'*100),50)
