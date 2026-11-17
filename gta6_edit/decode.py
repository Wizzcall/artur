import subprocess, numpy as np, sys
V="/root/.claude/uploads/ab0cf5aa-7632-56ce-8794-0d3a38f58f98/d8c149a7-copy_A57E6671-95D9-4ABA-8EAE-7B351BB41D5A.mov"
W,H=1080,1920
cmd=["ffmpeg","-v","error","-i",V,"-vf","zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,zscale=t=bt709:m=bt709:r=pc,format=rgb24","-f","rawvideo","-"]
p=subprocess.Popen(cmd,stdout=subprocess.PIPE)
fr=[]
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    fr.append(np.frombuffer(b,np.uint8).reshape(H,W,3))
a=np.stack(fr); print(a.shape)
np.save("work/frames.npy",a)
