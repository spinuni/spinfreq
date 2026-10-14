"""Check that selected frequency candidates have breathing-like spatial structure."""
import json
from pathlib import Path
import numpy as np


def characterize(folder):
    folder=Path(folder);records=[]
    for summary in sorted(folder.rglob('summary_*nm.json')):
        if 'legacy_image_sum' in summary.parts: continue
        for record in json.loads(summary.read_text()):
            if record['status']!='computed': continue
            raw=np.load(summary.parent/f"{record['case']}_{record['cell_nm']:g}nm.npz")
            m=raw['m'];ny,nx=m.shape[:2];spacing=record['cell_nm']*1e-9;period=nx*spacing
            x=(np.arange(nx)+.5)*spacing;y=(np.arange(ny)+.5)*spacing
            core=np.maximum(-m[...,2],0)
            center_x=np.angle(np.sum(core*np.exp(2j*np.pi*x/period)[None,:]))*period/(2*np.pi)%period
            center_y=float(np.sum(core*y[:,None])/core.sum())
            xx=(x-center_x+period/2)%period-period/2;yy=y-center_y
            xx,yy=np.meshgrid(xx,yy)
            mz=m[...,2]
            derivative_x=(np.roll(mz,-1,axis=1)-np.roll(mz,1,axis=1))/(2*spacing)
            derivative_y=np.gradient(mz,spacing,axis=0)
            mask=np.hypot(xx,yy)<min(period,ny*spacing)*.45
            radial=-(xx*derivative_x+yy*derivative_y)*mask
            frequencies=raw['eigenvalues'][0].imag/(2*np.pi*1e9)
            projections=[]
            for f,mode in zip(frequencies,raw['modes'][0]):
                if not 1<f<50: continue
                z=mode[...,2]
                denominator=np.sum(radial**2)*np.sum(abs(z)**2)
                score=float(abs(np.vdot(radial,z))**2/max(denominator,1e-300))
                projections.append(dict(frequency_GHz=float(f),radial_mz_overlap=score))
            selected=record['frequency_samples'][0]['breathing_GHz']
            near=min(projections,key=lambda p:abs(p['frequency_GHz']-selected))
            records.append(dict(case=record['case'],cell_nm=record['cell_nm'],source=str(summary.relative_to(folder)),
                selected_breathing_GHz=selected,radial_mz_overlap=near['radial_mz_overlap'],
                strongest_radial_mode=max(projections,key=lambda p:p['radial_mz_overlap']),
                matches_strongest_radial_mode=near is max(projections,key=lambda p:p['radial_mz_overlap']),
                positive_mode_projections=projections,
                note='Normalized overlap with radial derivative of equilibrium mz; checks k=0 mode shape, not full band tracking'))
    (folder/'mode_character.json').write_text(json.dumps(records,indent=2))
    return records

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('validation/liu2024/conditions'))
    for r in characterize(parser.parse_args().output):
        print(r['case'],r['cell_nm'],r['radial_mz_overlap'],r['matches_strongest_radial_mode'])
