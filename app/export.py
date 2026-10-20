"""Crash-safe tile spool and windowed GeoTIFF/PDF assembly."""
import io
import os
import shutil
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import Window
from rasterio.enums import Resampling
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from . import model, source

def sync_dir(p):
    if os.name!='nt':
        fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

def publish(temp,target):
    with open(temp,'rb+') as f: os.fsync(f.fileno())
    os.replace(temp,target); sync_dir(Path(target).parent)

def disk(p,needed=128_000_000):
    if shutil.disk_usage(p).free<needed:
        raise ValueError('Der er for lidt fri diskplads. Frigør plads og genoptag jobbet.')

def image_atomic(arr,path):
    tmp=path.with_suffix('.tmp')
    Image.fromarray(arr).save(tmp,format='PNG')
    publish(tmp,path)

def run(j,folder,progress,check,fetch=source.fetch,resolve=source.resolve):
    folder=Path(folder); spool=folder/'tiles'; spool.mkdir(parents=True,exist_ok=True)
    sync_dir(folder); sync_dir(folder.parent)
    parts=list(model.tiles(j)); w,h=model.dimensions(j)
    disk(folder,model.estimate(j)['disk_bytes'])
    endpoint=None
    progress('downloading',0,len(parts))
    for i,(x,y,tw,th,box) in enumerate(parts):
        check(); disk(folder)
        path=spool/f'{x}_{y}.png'
        valid=False
        if path.exists():
            try:
                with Image.open(path) as im: valid=im.size==(tw,th); im.load()
            except (OSError,ValueError): valid=False
        if not valid:
            if endpoint is None: endpoint=resolve()
            arr=fetch(endpoint,box,tw,th,check=check)
            check(); image_atomic(arr,path)
        progress('downloading',i+1,len(parts))
    endpoint=None
    tif=folder/'map.tif'; tmp=folder/'map.partial.tif'
    progress('geotiff',0,len(parts))
    with rasterio.Env(GDAL_CACHEMAX=64_000_000), rasterio.open(tmp,'w',driver='GTiff',width=w,height=h,count=3,
            dtype='uint8',crs='EPSG:25832',transform=from_bounds(*j['bbox'],w,h),
            tiled=True,blockxsize=256,blockysize=256,compress='deflate',BIGTIFF='IF_SAFER') as ds:
        ds.update_tags(YEAR='1954',SOURCE='DDO 1954 / Hexagon',DESCRIPTION='Efterkrigsmateriale')
        for i,(x,y,tw,th,box) in enumerate(parts):
            check(); disk(folder)
            with Image.open(spool/f'{x}_{y}.png') as im:
                ds.write(np.moveaxis(np.asarray(im.convert('RGB')),-1,0),window=Window(x,y,tw,th))
            progress('geotiff',i+1,len(parts))
    check(); publish(tmp,tif)
    with rasterio.open(tif) as ds:
        scale=min(1,1000/w,1000/h)
        preview=ds.read(out_shape=(3,max(1,round(h*scale)),max(1,round(w*scale))),resampling=Resampling.bilinear)
        image_atomic(np.moveaxis(preview,0,-1),folder/'preview.png')
    make_pdf(j,tif,folder/'map.pdf',progress,check)
    check(); progress('done',1,1)

def make_pdf(j,tif,output,progress,check):
    pw,ph,sx,sy,mw,mh=model.geometry(j)
    # Never invent pixels by upsampling. Selected DPI is an upper bound.
    w,h=model.dimensions(j)
    scale=min(1,mw/25.4*j['dpi']/w)
    W,H=max(1,round(w*scale)),max(1,round(h*scale))
    chunks=[(x,y,min(1024,W-x),min(1024,H-y)) for y in range(0,H,1024) for x in range(0,W,1024)]
    output=Path(output); tmp=output.with_suffix('.partial.pdf'); mm=72/25.4
    c=Canvas(str(tmp),pagesize=(pw*mm,ph*mm),pageCompression=1)
    c.setTitle(j['title']); c.setAuthor('Aarhus Plotter'); c.setSubject(model.ATTRIBUTION)
    progress('pdf',0,len(chunks))
    with rasterio.Env(GDAL_CACHEMAX=64_000_000), rasterio.open(tif) as ds:
        for i,(x,y,cw,ch) in enumerate(chunks):
            check(); disk(output.parent)
            a=ds.read(window=Window(x*w/W,y*h/H,cw*w/W,ch*h/H),out_shape=(3,ch,cw),resampling=Resampling.bilinear)
            b=io.BytesIO(); Image.fromarray(np.moveaxis(a,0,-1)).save(b,format='JPEG',quality=94)
            b.seek(0)
            c.drawImage(ImageReader(b),(sx+x*mw/W)*mm,(sy+(H-y-ch)*mh/H)*mm,
                        width=cw*mw/W*mm,height=ch*mh/H*mm)
            progress('pdf',i+1,len(chunks))
    check(); c.setFont('Helvetica',7); c.setFillGray(.3)
    c.drawString(8*mm,3*mm,model.ATTRIBUTION)
    c.showPage(); c.save(); check(); publish(tmp,output)
