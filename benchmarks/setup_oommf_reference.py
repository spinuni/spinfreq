"""Build the pinned CPU OOMMF reference locally, without system installation.

Requires git, make, gcc and g++. The managed prefix holds sources, Tcl and
headless OOMMF. Numerical runs do not require CUDA, Tk or an X server.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

OOMMF_COMMIT='8880fff5446eeab030a18881b474814f1ea60687'
TCL_COMMIT='cbf86d62348d6b052e1961b4df995960fb21545f'


def bootstrap(prefix,jobs=4):
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise RuntimeError('This headless reference bootstrap targets Linux x86_64; supply another OOMMF runtime on other platforms')
    prefix=Path(prefix).resolve();prefix.mkdir(parents=True,exist_ok=True)
    marker=prefix/'spinfreq-reference-runtime.json'
    if any(prefix.iterdir()) and not marker.exists():
        raise ValueError('Choose an empty prefix or an existing spinfreq reference runtime')
    marker.write_text(json.dumps(dict(oommf_commit=OOMMF_COMMIT,tcl_commit=TCL_COMMIT,
        purpose='Managed headless CPU reference build'),indent=2)+'\n')
    with (prefix/'build.log').open('a') as log:
        def command(args,cwd=None,env=None):
            print(' '.join(map(str,args)),flush=True)
            subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        def clone(url,target,commit):
            if not target.exists():
                command(['git','init',target]);command(['git','remote','add','origin',url],cwd=target)
                command(['git','fetch','--depth','1','origin',commit],cwd=target)
                command(['git','checkout','--detach','FETCH_HEAD'],cwd=target)
            actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=target,text=True).strip()
            if actual!=commit:raise ValueError(f'Unexpected reference commit in {target}')
        tcl_source=prefix/'tcl-source';tcl=prefix/'tcl'
        clone('https://github.com/tcltk/tcl.git',tcl_source,TCL_COMMIT)
        command(['./configure',f'--prefix={tcl}','--enable-threads'],cwd=tcl_source/'unix')
        command(['make',f'-j{jobs}'],cwd=tcl_source/'unix');command(['make','install'],cwd=tcl_source/'unix')
        source=prefix/'oommf-source'
        clone('https://github.com/fangohr/oommf.git',source,OOMMF_COMMIT)
        root=source/'oommf'
        local=root/'config/platforms/local/linux-x86_64.tcl';local.parent.mkdir(exist_ok=True)
        local.write_text('$config SetValue use_tk 0\n$config SetValue thread_count 2\n')
        # Keep the same selected extensions as the tested runtime. This is a
        # managed source checkout; unused extensions are preserved alongside it.
        extensions=root/'app/oxs/local';unused=prefix/'unused-extensions';unused.mkdir(exist_ok=True)
        for path in list(extensions.iterdir()):
            if path.name not in ('oommf-extension-dmi-cnv','dmexchange6ngbr','oommf_dmi_extensions'):
                if (unused/path.name).exists():raise ValueError(f'Conflicting saved extension: {path.name}')
                shutil.move(str(path),unused/path.name)
        env=os.environ.copy();env.update(OOMMF_TCL_CONFIG=str(tcl/'lib/tclConfig.sh'),OOMMF_TCL_INCLUDE_DIR=str(tcl/'include'))
        command([tcl/'bin/tclsh8.6',root/'oommf.tcl','pimake'],cwd=root,env=env)
        config=dict(tclsh=str(tcl/'bin/tclsh8.6'),oommf_tcl=str(root/'oommf.tcl'),
            env={k:env[k] for k in ['OOMMF_TCL_CONFIG','OOMMF_TCL_INCLUDE_DIR']},
            oommf_repository='https://github.com/fangohr/oommf',oommf_commit=OOMMF_COMMIT,tcl_commit=TCL_COMMIT)
        (prefix/'runtime.json').write_text(json.dumps(config,indent=2)+'\n')
        return config


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',type=Path,default=Path('results/oommf-runtime'))
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    if args.jobs<1:parser.error('jobs must be positive')
    print(json.dumps(bootstrap(args.prefix,args.jobs),indent=2))
