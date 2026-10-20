"""Fixed provider; credentials exist only in memory. Never relay upstream error text."""
import io
import time
from urllib.parse import urlsplit
import requests
import numpy as np
from PIL import Image

METADATA='https://arealdata-api.miljoeportal.dk/datasets/urn:dmp:ds:ortofoto-1954'
LAYER='DK-DDOland1954_25cm_UTM32ETRS89'

class SourceError(Exception): pass

def resolve():
    try:
        r=requests.get(METADATA,timeout=(10,30),allow_redirects=False)
        r.raise_for_status(); data=r.json()
        if data['attributes']['wms-layer-name']!=LAYER: raise ValueError()
        for s in data['sources']:
            if s['type'].lower()=='wms':
                for v in s['urls']:
                    u=urlsplit(v['url'])
                    if (u.scheme,u.netloc,u.path)==('https','services.hxgncontent.com','/streaming/wms') and not u.fragment:
                        return v['url']
    except Exception:
        pass
    raise SourceError('Den officielle kilde kunne ikke bekræftes. Prøv igen senere.')

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
        if a.std(axis=(0,1)).max()<1:
            raise SourceError('Ensfarvet billedfelt. Kontrollér dækningen og prøv et andet udsnit.')
        return a
    except SourceError: raise
    except Exception:
        raise SourceError('Kilden returnerede fejl-XML eller et ugyldigt billede.') from None

def fetch(endpoint,box,w,h,check=lambda:None,session=requests):
    params={'SERVICE':'WMS','VERSION':'1.1.1','REQUEST':'GetMap','LAYERS':LAYER,
            'STYLES':'','SRS':'EPSG:25832','BBOX':','.join(map(str,box)),
            'WIDTH':w,'HEIGHT':h,'FORMAT':'image/jpeg','TRANSPARENT':'FALSE'}
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
    raise SourceError('Billedkilden svarede ikke.')
