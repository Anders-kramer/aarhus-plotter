"""Historical map selection must preserve legacy jobs and protect credentials."""
import io
from urllib.parse import urlsplit, parse_qs
import numpy as np
import pytest
import rasterio
from PIL import Image
from fastapi.testclient import TestClient
from app import catalog, model, source, export
from app.main import create_app


def base(**extras):
    data={'bbox':[573300,6221700,573316,6221716], 'paper':'A3','dpi':50}
    data.update(extras)
    return data


def test_catalogue_shows_locked_sources(monkeypatch):
    monkeypatch.delenv('PLOTTER_DATAFORDELER_APIKEY',raising=False)
    entries={item['id']:item for item in catalog.catalogue()}
    assert entries['dmp_1954']['available']
    assert not entries['lave_maalebordsblade']['available']
    assert not entries['lw_1944']['available']
    assert not entries['ia_1945']['available']
    assert 'url' not in entries['dmp_1954']
    assert model.validate(base())['source_profile']=='dmp_1954'
    with pytest.raises(ValueError):
        model.validate(base(source_profile='lave_maalebordsblade'))
    for id in ('lw_1944','ia_1945','evil'):
        with pytest.raises(ValueError):
            model.validate(base(source_profile=id))


def test_datafordeler_wms_key_stays_on_server(monkeypatch):
    monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','test-secret-value')
    monkeypatch.setattr(catalog,'_verified_key',None)
    catalog.mark_verified('test-secret-value')
    j=model.validate(base(source_profile='lave_maalebordsblade'))
    assert j['meters_per_pixel']==1
    assert 'test-secret-value' not in str(j)
    assert 'test-secret-value' not in str(catalog.catalogue())
    assert j['source_profile']=='lave_maalebordsblade'
    assert '1954' not in j['title']
    endpoint=source.resolve('lave_maalebordsblade')
    uri=urlsplit(endpoint)
    assert uri.netloc=='wms.datafordeler.dk'
    assert uri.path=='/LaveMaalebordsblade/topo20_lave_maalebordsblade/1.0.0/wms'
    assert parse_qs(uri.query)['apikey']==['test-secret-value']

    class Response:
        status_code=200
        headers={}
        def __init__(self,body):self.body=body
        def iter_content(self,n):yield self.body
        def close(self):pass
    rgb=np.zeros((8,8,3),dtype=np.uint8)
    image=io.BytesIO()
    Image.fromarray(rgb).save(image,format='PNG')
    class Session:
        def get(self,url,**kwargs):
            assert url==endpoint
            params=kwargs['params']
            assert params['VERSION']=='1.3.0'
            assert params['LAYERS']=='dtk_lave_maalebordsblade'
            assert params['CRS']=='EPSG:25832'
            assert 'SRS' not in params
            return Response(image.getvalue())
    assert source.fetch(endpoint,[1,2,3,4],8,8,session=Session(),source_profile='lave_maalebordsblade').shape==(8,8,3)


def test_historical_export_metadata_and_pdf(tmp_path,monkeypatch):
    monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','test-secret-value')
    monkeypatch.setattr(catalog,'_verified_key',None)
    catalog.mark_verified('test-secret-value')
    j=model.validate(base(source_profile='lave_maalebordsblade',meters_per_pixel=2))
    assert model.dimensions(j)==(8,8)
    def tile(endpoint,box,w,h,**kwargs):
        assert kwargs['source_profile']=='lave_maalebordsblade'
        return np.full((h,w,3),125,dtype=np.uint8)
    export.run(j,tmp_path,lambda *x:None,lambda:None,
               fetch=tile,resolve=lambda profile:'in-memory')
    with rasterio.open(tmp_path/'map.tif') as ds:
        tags=ds.tags()
        assert tags['SOURCE']=='Datafordeleren / Klimadatastyrelsen'
        assert '1901' in tags['PERIOD']
        assert 'YEAR' not in tags
        assert tuple(ds.bounds)==tuple(j['bbox'])
    assert (tmp_path/'map.pdf').is_file()
    from pypdf import PdfReader
    pdf=PdfReader(tmp_path/'map.pdf')
    assert 'https://creativecommons.org/licenses/by/4.0/' in pdf.metadata.subject
    assert 'Klimadatastyrelsen' in pdf.pages[0].extract_text()


def test_source_selection_api(monkeypatch,tmp_path):
    monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','test-secret-value')
    monkeypatch.setattr(catalog,'_verified_key',None)
    catalog.mark_verified('test-secret-value')
    calls=[]
    monkeypatch.setattr(source,'resolve',lambda profile='dmp_1954': calls.append(('resolve',profile)) or 'opaque')
    def image(endpoint,box,w,h,**kw):
        calls.append(('fetch',kw['source_profile']))
        return np.zeros((h,w,3),dtype=np.uint8)
    monkeypatch.setattr(source,'fetch',image)
    app=create_app(tmp_path,worker=False)
    with TestClient(app) as client:
        client.headers['X-Plotter-Request']='1'
        r=client.get('/api/config')
        assert r.status_code==200
        assert len(r.json()['sources'])==4
        assert 'test-secret-value' not in r.text
        data={'source_profile':'lave_maalebordsblade',
              'bbox':[10.18,56.14,10.22,56.17],'width':64,'height':64}
        assert client.post('/api/map-image',json=data).status_code==200
        assert ('resolve','lave_maalebordsblade') in calls
        assert ('fetch','lave_maalebordsblade') in calls
        data['source_profile']='lw_1944'
        assert client.post('/api/map-image',json=data).status_code==400
        data['source_profile']='https://evil.example'
        assert client.post('/api/map-image',json=data).status_code==400


def test_legacy_config_still_uses_1954(monkeypatch):
    monkeypatch.delenv('PLOTTER_DATAFORDELER_APIKEY',raising=False)
    old=base(meters_per_pixel=0.25)
    j=model.validate(old)
    assert j['source_profile']=='dmp_1954'
    assert model.dimensions(j)==(64,64)
