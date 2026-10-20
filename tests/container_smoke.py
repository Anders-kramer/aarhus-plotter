"""Invoked inside the restricted production image; no live imagery."""
from pathlib import Path
import numpy as np
import rasterio
from app.export import run
from app.model import validate

j = validate({"bbox": [573300, 6221700, 573556, 6221956], "paper": "A0"})
def synthetic(endpoint,box,w,h,**kw):
    a=np.zeros((h,w,3),dtype=np.uint8)
    a[:,:,0]=np.arange(w,dtype=np.uint8)[None,:]
    a[:,:,1]=np.arange(h,dtype=np.uint8)[:,None]
    return a

folder=Path('/data/synthetic-container-test')
run(j,folder,lambda *a:None,lambda:None,fetch=synthetic,resolve=lambda:'synthetic')
with rasterio.open(folder/'map.tif') as ds:
    assert ds.width==1024 and ds.crs.to_epsg()==25832
assert (folder/'map.pdf').stat().st_size>1000
assert (folder/'preview.png').stat().st_size>100
print('Restricted container: synthetic GeoTIFF, PDF and preview verified.')
