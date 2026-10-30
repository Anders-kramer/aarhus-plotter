import json
import numpy as np
import pytest
from PIL import Image
from app import catalog, export, model, source
from app.jobs import Jobs


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','private-test-key')
    monkeypatch.setattr(catalog,'_verified_key',None)
    catalog.mark_verified('private-test-key')


def config(**kw):
    return model.validate({'bbox':[573000,6222000,573016,6222016], 'dpi':50, **kw})


def flat(endpoint,box,w,h,**kw):
    return np.full((h,w,3),100,dtype=np.uint8)


def test_resume_cannot_mix_source_or_geometry(tmp_path,ready):
    j=config(meters_per_pixel=1)
    export.run(j,tmp_path,lambda *a:None,lambda:None,fetch=flat,resolve=lambda:'test')
    original=(tmp_path/'tiles/0_0.png').read_bytes()
    for other in [dict(j,source_profile='lave_maalebordsblade'),
                  dict(j,bbox=[573001,6222000,573017,6222016]),dict(j,meters_per_pixel=.5)]:
        with pytest.raises(ValueError,match='anden kilde eller geometri'):
            export.run(other,tmp_path,lambda *a:None,lambda:None,fetch=flat)
    assert (tmp_path/'tiles/0_0.png').read_bytes()==original


def test_legacy_tiles_resume_without_network(tmp_path):
    j=config(meters_per_pixel=1);j.pop('source_profile')
    spool=tmp_path/'tiles';spool.mkdir()
    Image.fromarray(flat('',[],16,16)).save(spool/'0_0.png')
    def unexpected(*a,**kw):raise AssertionError('legacy tile should be reused')
    export.run(j,tmp_path,lambda *a:None,lambda:None,fetch=unexpected,resolve=unexpected)
    assert json.loads((tmp_path/'tile-source.json').read_text())['source_profile']=='dmp_1954'


def test_unlabelled_tiles_cannot_be_adopted_by_new_source(tmp_path,ready):
    spool=tmp_path/'tiles';spool.mkdir()
    Image.fromarray(flat('',[],16,16)).save(spool/'0_0.png')
    with pytest.raises(ValueError,match='mangler kildeidentitet'):
        export.run(config(source_profile='lave_maalebordsblade'),tmp_path,lambda *a:None,lambda:None)


def test_saved_job_keeps_source_on_resume(tmp_path,ready):
    jobs=Jobs(tmp_path)
    j=jobs.create(config(source_profile='lave_maalebordsblade'))
    jobs.action(j['id'],'cancel')
    jobs.action(j['id'],'resume')
    received=[]
    jobs.once(runner=lambda config,*args:received.append(config['source_profile']))
    assert received==['lave_maalebordsblade']
    assert 'private-test-key' not in (tmp_path/'jobs.sqlite').read_bytes().decode('latin1')


CAPABILITIES=b'''<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
<Capability><Request><GetMap><Format>image/jpeg</Format></GetMap></Request>
<Layer><CRS>EPSG:25832</CRS><CRS>EPSG:3857</CRS>
<Layer><Name>dtk_lave_maalebordsblade</Name></Layer></Layer></Capability></WMS_Capabilities>'''


@pytest.mark.parametrize('broken',[None,'layer','crs','version','format','flat','xml','network'])
def test_optional_provider_requires_live_images(monkeypatch,broken):
    monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','private-test-key')
    monkeypatch.setattr(catalog,'_verified_key',None)
    body=CAPABILITIES
    for key,old,new in [('layer',b'dtk_lave_maalebordsblade',b'wrong'),('crs',b'EPSG:3857',b'EPSG:4326'),
                        ('version',b'1.3.0',b'1.1.1'),('format',b'image/jpeg',b'image/png')]:
        if broken==key:body=body.replace(old,new)
    if broken=='xml':body=b'<broken'
    class Response:
        status_code=200
        def iter_content(self,n):yield body
        def close(self):pass
    monkeypatch.setattr(source.requests,'get',lambda *a,**kw:Response())
    crss=[]
    def fetch(endpoint,box,w,h,**kw):
        crss.append(kw['crs'])
        if broken=='network':raise source.requests.RequestException('private-test-key')
        if broken=='flat':return np.zeros((h,w,3),dtype=np.uint8)
        return np.arange(w*h*3,dtype=np.uint8).reshape(h,w,3)
    monkeypatch.setattr(source,'fetch',fetch)
    assert not catalog.available('lave_maalebordsblade')
    assert source.verify_optional_sources()==(broken is None)
    assert catalog.available('lave_maalebordsblade')==(broken is None)
    if broken is None:
        assert crss==['EPSG:25832','EPSG:3857']
        monkeypatch.setenv('PLOTTER_DATAFORDELER_APIKEY','changed-test-key')
        assert not catalog.available('lave_maalebordsblade')
    assert 'private-test-key' not in str(catalog.catalogue())


def test_stream_exception_never_exposes_credentials():
    class Session:
        def get(self,*args,**kw):raise source.requests.exceptions.ChunkedEncodingError('url?apikey=SECRET')
    with pytest.raises(source.SourceError) as error:
        source.fetch('unused',[1,2,3,4],8,8,session=Session())
    assert 'SECRET' not in str(error.value)
