import numpy as np, cv2, sys
from PIL import Image
a=np.load('work/frames.npy',mmap_mode='r')
glob=np.load('work/glob.npy')
clips={'kayak':(33,57),'expl':(63,81)}
H,W=1920,1080
def glyph(f):
    f=f.astype(np.int16); mn=f.min(2); return (mn>205)&((f.max(2)-mn)<40)
band=np.zeros((H,W),bool); band[15:100,0:420]=True; band[600:720,0:340]=True; band[1200:1330,0:720]=True; band[1420:1495,480:870]=True
S=cv2.dilate(((glob>0.3)&band).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
rect=np.zeros((H,W),bool); rect[1360:1412,8:866]=True; rect[1420:1495,8:185]=True
numrect=np.zeros((H,W),bool); numrect[790:1170,0:960]=True
k=np.zeros((19,19),np.uint8); k[:, :]=0
# kernel: offsets -4..+14 (dilate shifts mask toward +dy,+dx)
K=np.ones((25,25),np.uint8)
def shadowdil(m):
    m=m.astype(np.uint8)
    # anchor so that output covers m shifted by -4..+14
    return cv2.dilate(m,K,anchor=(6,6)).astype(bool)
Sd=shadowdil(S)|rect
out={}
for name,(s,e) in clips.items():
    fr=np.array(a[s:e+1]); n=len(fr)
    masks=[]
    for i in range(n):
        ff=fr[i].astype(np.int16); mn=ff.min(2)
        g=(mn>180)&((ff.max(2)-mn)<45)&numrect
        # drop tiny comps
        cnt,lab,st,_=cv2.connectedComponentsWithStats(g.astype(np.uint8),8)
        keep=np.zeros(cnt,bool); keep[1:]=st[1:,4]>400
        g=keep[lab]
        gd=shadowdil(g)
        near=cv2.dilate(gd.astype(np.uint8),np.ones((15,15),np.uint8)).astype(bool)
        dark=(ff.max(2)<70)&near&numrect
        masks.append(gd|cv2.dilate(dark.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool))
    masks=np.array(masks)
    res=[]
    for i in range(n):
        f=fr[i].copy(); m=masks[i]|Sd
        # temporal fill for number area
        rem=m.copy()
        for d in []:
            j=i+d
            if j<0 or j>=n: continue
            ok=rem&~(masks[j]|Sd)
            f[ok]=fr[j][ok]; rem&=~ok
        # spatial inpaint remainder at half res
        small=cv2.resize(f,(W//2,H//2),interpolation=cv2.INTER_AREA)
        ms=(cv2.resize(rem.astype(np.float32),(W//2,H//2),interpolation=cv2.INTER_AREA)>0).astype(np.uint8)
        ms=cv2.dilate(ms,np.ones((3,3),np.uint8))
        inp=cv2.inpaint(small,ms,9,cv2.INPAINT_TELEA)
        inp=cv2.GaussianBlur(inp,(0,0),3)
        up=cv2.resize(inp,(W,H),interpolation=cv2.INTER_CUBIC)
        alpha=cv2.GaussianBlur(cv2.dilate(rem.astype(np.uint8)*255,np.ones((7,7),np.uint8)),(0,0),4).astype(np.float32)[...,None]/255
        f=(f*(1-alpha)+up*alpha)
        # grain in filled area
        noise=np.random.normal(0,3.0,f.shape[:2])[...,None]
        f=np.clip(f+noise*alpha,0,255).astype(np.uint8)
        res.append(f)
    out[name]=np.array(res); print(name,n,flush=True)
np.savez('work/clean2.npz',**out)
