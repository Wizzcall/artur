import numpy as np, subprocess, cv2, math, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1080,1920,30
DUR=16.0; NF=int(DUR*FPS)
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

# ---------- layouts measured on the original ----------
LEFT=dict(gta=(22,632,80),num=(26,804,486),days=(22,1224,118),bar=(19,1370,849,1399),info_y=1431,info_s=62,info_r=845,
          timer_y=1545,timer_s=150,align='left')
CARD=dict(gta=(None,215,134),num=(None,461,824),days=(None,1177,152),bar=(94,1350,987,1389),info_y=1429,info_s=66,info_r=983,
          timer_y=1560,timer_s=165,align='center')
def sprites(L):
    S={}
    sh=lambda s:max(4,int(round(s*0.024)))
    S['gta']=text_sprite('GTA VI',font(FB,L['gta'][2]),sh(L['gta'][2]))
    S['num']=text_sprite('1',font(FB,L['num'][2]),sh(L['num'][2]))
    S['days']=text_sprite('DAY LEFT',font(FB,L['days'][2]),sh(L['days'][2]))
    S['pct']=text_sprite('99%',font(FB,L['info_s']),4)
    S['date']=text_sprite('NOV 19, 2026',font(FB,L['info_s']*0.92 if False else int(L['info_s']*0.92)),4)
    return S
SL,SC=sprites(LEFT),sprites(CARD)
def capfix(spr,L,key):
    # glyph top from bbox -> measured cap top; Inter bbox already tight, fine
    return spr
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

# ---------- backgrounds ----------
def readclip(name):
    p=subprocess.run(['ffmpeg','-v','error','-i',f'work/rt_{name}.mkv','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True)
    a=np.frombuffer(p.stdout,np.uint8); return a.reshape(-1,H,W,3)
TL=[('swamp',0.0,1.0),('kayak',1.0,2.0),('expl',2.0,3.0),('bld',3.0,4.0),('street',4.0,5.0),('rest',5.0,7.5),('card',7.5,10.0),('race',10.0,16.0)]
clips={n:readclip(n) for n,_,_ in TL if n!='card'}
# card gradient sampled from the original end card
col=np.array([(50,16,39),(61,20,49),(66,22,51),(72,23,61),(81,25,67),(89,29,73),(93,31,79),(102,31,83),(109,35,91),(116,36,95),(126,38,106),(133,37,110),(138,40,114),(150,41,123),(151,43,126),(160,46,136)],np.float32)
ys=np.linspace(0,H-1,len(col)); grad=np.stack([np.interp(np.arange(H),ys,col[:,c]) for c in range(3)],1)
CARDBG=np.repeat(grad[:,None,:],W,1)
noise=np.random.default_rng(1).normal(0,1.6,(H,W,1))
CARDBG=np.clip(CARDBG+noise,0,255).astype(np.uint8)

def background(t):
    for n,a,b in TL:
        if a<=t<b or (n=='race' and t>=b):
            if n=='card': return CARDBG.copy(),n,a,b
            fr=clips[n]; i=min(len(fr)-1,int(round((t-a)*FPS)))
            img=fr[i]
            # gentle push-in per shot (Ken Burns)
            z=1.0+0.05*clamp((t-a)/(b-a))
            if n=='race': z=1.0+0.07*clamp((t-a)/(b-a))
            M=np.array([[z,0,W/2*(1-z)],[0,z,H/2*(1-z)]],np.float32)
            return cv2.warpAffine(img,M,(W,H),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT),n,a,b
CUTS=[1.0,2.0,3.0,4.0,5.0,7.5,10.0]

def frame(fi):
    t=fi/FPS
    bg,name,a,b=background(t)
    img=bg.astype(np.float32)
    # shake on the "1" slam and the card/race hits
    sh=0
    for c,amp in [(5.0,18),(7.5,12),(10.0,14)]:
        if c<=t<c+0.3: sh=amp*(1-(t-c)/0.3)
    if sh>0:
        rng=np.random.default_rng(fi); dx,dy=rng.uniform(-sh,sh,2)
        img=cv2.warpAffine(img,np.float32([[1,0,dx],[0,1,dy]]),(W,H),borderMode=cv2.BORDER_REFLECT)
    canvas=Image.fromarray(np.clip(img,0,255).astype(np.uint8)).convert('RGBA')
    L,S=(CARD,SC) if name=='card' else (LEFT,SL)
    card=name=='card'
    TA,TS,T1,T0=0.55,0.75,5.0,5.6   # text in, count start, slam to 1, timer in
    # GTA VI
    if t>=TA:
        p=1.0 if t>=7.5 else eo((t-TA)/0.35)
        spr=S['gta']; x=xpos(L,'gta',spr)-int((1-p)*80); paste(canvas,spr,x,L['gta'][1],alpha=p)
    # day count: 369 -> 2 decelerating (slow-motion ending), then slam on 1
    if t>=TS:
        if t<T1:
            u=clamp((t-TS)/(T1-TS))
            n=int(round(2+367*(1-u)**2.6))
            spr=num_sprite(L,n); p=eo((t-TS)/0.25)
            # tiny pop each time the value changes in the slow part
            sc=1.0
            if n<=9:
                tu=(t-TS)/(T1-TS); 
                # time since this value appeared
                lo=TS; 
                k=0.0
                for back in range(1,40):
                    tt=t-back/FPS
                    if tt<TS: break
                    uu=clamp((tt-TS)/(T1-TS))
                    if int(round(2+367*(1-uu)**2.6))!=n: break
                    k+=1
                sc=1.0+0.12*max(0,1-k/5)
            paste(canvas,spr,xpos(L,'num',spr),L['num'][1],alpha=p,scale=sc)
        else:
            if t<7.5: p=(t-T1)/0.22
            elif t<10: p=(t-7.5)/0.22
            else: p=(t-10.0)/0.22
            sc=1.0+0.7*(1-eo(p)) if p<1 else 1.0
            spr=S['num']; paste(canvas,spr,xpos(L,'num',spr),L['num'][1],alpha=clamp(p*3),scale=sc)
    # DAYS LEFT / DAY LEFT + bar + info
    if t>=TS+0.1:
        p=1.0 if t>=7.5 else eo((t-TS-0.1)/0.35)
        if t<T1:
            u=clamp((t-TS)/(T1-TS)); n=int(round(2+367*(1-u)**2.6))
            spr=days_sprite(L); bf=min(0.99,1-n/380.0)
        else:
            spr=S['days']; bf=0.99
        paste(canvas,spr,xpos(L,'days',spr),L['days'][1]+int((1-p)*60),alpha=p)
        canvas.alpha_composite(bar_layer(L,bf,alpha=p))
        pct=pct_sprite(L,int(round(bf*100)))
        paste(canvas,pct,L['bar'][0]+2,L['info_y'],alpha=p)
        dspr=S['date']; dw=dspr[0].size[0]-2*dspr[1][0]-4
        paste(canvas,dspr,L['info_r']-dw,L['info_y']+3,alpha=p)
    # timer
    if t>=T0:
        p=(t-T0)/0.4
        sc=1.0+0.25*(1-eo(p)) if p<1 else 1.0
        if card and t-7.5<0.3: sc=1.0+0.15*(1-eo((t-7.5)/0.3))
        e=t-T0; pulse=1.0+0.5*math.exp(-(e-math.floor(e))*6)
        if p<1: pulse=1.6*(1-eo(p))+1.0
        canvas.alpha_composite(timer_layer(L,e,T0,glow=pulse,alpha=clamp(p*2),scale=sc))
    out=np.array(canvas.convert('RGB')).astype(np.float32)
    # white flash transitions (same style as the original edit)
    for c in CUTS:
        if c-0.04<=t<c+0.25:
            k=1.0 if t<c else (1-(t-c)/0.25)**1.6
            out=out*(1-0.9*k)+255*0.9*k
    if t<0.25: out=out*(t/0.25)+255*(1-t/0.25)  # opens from white like the source
    # subtle vignette for a cleaner finish
    return np.clip(out*VIG,0,255).astype(np.uint8)
yy,xx=np.mgrid[0:H,0:W]; rr=np.sqrt(((xx-W/2)/(W*0.75))**2+((yy-H/2)/(H*0.75))**2)
VIG=(1-0.22*np.clip(rr-0.35,0,1)**1.5)[...,None]

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='preview':
        for t in [0.4,0.9,1.5,2.5,3.5,4.2,4.6,4.9,5.1,6.0,8.0,12]:
            Image.fromarray(frame(int(t*FPS))).resize((360,640)).save(f'ref/pv_{t}.png')
        sys.exit()
    out=sys.argv[1]
    p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-i','work/music.wav','-map','0:v','-map','1:a','-c:v','libx264','-preset','slow','-crf','14','-profile:v','high','-pix_fmt','yuv420p',
        '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart','-c:a','aac','-b:a','320k','-shortest',out],stdin=subprocess.PIPE)
    for fi in range(NF):
        p.stdin.write(frame(fi).tobytes())
        if fi%60==0: print(fi,flush=True)
    p.stdin.close(); p.wait()
