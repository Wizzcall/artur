# dedupe cleaned clips and slow them with motion interpolation to exact target length
import numpy as np, subprocess
d=dict(np.load('work/clean.npz')); d.update(dict(np.load('work/clean2.npz')))
src=np.load('work/frames.npy',mmap_mode='r')
clips={'swamp':(3,28),'kayak':(33,57),'expl':(63,81),'bld':(87,108),'street':(115,141),'rest':(148,205),'race':(211,267)}
plan={'swamp':2.5,'kayak':2.0,'expl':2.0,'bld':2.0,'street':2.0,'rest':3.0}
FPS=30
for name,dur in plan.items():
    fr=d[name]; s0=clips[name][0]; keep=[fr[0]]; last=src[s0]
    for i in range(1,len(fr)):
        o=src[s0+i]
        if np.abs(o[::4,::4].astype(np.int16)-last[::4,::4]).mean()>1.2: keep.append(fr[i]); last=o
    n=len(keep); nout=int(round(dur*FPS))+4
    # input rate so that n frames span dur
    inrate=n/dur
    cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r',f'{inrate:.6f}','-i','-',
         '-vf',f'minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1','-frames:v',str(nout),
         '-c:v','ffv1','-pix_fmt','rgb24',f'work/rtL_{name}.mkv']
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for f in keep: p.stdin.write(np.ascontiguousarray(f).tobytes())
    # pad with last frame so output long enough
    for _ in range(3): p.stdin.write(np.ascontiguousarray(keep[-1]).tobytes())
    p.stdin.close(); p.wait(); print(name,len(fr),n,flush=True)
