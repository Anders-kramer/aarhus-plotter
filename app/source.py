"""Fixed provider; credentials exist only in memory. Never relay upstream error text."""
import io
import time
from urllib.parse import urlsplit, urlencode
import xml.etree.ElementTree as ET
import requests
import numpy as np
from PIL import Image
from . import catalog

METADATA='https://datakatalog.miljoeportal.dk/api/datasets/urn%3Admp%3Ads%3Aortofoto-1954'
DATASET_ID='urn:dmp:ds:ortofoto-1954'
LAYER='DK-DDOland1954_25cm_UTM32ETRS89'
DATAFORDELER_URL='https://wms.datafordeler.dk/LaveMaalebordsblade/topo20_lave_maalebordsblade/1.0.0/wms'
DATAFORDELER_LAYER='dtk_lave_maalebordsblade'

class SourceError(Exception): pass

def resolve(profile='dmp_1954'):
    """Resolve approved sources without persisting or exposing access keys."""
    spec=catalog.require_available(profile)
    if spec['kind']=='datafordeler':
        # Official fixed service URL; only the API key is configurable by environment.
        return DATAFORDELER_URL+'?'+urlencode({'apikey':catalog.datafordeler_key()})
    if spec['kind']!='dmp': raise SourceError('Kortkilden er ikke klar.')
    try:
        r=requests.get(METADATA,params={'include':'wmsSource'},
                       headers={'Accept':'application/vnd.api+json'},
                       timeout=(10,30),allow_redirects=False)
        if r.status_code!=200: raise ValueError()
        data=r.json()
        dataset=data['data']
        if dataset['id']!=DATASET_ID: raise ValueError()

        ref=dataset['relationships']['wmsSource']['data']
        if not isinstance(ref,dict) or ref.get('type')!='wmsSources': raise ValueError()

        matching=[item for item in data['included']
                  if item.get('type')==ref['type'] and item.get('id')==ref['id']]
        if len(matching)!=1: raise ValueError()
        attrs=matching[0]['attributes']
        if (attrs.get('layer')!=LAYER or
            attrs.get('version')!='1.1.1' or
            attrs.get('format')!='image/jpeg'):
            raise ValueError()

        endpoint=attrs['url']
        u=urlsplit(endpoint)
        if ((u.scheme,u.hostname,u.path)!=
            ('https','services.hxgncontent.com','/streaming/wms') or
            u.port not in (None,443) or u.username or u.password or
            u.fragment or not u.query):
            raise ValueError()
        return endpoint
    except Exception:
        # Never expose API response bodies, credentials or private query parameters.
        pass
    raise SourceError('Den officielle kilde kunne ikke bekræftes. Prøv igen senere.') from None

def verify_optional_sources():
    """Fail closed; enable the configured key only after capabilities AND image tests.

    Run once at application startup. Never persist credentials or upstream errors.
    Both projected CRSs use easting/northing order with WMS 1.3.0.
    """
    catalog.mark_verified(None)
    key=catalog.datafordeler_key()
    if not key: return False
    endpoint=DATAFORDELER_URL+'?'+urlencode({'apikey':key})
    try:
        r=requests.get(endpoint,params={'SERVICE':'WMS','REQUEST':'GetCapabilities','VERSION':'1.3.0'},
                       timeout=(10,30),allow_redirects=False,stream=True)
        if r.status_code!=200:
            r.close(); return False
        root=ET.fromstring(bounded_body(r,4_000_000))
        ns={'w':'http://www.opengis.net/wms'}
        if root.attrib.get('version')!='1.3.0': return False
        if 'image/jpeg' not in [n.text for n in root.findall('.//w:GetMap/w:Format',ns)]: return False
        # CRS declarations may be inherited from parent layers.
        def supported(node,inherited):
            crs=inherited|{n.text for n in node.findall('w:CRS',ns)}
            if node.findtext('w:Name',namespaces=ns)==DATAFORDELER_LAYER:
                return {'EPSG:25832','EPSG:3857'} <= crs
            return any(supported(child,crs) for child in node.findall('w:Layer',ns))
        if not any(supported(n,set()) for n in root.findall('./w:Capability/w:Layer',ns)):return False
        from pyproj import Transformer
        box=[573000,6222000,573512,6222512]
        for crs in ('EPSG:25832','EPSG:3857'):
            bounds=box if crs=='EPSG:25832' else list(Transformer.from_crs(25832,3857,always_xy=True).transform_bounds(*box))
            a=fetch(endpoint,bounds,128,128,crs=crs,source_profile='lave_maalebordsblade')
            if a.shape!=(128,128,3) or float(np.std(a))==0:return False
        catalog.mark_verified(key)
        return True
    except Exception:
        return False


def bounded_body(response,limit=16_000_000):
    """Bound memory even when the provider sends a huge/chunked response."""
    body=bytearray()
    try:
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body)>limit:raise SourceError('Billedsvaret var for stort.')
        return bytes(body)
    finally:
        response.close()

def decode(body,w,h):
    try:
        with Image.open(io.BytesIO(body)) as im:
            if im.size!=(w,h): raise SourceError('Billedkilden returnerede forkert billedstørrelse.')
            im.load(); a=np.array(im.convert('RGB'))
        # Valid WMS tiles can be uniform over sea or outside photo coverage.
        # Preserve the provider's pixels; uniformity is not a transport error.
        return a
    except SourceError: raise
    except Exception:
        raise SourceError('Kilden returnerede fejl-XML eller et ugyldigt billede.') from None

def fetch(endpoint,box,w,h,check=lambda:None,session=requests,crs='EPSG:25832',source_profile='dmp_1954'):
    if crs not in ('EPSG:25832','EPSG:3857'):raise ValueError('Ugyldigt koordinatsystem.')
    spec=catalog.get(source_profile)
    if spec['kind']=='datafordeler':
        params={'SERVICE':'WMS','VERSION':'1.3.0','REQUEST':'GetMap',
                'LAYERS':DATAFORDELER_LAYER,'STYLES':'',
                'CRS':crs,'BBOX':','.join(map(str,box)),
                'WIDTH':w,'HEIGHT':h,'FORMAT':'image/jpeg','TRANSPARENT':'FALSE'}
    elif spec['kind']=='dmp':
        params={'SERVICE':'WMS','VERSION':'1.1.1','REQUEST':'GetMap','LAYERS':LAYER,
                'STYLES':'','SRS':crs,'BBOX':','.join(map(str,box)),
                'WIDTH':w,'HEIGHT':h,'FORMAT':'image/jpeg','TRANSPARENT':'FALSE'}
    else:
        raise SourceError('Kortkilden er ikke klar.')
    for attempt in range(3):
        check()
        try:
            r=session.get(endpoint,params=params,timeout=(10,45),allow_redirects=False,stream=True,
                          headers={'User-Agent':'AarhusPlotter/1.0 personal-use'})
            if r.status_code==429 or r.status_code>=500:
                r.close()
                if attempt==2: raise SourceError('Billedkilden er optaget. Genoptag senere.')
                try: delay=min(60,max(2**attempt,float(r.headers.get('Retry-After',2**attempt))))
                except ValueError: delay=2**attempt
                for _ in range(int(delay)+1): check(); time.sleep(1)
                continue
            if r.status_code!=200:
                r.close()
                raise SourceError('Billedkilden afviste forespørgslen.')
            return decode(bounded_body(r),w,h)
        except (requests.Timeout,requests.ConnectionError):
            if attempt==2: raise SourceError('Billedkilden svarede ikke inden tidsgrænsen.') from None
            check(); time.sleep(2**attempt)
        except requests.RequestException:
            raise SourceError('Billedkilden kunne ikke læses. Prøv igen senere.') from None
    raise SourceError('Billedkilden svarede ikke.')
