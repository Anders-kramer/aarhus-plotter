"""Fixed provider; credentials exist only in memory. Never relay upstream error text."""
import io
import time
from urllib.parse import urlsplit
import requests
import numpy as np
from PIL import Image

METADATA='https://datakatalog.miljoeportal.dk/api/datasets/urn%3Admp%3Ads%3Aortofoto-1954'
DATASET_ID='urn:dmp:ds:ortofoto-1954'
LAYER='DK-DDOland1954_25cm_UTM32ETRS89'

class SourceError(Exception): pass

def resolve():
    """Resolve the approved 1954 WMS endpoint from the current JSON:API catalogue."""
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

def fetch(endpoint,box,w,h,check=lambda:None,session=requests,crs='EPSG:25832'):
    if crs not in ('EPSG:25832','EPSG:3857'):raise ValueError('Ugyldigt koordinatsystem.')
    params={'SERVICE':'WMS','VERSION':'1.1.1','REQUEST':'GetMap','LAYERS':LAYER,
            'STYLES':'','SRS':crs,'BBOX':','.join(map(str,box)),
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
