"""Only non-secret, canonical export settings cross the API boundary."""
import math
from pyproj import Transformer

PAPERS = {'A0': (841,1189), 'A1': (594,841), 'A2': (420,594), 'A3': (297,420)}
PROFILES = [
    ('Hele Aarhus',574768,6224863,6,9),
    ('Indre by og havn',574885,6224500,3.3,4.2),
    ('Universitetet og Trøjborg',574950,6226510,2.8,3.5),
    ('Frederiksbjerg / Marselisborg',574250,6221800,4,4.8),
    ('Vesterbro / Åbyhøj',573370,6224660,4,3.2),
    ('Havnen',576040,6224010,2.4,4),
    ('Risskov',576517,6228133,3.4,4.5)]
TO_UTM = Transformer.from_crs(4326,25832,always_xy=True)
TO_GEO = Transformer.from_crs(25832,4326,always_xy=True)
ATTRIBUTION = 'DDO 1954 © Hexagon · Efterkrigsmateriale · Print i faktisk størrelse / 100 %'

def validate(raw):
    if not isinstance(raw,dict):
        raise ValueError('Jobbet skal være et JSON-objekt.')
    allowed = {'bbox','meters_per_pixel','paper','orientation','dpi','margin_mm','title',
               'source_profile','endpoint','layer','crs','tile_px','format','extra_params','attribution'}
    if set(raw)-allowed:
        raise ValueError('Ukendte jobfelter. Adgangsoplysninger og filstier accepteres ikke.')
    # Legacy addresses are accepted only as known, query-free identifiers. Never requested.
    if raw.get('endpoint') not in (None,'','https://services.hxgncontent.com/streaming/wms') or raw.get('extra_params'):
        raise ValueError('Fjern WMS-adresse og adgangsparametre. Appen bruger kun den officielle kilde.')
    if raw.get('source_profile','dmp_1954') != 'dmp_1954' or raw.get('crs','EPSG:25832') != 'EPSG:25832':
        raise ValueError('Kun 1954-kilden og EPSG:25832 understøttes.')
    b = raw.get('bbox')
    if not isinstance(b,list) or len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b):
        raise ValueError('Angiv fire endelige BBOX-tal.')
    x0,y0,x1,y1=b
    if not (555000<=x0<x1<=595000 and 6200000<=y0<y1<=6250000):
        raise ValueError('Området skal ligge omkring Aarhus og have positiv størrelse.')
    j = {'bbox':b,'meters_per_pixel':raw.get('meters_per_pixel',0.25),
         'paper':raw.get('paper','A1'),'orientation':raw.get('orientation','auto'),
         'dpi':raw.get('dpi',200),'margin_mm':raw.get('margin_mm',8),
         'title':raw.get('title','Aarhus 1954')}
    if any(type(j[k]) not in (int,float) for k in ('meters_per_pixel','dpi')) or any(not isinstance(j[k],str) for k in ('paper','orientation')):
        raise ValueError('Indstillingerne har forkert datatype.')
    for key,choices in [('meters_per_pixel',(0.25,0.5,1)),('paper',PAPERS),('orientation',('auto','portrait','landscape')),('dpi',(150,200,240,300))]:
        if j[key] not in choices or isinstance(j[key],bool):
            raise ValueError('Ugyldig indstilling: '+key)
    m=j['margin_mm']
    if type(m) not in (int,float) or not math.isfinite(m) or not 8<=m<=35:
        raise ValueError('Margen skal være 8–35 mm, inklusive kildeangivelse.')
    if not isinstance(j['title'],str) or len(j['title'])>100 or any(ord(c)<32 for c in j['title']):
        raise ValueError('Titlen skal være højst 100 tegn uden kontroltegn.')
    w,h=dimensions(j)
    if min(w,h)<8:
        raise ValueError('Udsnittet er for lille. Vælg mindst 8 pixels pr. side.')
    if w*h>1_000_000_000:
        count=f'{w*h:,}'.replace(',', '.')
        raise ValueError(f'Udsnittet kræver {count} pixels ved {j["meters_per_pixel"]} meter pr. pixel. Grænsen er 1 milliard. Gør rammen mindre eller vælg 0,5 eller 1 meter under Kildepixel.')
    return j

def dimensions(j):
    a,b,c,d=j['bbox']; g=j['meters_per_pixel']
    return math.ceil((c-a)/g),math.ceil((d-b)/g)

def geometry(j):
    w,h=dimensions(j); pw,ph=PAPERS[j['paper']]
    if j['orientation']=='landscape' or (j['orientation']=='auto' and w>h): pw,ph=ph,pw
    s=min((pw-2*j['margin_mm'])/w,(ph-2*j['margin_mm'])/h)
    return pw,ph,(pw-w*s)/2,(ph-h*s)/2,w*s,h*s

def estimate(j):
    w,h=dimensions(j); pw,ph,x,y,mw,mh=geometry(j)
    return {'width_px':w,'height_px':h,'tiles':math.ceil(w/1024)*math.ceil(h/1024),
            'disk_bytes':w*h*12+512_000_000,'effective_dpi':round(w/mw*25.4,1),
            'paper_mm':[pw,ph], 'upscaled':w/mw*25.4<j['dpi']}

def tiles(j):
    w,h=dimensions(j); a,b,c,d=j['bbox']
    for y in range(0,h,1024):
        for x in range(0,w,1024):
            tw,th=min(1024,w-x),min(1024,h-y)
            yield x,y,tw,th,[a+x/w*(c-a),d-(y+th)/h*(d-b),a+(x+tw)/w*(c-a),d-y/h*(d-b)]
