"""OVF2 rectangular single-layer vector interchange with MuMax3."""
from pathlib import Path
import re
import numpy as np


def write_ovf(path,m,dx_m,dy_m,thickness_m):
    m=np.asarray(m)
    if m.ndim!=3 or m.shape[-1]!=3 or not np.all(np.isfinite(m)):
        raise ValueError('Require finite (ny,nx,3) field')
    if min(dx_m,dy_m,thickness_m)<=0:
        raise ValueError('Require positive cell dimensions')
    ny,nx,_=m.shape
    header=f'''# OOMMF OVF 2.0
# Segment count: 1
# Begin: Segment
# Begin: Header
# Title: spinfreq magnetization
# meshtype: rectangular
# meshunit: m
# xmin: 0
# ymin: 0
# zmin: 0
# xmax: {nx*dx_m:.17g}
# ymax: {ny*dy_m:.17g}
# zmax: {thickness_m:.17g}
# xbase: {dx_m/2:.17g}
# ybase: {dy_m/2:.17g}
# zbase: {thickness_m/2:.17g}
# xstepsize: {dx_m:.17g}
# ystepsize: {dy_m:.17g}
# zstepsize: {thickness_m:.17g}
# xnodes: {nx}
# ynodes: {ny}
# znodes: 1
# valuedim: 3
# valuelabels: mx my mz
# valueunits: 1 1 1
# End: Header
# Begin: Data Text
'''
    with Path(path).open('w') as file:
        file.write(header)
        np.savetxt(file,m.reshape(-1,3),fmt='%.17g')
        file.write('# End: Data Text\n# End: Segment\n')


def read_ovf(path):
    raw=Path(path).read_bytes()
    match=re.search(rb'#\s*Begin:\s*Data\s+(Text|Binary 4|Binary 8)\s*\r?\n',raw,re.I)
    if not match:
        raise ValueError('Unsupported or missing OVF data block')
    header=raw[:match.start()].decode('utf-8')
    if 'OVF 2.0' not in header:
        raise ValueError('Only OVF2 supported')
    metadata={}
    for line in header.splitlines():
        item=re.match(r'#\s*([\w]+):\s*(.*)',line)
        if item: metadata[item[1].lower()]=item[2]
    timestamp=re.search(r'Total simulation time:\s*([+\-0-9.eE]+)',header,re.I)
    if timestamp: metadata['time_s']=float(timestamp[1])
    nx,ny,nz=map(lambda key:int(metadata[key]),['xnodes','ynodes','znodes'])
    if nz!=1 or int(metadata.get('valuedim','0'))!=3:
        raise ValueError('Only single-layer vector fields supported')
    count=nx*ny*3
    kind=match[1].decode().lower()
    content=raw[match.end():]
    if kind=='text':
        data=content.split(b'#',1)[0].decode()
        numbers=np.fromstring(data,sep=' ')
        if len(numbers)!=count: raise ValueError('OVF sample count mismatch')
    else:
        size=4 if kind.endswith('4') else 8
        check=1234567.0 if size==4 else 123456789012345.0
        dtype=np.dtype('<f'+str(size))
        if len(content)<size*(count+1): raise ValueError('Truncated binary OVF')
        if np.frombuffer(content[:size],dtype=dtype)[0]!=check:
            raise ValueError('Invalid OVF2 binary check value (little endian required)')
        numbers=np.frombuffer(content,dtype=dtype,count=count,offset=size).copy()
    field=numbers.reshape(ny,nx,3)
    if not np.all(np.isfinite(field)): raise ValueError('Nonfinite OVF magnetization')
    return field,metadata
