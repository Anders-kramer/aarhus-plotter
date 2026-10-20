"""Real process death (os._exit), not only a Python exception."""
import os
import subprocess
import sys
from pathlib import Path
import pytest
from app.jobs import Jobs

SCRIPT = r'''
import os,sys
import numpy as np
from app.jobs import Jobs
from app.export import run
root,phase=sys.argv[1:]; jobs=Jobs(root)
j=jobs.create({'bbox':[573300,6221700,573820,6221960]})
def runner(config,folder,progress,check):
    def hook(state,done,total):
        progress(state,done,total)
        if state==phase and done==1: os._exit(71)
    def synthetic(endpoint,box,w,h,**kw):
        a=np.zeros((h,w,3),dtype=np.uint8)
        a[:,:,0]=np.arange(w,dtype=np.uint8)[None,:]
        return a
    run(config,folder,hook,check,fetch=synthetic,resolve=lambda:'synthetic')
jobs.once(runner)
'''

@pytest.mark.parametrize('phase',['downloading','pdf'])
def test_process_death_preserves_tiles_and_never_publishes_partial_pdf(tmp_path,phase):
    p=subprocess.run([sys.executable,'-c',SCRIPT,str(tmp_path),phase],timeout=30)
    assert p.returncode==71
    jobs=Jobs(tmp_path);j=jobs.list()[0];folder=tmp_path/j['id']
    assert j['state']=='interrupted'
    assert len(list((folder/'tiles').glob('*.png')))>=1
    assert not (folder/'map.pdf').exists()
    jobs.action(j['id'],'resume')
    assert jobs.get(j['id'])['config']==j['config']
