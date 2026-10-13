"""Generate independent GPU reference inputs; generation does not execute MuMax3."""
import argparse
import json
from pathlib import Path
from spinfreq.confined import ConfinedFilm,lattice_seed
from spinfreq.ovf import write_ovf
from liu2024 import paper_material


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--columns',type=int,default=1)
    parser.add_argument('--rows',type=int,default=1)
    parser.add_argument('--drive',choices=['sinc-x','sinc-z','harmonic'],default='sinc-x')
    parser.add_argument('--frequency-ghz',type=float,default=50)
    parser.add_argument('--amplitude-mt',type=float,default=5)
    parser.add_argument('--duration-ns',type=float,default=40)
    parser.add_argument('--source-width-nm',type=float,help='Localized left strip; omit for full-film excitation')
    parser.add_argument('--output',type=Path,default=Path('results/mumax_liu2024'))
    args=parser.parse_args()
    if min(args.columns,args.rows)<1 or args.frequency_ghz<=0 or args.duration_ns<=0:
        parser.error('Require positive geometry, frequency and duration')
    if args.source_width_nm is not None and not 0<args.source_width_nm<=40*args.columns:
        parser.error('Source width must fit inside the film')
    args.output.mkdir(parents=True,exist_ok=True)
    film=ConfinedFilm(nx=40*args.columns,ny=40*args.rows,dx=1e-9,thickness=1e-9,
                      material=paper_material(),field_T=(0,0,0),demag=False)
    write_ovf(args.output/'seed.ovf',lattice_seed(film,args.columns,args.rows),1e-9,1e-9,1e-9)
    amplitude=args.amplitude_mt*1e-3
    frequency=args.frequency_ghz*1e9
    wave=f'{amplitude:.17g}*sin(2*pi*{frequency:.17g}*t)' if args.drive=='harmonic' else f'{amplitude:.17g}*sinc(2*pi*{frequency:.17g}*(t-1e-9))'
    vector=f'vector(0,0,{wave})' if args.drive=='sinc-z' else f'vector({wave},0,0)'
    excitation=f'B_ext = {vector}'
    if args.source_width_nm is not None:
        lx=film.nx*film.dx
        excitation=f'DefRegion(1, XRange({-lx/2:.17g}, {-lx/2+args.source_width_nm*1e-9:.17g}))\nB_ext.SetRegion(1, {vector})'
    script=f'''// Liu et al. PRB 110,184413 (2024); generated independent reference.
// Array/source details supplied by user are explicit assumptions, not author files.
SetGridSize({film.nx}, {film.ny}, 1)
SetCellSize(1e-9, 1e-9, 1e-9)
SetPBC(0, 0, 0)
Msat = 5.8e5
Aex = 1.5e-11
Dind = 3e-3
Ku1 = 0.6e6
anisU = vector(0, 0, 1)
GammaLL = 1.7595e11
alpha = 0.001
OpenBC = false // MuMax default: DMI natural boundary via extrapolated ghost spins.
B_ext = vector(0, 0, 0)
m.LoadFile("seed.ovf")
MinimizerStop = 1e-7
Minimize()
OutputFormat = OVF2_TEXT
SaveAs(m, "equilibrium")
TableAdd(MaxTorque)
{excitation}
TableAutoSave(5e-12)
AutoSave(m, 5e-12)
Run({args.duration_ns*1e-9:.17g})
'''
    (args.output/'run.mx3').write_text(script)
    (args.output/'configuration.json').write_text(json.dumps(vars(args),default=str,indent=2))
    print(f'Generated {args.output}/run.mx3 and seed.ovf. Run mumax3 run.mx3 from that directory on a CUDA machine.')

if __name__=='__main__': main()
