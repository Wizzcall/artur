import numpy as np, subprocess, cv2, math, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1920,1080,30
VW,VH=1080,1920
DUR=32.0; NF=int(DUR*FPS)
FB='/usr/share/fonts/opentype/inter/Inter-Black.otf'
FX='/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
def font(p,s): return ImageFont.truetype(p,s)
def clamp(x,a=0,b=1): return max(a,min(b,x))
def eo(x): x=clamp(x); return 1-(1-x)**3
def eback(x):
    x=clamp(x); c1=1.70158; c3=c1+1; return 1+c3*(x-1)**3+c1*(x-1)**2

# ---------- sprite helpers ----------
def text_sprite(txt,fnt,shadow,features=None,fill=(255,255,255,255)):
    l,t,r,b=fnt.getbbox(txt,features=features)
    pad=shadow+4
    im=Image.new('RGBA',(r-l+pad*2,b-t+pad*2),(0,0,0,0)); d=ImageDraw.Draw(im)
    d.text((pad-l+shadow,pad-t+shadow),txt,font=fnt,fill=(0,0,0,255),features=features)
    d.text((pad-l,pad-t),txt,font=fnt,fill=fill,features=features)
    return im,(pad,pad)   # offset of glyph top-left inside sprite
def paste(canvas,spr,x,y,alpha=1.0,scale=1.0,anchor=(0,0)):
    """x,y = position of glyph top-left (anchor 0,0) ; scale around sprite centre"""
    im,(ox,oy)=spr
    if scale!=1.0:
        w,h=im.size; nw,nh=max(1,int(w*scale)),max(1,int(h*scale))
        cx,cy=x-ox+w/2,y-oy+h/2
        im=im.resize((nw,nh),Image.LANCZOS); px,py=int(cx-nw/2),int(cy-nh/2)
    else: px,py=int(x-ox),int(y-oy)
    if alpha<1.0:
        a=im.getchannel('A').point(lambda v:int(v*alpha)); im=im.copy(); im.putalpha(a)
    canvas.alpha_composite(im,(px,py)) if px>=0 and py>=0 else canvas.paste(im,(px,py),im)


# 16:9 layouts derived from the original vertical layout (scale 0.75, same proportions)
k=0.75; X0=130; Y0=150
def sy(y): return int(Y0+(y-632)*k)
def sx(x): return int(X0+(x-22)*k)
LEFT=dict(gta=(X0,sy(632),int(80*k)),num=(X0+3,sy(804),int(486*k)),days=(X0,sy(1224),int(118*k)),
          bar=(sx(19),sy(1370),sx(849),sy(1399)),info_y=sy(1431),info_s=int(62*k),info_r=sx(845),
          timer_y=sy(1545),timer_s=int(150*k),align='left')
kc=0.6; YC=40
def cy_(y): return int(YC+(y-215)*kc)
CARD=dict(gta=(None,cy_(215),int(134*kc)),num=(None,cy_(461),int(824*kc)),days=(None,cy_(1177),int(152*kc)),
          bar=(W//2-int(446*kc),cy_(1350),W//2+int(446*kc),cy_(1389)),info_y=cy_(1429),info_s=int(66*kc),info_r=W//2+int(446*kc)-4,
          timer_y=cy_(1560),timer_s=int(165*kc),align='center')
def sprites(L):
    S={}
    sh=lambda s:max(3,int(round(s*0.024)))
    S['gta']=text_sprite('GTA VI',font(FB,L['gta'][2]),sh(L['gta'][2]))
    S['num']=text_sprite('1',font(FB,L['num'][2]),sh(L['num'][2]))
    S['days']=text_sprite('DAY LEFT',font(FB,L['days'][2]),sh(L['days'][2]))
    S['date']=text_sprite('NOV 19, 2026',font(FB,int(L['info_s']*0.92)),3)
    return S
SL,SC=sprites(LEFT),sprites(CARD)
def xpos(L,key,spr):
    if L['align']=='center':
        w=spr[0].size[0]-2*spr[1][0]; return (W-w)//2
    return L[key][0]
def bar_layer(L,frac,alpha=1.0):
    x0,y0,x1,y1=L['bar']; h=y1-y0; r=h//2
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((x0+4,y0+4,x1+4,y1+4),r,fill=(0,0,0,140))
    d.rounded_rectangle((x0,y0,x1,y1),r,fill=(10,10,12,235),outline=(255,255,255,235),width=3)
    fw=int((x1-x0-6)*frac)
    if fw>h:
        g=np.zeros((h-6,fw,4),np.uint8); t=np.linspace(0,1,fw)[None,:]
        c0=np.array([252,108,190]); c1=np.array([255,192,58])
        g[...,:3]=(c0[None,None,:]*(1-t[...,None])+c1[None,None,:]*t[...,None]).astype(np.uint8)
        g[...,3]=255
        gi=Image.fromarray(g,'RGBA'); m=Image.new('L',gi.size,0); ImageDraw.Draw(m).rounded_rectangle((0,0,fw-1,h-7),(h-6)//2,fill=255)
        lay.paste(gi,(x0+3,y0+3),m)
    if alpha<1: lay.putalpha(lay.getchannel('A').point(lambda v:int(v*alpha)))
    return lay

# timer
TF={}
def timer_font(s):
    if s not in TF: TF[s]=font(FX,s)
    return TF[s]
def timer_layer(L,secs_elapsed_float,appear_t,glow=1.0,alpha=1.0,scale=1.0):
    s=L['timer_s']; f=timer_font(s)
    cw=max(f.getbbox(c)[2]-f.getbbox(c)[0] for c in '0123456789')+6
    colw=int(s*0.33)
    k=int(math.floor(secs_elapsed_float)); frac=secs_elapsed_float-k
    def fmt(v):
        v=max(0,v); return '%02d:%02d:%02d'%(v//3600,(v%3600)//60,v%60)
    cur,prev=fmt(86399-k),fmt(86399-k+1)
    total=sum(colw if c==':' else cw for c in cur)
    x0=(W-total)//2 if L['align']=='center' else LEFT['gta'][0]
    y0=L['timer_y']
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    roll=eo(frac/0.18) if k>0 else 1.0
    asc=f.getbbox('0')[1]; hgt=f.getbbox('0')[3]-asc
    txt=Image.new('RGBA',(W,H),(0,0,0,0)); dt=ImageDraw.Draw(txt)
    clip=Image.new('L',(W,H),0); ImageDraw.Draw(clip).rectangle((0,y0-6,W,y0+hgt+8),fill=255)
    x=x0
    for i,c in enumerate(cur):
        w=colw if c==':' else cw
        if c!=prev[i] and roll<1:
            off=int((1-roll)*hgt*1.35)
            dt.text((x+(w-(f.getbbox(prev[i])[2]-f.getbbox(prev[i])[0]))//2-f.getbbox(prev[i])[0],y0-asc+off-int(hgt*1.35)),prev[i],font=f,fill=(255,255,255,255))
            dt.text((x+(w-(f.getbbox(c)[2]-f.getbbox(c)[0]))//2-f.getbbox(c)[0],y0-asc+off),c,font=f,fill=(255,255,255,255))
        else:
            bb=f.getbbox(c); dt.text((x+(w-(bb[2]-bb[0]))//2-bb[0],y0-asc-(int(hgt*0.06) if c==':' else 0)),c,font=f,fill=(255,255,255,255))
        x+=w
    # roll goes downward -> reverse direction so new digit comes from top: fine either way
    a=np.array(txt.getchannel('A')); a=(a.astype(np.float32)*np.array(clip)/255).astype(np.uint8)
    txt.putalpha(Image.fromarray(a))
    # shadow (hard, like rest of the identity) + glow
    shadow=Image.new('RGBA',(W,H),(0,0,0,0)); shadow.putalpha(Image.fromarray(a))
    shadow=Image.composite(Image.new('RGBA',(W,H),(0,0,0,255)),Image.new('RGBA',(W,H),(0,0,0,0)),Image.fromarray(a))
    glowm=Image.fromarray(a).filter(ImageFilter.GaussianBlur(18))
    gl=Image.new('RGBA',(W,H),(255,255,255,0)); gl.putalpha(glowm.point(lambda v:int(min(255,v*0.85*glow))))
    gl2=Image.new('RGBA',(W,H),(255,170,220,0)); gl2.putalpha(Image.fromarray(a).filter(ImageFilter.GaussianBlur(40)).point(lambda v:int(min(255,v*0.55*glow))))
    lay.alpha_composite(gl2); lay.alpha_composite(gl)
    sh=max(4,int(s*0.03)); lay.alpha_composite(shadow,(0,0)) if False else lay.paste(shadow,(sh,sh),shadow)
    lay.alpha_composite(txt)
    if scale!=1.0:
        cx,cy=(x0+total/2),(y0+hgt/2)
        M=np.array([[scale,0,cx*(1-scale)],[0,scale,cy*(1-scale)]],np.float32)
        arr=cv2.warpAffine(np.array(lay),M,(W,H),flags=cv2.INTER_LINEAR)
        lay=Image.fromarray(arr,'RGBA')
    if alpha<1: lay.putalpha(lay.getchannel('A').point(lambda v:int(v*alpha)))
    return lay


NUMC={}
def num_sprite(L,n):
    key=(L['align'],n)
    if key not in NUMC:
        s=L['num'][2]; f=font(FB,s); w=f.getbbox(str(n))[2]-f.getbbox(str(n))[0]
        if w>1030: s=int(s*1030/w); f=font(FB,s)
        NUMC[key]=text_sprite(str(n),f,max(4,int(round(s*0.024))))
    return NUMC[key]
DAYSC={}
def days_sprite(L):
    if L['align'] not in DAYSC:
        s=L['days'][2]; DAYSC[L['align']]=text_sprite('DAYS LEFT',font(FB,s),max(4,int(round(s*0.024))))
    return DAYSC[L['align']]
PCTC={}
def pct_sprite(L,v):
    key=(L['align'],v)
    if key not in PCTC: PCTC[key]=text_sprite('%d%%'%v,font(FB,L['info_s']),4)
    return PCTC[key]



def readclip(name):
    p=subprocess.run(['ffmpeg','-v','error','-i',f'work/rtL_{name}.mkv','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True)
    return np.frombuffer(p.stdout,np.uint8).reshape(-1,VH,VW,3)
# shots on the 120 BPM grid: (start,end,clip,src_from,src_to)
SHOTS=[(0,2,'swamp',0,1),(2,4,'kayak',0,1),
 (4,5,'expl',0,.55),(5,6,'bld',0,.55),(6,7,'street',0,.55),(7,8,'rest',0,.5),
 (8,9,'race',0,.33),(9,10,'swamp',.45,1),(10,11,'kayak',.45,1),(11,12,'bld',.45,1),
 (12,13,'street',.45,1),(13,14,'rest',.5,1),(14,15,'race',.33,.66),(15,16,'kayak',.2,.8),
 (16,18,'expl',.3,1),(18,20,'rest',0,1),(20,24,'card',0,1),
 (24,26,'race',0,.45),(26,27,'bld',0,1),(27,28,'street',0,1),(28,32,'race',.4,1)]
clips={n:readclip(n) for n in set(x[2] for x in SHOTS) if n!='card'}
CS,CE=20.0,24.0
CUTS=[x[0] for x in SHOTS[1:]]
KICKS=[float(t) for t in range(4,20)]+[float(t) for t in range(24,32)]
col=np.array([(50,16,39),(61,20,49),(66,22,51),(72,23,61),(81,25,67),(89,29,73),(93,31,79),(102,31,83),(109,35,91),(116,36,95),(126,38,106),(133,37,110),(138,40,114),(150,41,123),(151,43,126),(160,46,136)],np.float32)
ys=np.linspace(0,H-1,len(col)); grad=np.stack([np.interp(np.arange(H),ys,col[:,c]) for c in range(3)],1)
CARDBG=np.clip(np.repeat(grad[:,None,:],W,1)+np.random.default_rng(1).normal(0,1.6,(H,W,1)),0,255).astype(np.uint8)
PW=round(VW*H/VH)  # 608 : panel width
def mirror_fill(v):
    p=cv2.resize(v,(PW,H),interpolation=cv2.INTER_AREA)
    f=p[:,::-1]
    strip=np.concatenate([p,f,p,f,p],1)        # orig | flip | ORIG | flip | orig
    start=2*PW+PW//2-W//2                      # original panel centred on screen
    return np.ascontiguousarray(strip[:,start:start+W])
def ramp(tau,long):
    # speed ramp: fast on the hit, easing into slow-motion
    return 0.35*tau+0.65*(1-(1-tau)**2) if not long else 0.4*tau+0.6*(1-(1-tau)**1.6)
def background(t):
    for i,(a,b,n,f0,f1) in enumerate(SHOTS):
        if a<=t<b or (i==len(SHOTS)-1 and t>=b):
            if n=='card': return CARDBG.copy().astype(np.float32),n
            fr=clips[n]; tau=clamp((t-a)/(b-a)); p=f0+(f1-f0)*ramp(tau,(b-a)>1.5)
            fi=p*(len(fr)-5); i0=int(fi); w=fi-i0
            v=fr[i0].astype(np.float32)*(1-w)+fr[min(i0+1,len(fr)-1)].astype(np.float32)*w
            img=mirror_fill(v.astype(np.uint8)).astype(np.float32)
            # slow push-in over the shot + punch-in on every kick
            z=1.0+0.05*tau
            for kt in KICKS:
                if kt<=t<kt+0.4: z+=0.045*math.exp(-(t-kt)*9)
            M=np.array([[z,0,W/2*(1-z)],[0,z,H/2*(1-z)]],np.float32)
            return cv2.warpAffine(img,M,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT),n

def frame(fi):
    t=fi/FPS
    img,name=background(t)
    sh=0
    for c,amp in [(16.0,16),(20.0,10),(24.0,14)]:
        if c<=t<c+0.3: sh=amp*(1-(t-c)/0.3)
    if sh>0:
        rng=np.random.default_rng(fi); dx,dy=rng.uniform(-sh,sh,2)
        img=cv2.warpAffine(img,np.float32([[1,0,dx],[0,1,dy]]),(W,H),borderMode=cv2.BORDER_REFLECT)
    canvas=Image.fromarray(np.clip(img,0,255).astype(np.uint8)).convert('RGBA')
    card=name=='card'
    L,S=(CARD,SC) if card else (LEFT,SL)
    TA,TS,T1,T0=1.0,1.2,16.0,16.5
    if t>=TA:
        p=1.0 if t>=CS else eo((t-TA)/0.35)
        spr=S['gta']; paste(canvas,spr,xpos(L,'gta',spr)-int((1-p)*60),L['gta'][1],alpha=p)
    if t>=TS:
        if t<T1:
            u=clamp((t-TS)/(T1-TS)); n=int(round(2+367*(1-u)**2.2))
            spr=num_sprite(L,n); p=eo((t-TS)/0.25)
            # pop on every kick + when the slow last values change
            sc=1.0
            for kt in KICKS:
                if kt<=t<kt+0.3: sc+=0.06*math.exp(-(t-kt)*10)
            paste(canvas,spr,xpos(L,'num',spr),L['num'][1],alpha=p,scale=sc)
        else:
            base=T1 if t<CS else (CS if t<CE else CE)
            p=(t-base)/0.22
            sc=1.0+0.7*(1-eo(p)) if p<1 else 1.0
            for kt in KICKS:
                if kt<=t<kt+0.3 and p>=1: sc+=0.05*math.exp(-(t-kt)*10)
            spr=S['num']; paste(canvas,spr,xpos(L,'num',spr),L['num'][1],alpha=clamp(p*3),scale=sc)
    if t>=TS+0.1:
        p=1.0 if t>=CS else eo((t-TS-0.1)/0.35)
        if t<T1:
            u=clamp((t-TS)/(T1-TS)); n=int(round(2+367*(1-u)**2.2))
            spr=days_sprite(L); bf=min(0.99,1-n/380.0)
        else: spr=S['days']; bf=0.99
        paste(canvas,spr,xpos(L,'days',spr),L['days'][1]+int((1-p)*45),alpha=p)
        canvas.alpha_composite(bar_layer(L,bf,alpha=p))
        paste(canvas,pct_sprite(L,int(round(bf*100))),L['bar'][0]+2,L['info_y'],alpha=p)
        dspr=S['date']; dw=dspr[0].size[0]-2*dspr[1][0]-3
        paste(canvas,dspr,L['info_r']-dw,L['info_y']+2,alpha=p)
    if t>=T0:
        p=(t-T0)/0.4
        sc=1.0+0.25*(1-eo(p)) if p<1 else 1.0
        if card and t-CS<0.3: sc=1.0+0.15*(1-eo((t-CS)/0.3))
        e=t-T0; pulse=1.0+0.5*math.exp(-(e-math.floor(e))*6)
        if p<1: pulse=1.6*(1-eo(p))+1.0
        canvas.alpha_composite(timer_layer(L,e,T0,glow=pulse,alpha=clamp(p*2),scale=sc))
    out=np.array(canvas.convert('RGB')).astype(np.float32)
    for c in CUTS:
        big=c in (16,20,24)
        d=0.25 if big else 0.14
        if c-0.033<=t<c+d:
            kk=1.0 if t<c else (1-(t-c)/d)**1.6
            a=(0.9 if big else 0.6)*kk
            out=out*(1-a)+255*a
    if t<0.25: out=out*(t/0.25)+255*(1-t/0.25)
    if t>DUR-0.7: out=out*max(0,(DUR-t)/0.7)
    return np.clip(out*VIG,0,255).astype(np.uint8)
yy,xx=np.mgrid[0:H,0:W]; rr=np.sqrt(((xx-W/2)/(W*0.7))**2+((yy-H/2)/(H*0.85))**2)
VIG=(1-0.25*np.clip(rr-0.35,0,1)**1.5)[...,None]

if __name__=='__main__':
    if sys.argv[1]=='preview':
        ts=[float(x) for x in sys.argv[2:]]
        for t in ts: Image.fromarray(frame(int(t*FPS))).save(f'ref/w_{t}.png')
        sys.exit()
    out=sys.argv[1]
    p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-i','work/music_wide.wav','-map','0:v','-map','1:a','-c:v','libx264','-preset','slow','-crf','15','-profile:v','high','-pix_fmt','yuv420p',
        '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart','-c:a','aac','-b:a','320k','-shortest',out],stdin=subprocess.PIPE)
    for fi in range(NF):
        p.stdin.write(frame(fi).tobytes())
        if fi%120==0: print(fi,flush=True)
    p.stdin.close(); p.wait()
