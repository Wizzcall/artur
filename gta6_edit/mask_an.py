import numpy as np
from PIL import Image
a=np.load('work/frames.npy',mmap_mode='r')
clips={'swamp':(3,28),'kayak':(33,57),'expl':(63,81),'bld':(87,108),'street':(115,141),'rest':(148,205),'race':(211,267)}
def glyph(f):
    f=f.astype(np.int16); mn=f.min(2); return (mn>215)&((f.max(2)-mn)<30)
acc=np.zeros((1920,1080),np.float32); n=0
per={}
for k,(s,e) in clips.items():
    c=np.zeros((1920,1080),np.float32)
    for i in range(s,e+1):
        g=glyph(a[i]); c+=g
    per[k]=c/(e-s+1); acc+=c; n+=e-s+1
glob=acc/n
np.save('work/glob.npy',glob); np.savez('work/per.npz',**per)
Image.fromarray((glob*255).astype(np.uint8)).resize((540,960)).save('ref/glob.png')
# shadow offset on race
f=a[240].astype(np.int16); G=glyph(a[240]); D=f.max(2)<45
best=[]
for dy in range(0,16):
  for dx in range(0,16):
    sh=np.zeros_like(G); sh[dy:,dx:]=G[:1920-dy,:1080-dx]
    edge=sh&~G
    best.append(((D&edge)[800:1170,0:400].sum()/max(1,edge[800:1170,0:400].sum()),dx,dy))
best.sort(reverse=True); print(best[:6])
