"""Publish comparisons without treating assumed geometry as author validation."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from liu2024 import savefig,write_table
from liu2024_fig2 import fit_collective


def main():
    root=Path('validation/liu2024/conditions')
    records=[]
    for path in sorted(root.rglob('summary_*nm.json')):
        if 'legacy_image_sum' in path.parts: continue
        for r in json.loads(path.read_text()):
            if r['status']!='computed': continue
            r={**r,'source':str(path.relative_to(root))}
            if r['cell_nm']==1:
                r['upper_onset_error_percent']=abs(r['k0_upper_GHz']/34.5-1)*100
                r['gyration_upper_error_percent']=abs(r['bands_GHz']['gyration'][1]/4-1)*100
                r['collective_fits']=fit_collective(r['frequency_samples'])
            records.append(r)
    fine=[r for r in records if r['cell_nm']==1]
    write_table(root/'comparison.csv',['case','cell_nm','width_nm','pinned_nm','gyration_min_GHz','gyration_max_GHz','breathing_min_GHz','breathing_max_GHz','k0_upper_candidate_GHz','torque_T'],
        [[r['case'],r['cell_nm'],r['assumptions']['width_nm'],r['assumptions']['pinned_nm'],*r['bands_GHz']['gyration'],*r['bands_GHz']['breathing'],r['k0_upper_GHz'],r['torque_T']] for r in records])
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for record in fine:
        x=[row['reduced_ka_over_pi'] for row in record['frequency_samples']]
        for ax,band in zip(axes,['gyration','breathing','upper_branch']):
            ax.plot(x,[row[band+'_GHz'] for row in record['frequency_samples']],'o-',label=record['case'])
    axes[0].axhspan(.1,4,color='gray',alpha=.1,label='Paper quoted interval')
    axes[1].axhspan(13.4,20.4,color='gray',alpha=.1,label='Paper quoted interval')
    axes[2].axhline(34.5,color='gray',ls='--',label='Paper k=0 upper onset')
    for ax,label in zip(axes,['Gyration candidate','Breathing','Lowest upper candidate']):
        ax.set(xlabel='k a / π',ylabel='Frequency (GHz)',title=label);ax.legend(fontsize=7)
    savefig(fig,root,'fine_conditions')
    best_breathing=min(fine,key=lambda r:max(r['breathing_endpoint_errors_percent']))
    summary=dict(paper=dict(breathing_GHz=[13.4,20.4],gyration_GHz=[.1,4],k0_upper_GHz=34.5),
        material_parameters_fitted=False,geometry_search_exploratory=True,
        best_breathing_case=best_breathing['case'],paper_validation_passed=False,
        fine_comparisons=[{key:r[key] for key in ['case','assumptions','bands_GHz','k0_upper_GHz',
           'breathing_endpoint_errors_percent','upper_onset_error_percent','gyration_upper_error_percent',
           'torque_T','max_growth_per_s','source','collective_fits']} for r in fine],
        caveats=['45 nm case was an adaptive midpoint probe after 44/46 nm checks, not an author-specified geometry',
                 'Near matching frequency intervals do not validate the full dispersion curve or finite-chain source response',
                 'Infinite-chain neutral translation mode does not reproduce the finite 0.1 GHz cutoff',
                 'Boundary pinning assumed; no author script establishes it',
                 'Upper candidate remains shifted for the low-band-matching cases',
                 'No MuMax3 switching dynamics or time-domain frequency comb comparison executed'])
    (root/'comparison.json').write_text(json.dumps(summary,indent=2))

if __name__=='__main__':main()
