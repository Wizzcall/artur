import numpy as np, wave
SR=44100; DUR=32.0; N=int(SR*DUR)
L=np.zeros(N); R=np.zeros(N)
rng=np.random.default_rng(7)
BPM=120; B=60/BPM
def add(sig,t,gain=1.0,pan=0.0):
    i=int(t*SR); j=min(N,i+len(sig))
    if j<=i: return
    s=sig[:j-i]*gain
    L[i:j]+=s*np.sqrt((1-pan)/2)*1.414; R[i:j]+=s*np.sqrt((1+pan)/2)*1.414
def env(n,a,d):
    t=np.arange(n)/SR; return np.minimum(1,t/max(a,1e-4))*np.exp(-t/d)
def kick():
    n=int(.45*SR); t=np.arange(n)/SR
    f=45+140*np.exp(-t*30); ph=2*np.pi*np.cumsum(f)/SR
    return np.tanh(2.2*np.sin(ph)*np.exp(-t*7))*0.9
def b808(freq,length,glide_to=None):
    n=int(length*SR); t=np.arange(n)/SR
    f=np.full(n,freq)
    if glide_to: f=freq*(glide_to/freq)**np.clip((t-length*0.6)/(length*0.3),0,1)
    ph=2*np.pi*np.cumsum(f)/SR
    e=np.minimum(1,t/0.005)*np.exp(-t/1.2)*np.clip((length-t)/0.03,0,1)
    return np.tanh(1.8*np.sin(ph))*e*0.75
def clap():
    n=int(.3*SR); t=np.arange(n)/SR; x=rng.normal(0,1,n)
    # bandpass-ish
    x=np.convolve(x,np.ones(3)/3,'same')-np.convolve(x,np.ones(40)/40,'same')
    e=np.zeros(n)
    for o in (0,.011,.022): e+=np.where(t>=o,np.exp(-(t-o)*60),0)*(t>=o)
    e+=np.where(t>.03,np.exp(-(t-.03)*14),0)
    return x*e*0.45
def hat(open_=False):
    n=int((.25 if open_ else .06)*SR); t=np.arange(n)/SR; x=rng.normal(0,1,n)
    x=x-np.convolve(x,np.ones(6)/6,'same')
    return x*np.exp(-t*(12 if open_ else 70))*0.16
def tick(high=True):
    n=int(.05*SR); t=np.arange(n)/SR
    return (np.sin(2*np.pi*(3200 if high else 2400)*t)+0.5*np.sin(2*np.pi*5100*t))*np.exp(-t*160)*0.22
def impact(length=2.2):
    n=int(length*SR); t=np.arange(n)/SR
    sub=np.sin(2*np.pi*np.cumsum(35+80*np.exp(-t*8))/SR)*np.exp(-t*1.6)
    x=rng.normal(0,1,n); lp=np.convolve(x,np.ones(25)/25,'same')
    noise=lp*np.exp(-t*3.5)*2.2+ x*np.exp(-t*18)*0.25
    return np.tanh(sub*1.4+noise*0.5)*0.85
def riser(length):
    n=int(length*SR); t=np.arange(n)/SR; x=rng.normal(0,1,n)
    out=np.zeros(n); k=np.linspace(60,2,n).astype(int)
    cs=np.cumsum(np.concatenate([[0],x]))
    for i in range(n):  # moving average with shrinking window = rising filter
        w=k[i]; out[i]=(cs[i+1]-cs[max(0,i+1-w)])/w
    return out*(t/length)**2*1.2
def pad(freqs,length):
    n=int(length*SR); t=np.arange(n)/SR; s=np.zeros(n)
    for f in freqs:
        for det in (-0.12,0,0.11):
            ph=2*np.pi*f*(1+det/100)*t+rng.uniform(0,6)
            s+=2*(ph/(2*np.pi)%1)-1
    s=np.convolve(s,np.ones(18)/18,'same')/len(freqs)/3
    e=np.minimum(1,t/0.25)*np.minimum(1,(length-t)/0.3)
    return s*e*0.35
def bell(f,length=0.8):
    n=int(length*SR); t=np.arange(n)/SR
    return (np.sin(2*np.pi*f*t+1.5*np.sin(2*np.pi*f*3.5*t)*np.exp(-t*6)))*np.exp(-t*3.2)*0.18
A=55.0
nt=lambda semi: 220*2**(semi/12)
# chord prog per bar (2s): Am, F, Dm, E  (dark trap vibe)
prog=[[0,3,7],[-4,0,3],[-7,-4,0],[-5,-1,2]]
for bar in range(16):
    ch=prog[bar%4]; add(pad([nt(c) for c in ch]+[nt(ch[0]-12)],2.05),bar*2.0,0.6 if bar<2 else 0.85)
mel=[(0,12),(0.75,10),(1.5,7),(2.0,8),(2.75,7),(3.5,3)]
for rep in range(8):
    for o,s_ in mel:
        t=rep*4.0+o
        if 20.0<=t<24.0: continue
        add(bell(nt(s_)),t,0.8 if t<4 else 1.0,pan=0.25)
bassnotes=[A, A*2**(-4/12), A*2**(-7/12)*2, A*2**(-5/12)]
def groove(t0,t1,full=True,clapg=1.0):
    t=t0
    while t<t1-1e-6:
        beat=int(round(t/B)); pos=beat%4
        if pos in (0,2): add(kick(),t,1.0)          # kick every second = every cut
        if pos in (1,3): add(clap(),t,clapg)
        add(hat(),t,0.85,pan=-0.2)
        if full: add(hat(),t+B/2,0.6,pan=-0.2)
        if full and beat%8==7:
            for r in range(4): add(hat(),t+B/2+r*B/8,0.7,pan=-0.2)
        t+=B
def bass(t0,t1):
    t=t0
    while t<t1-1e-6:
        bar=int(t/2.0)%4; f=bassnotes[bar]
        add(b808(f,0.9),t,0.9)
        add(b808(f,0.55,glide_to=f*1.5 if bar==3 else None),t+1.0,0.8)
        t+=2.0
# intro 0-4
for i in range(8): add(hat(),i*B,0.45)
add(impact(1.5),1.0,0.5)
add(riser(1.0),3.0,0.5)
for r in range(8): add(hat(),3.5+r*B/8,0.4+0.05*r)
# countdown groove 4-16
groove(4.0,12.0,full=False); bass(4.0,12.0)
groove(12.0,15.0,full=True); bass(12.0,15.0)
for r in range(16): add(hat(),15.0+r*B/8,0.5+0.03*r,pan=-0.2)
add(riser(1.0),15.0,0.6)
for r in range(8): add(clap()*0.5,15.5+r*B/8,0.3+0.08*r)
TS,T1=1.2,16.0
prev=None
for k in range(int(TS*1000),int(T1*1000)):
    t=k/1000; u=(t-TS)/(T1-TS); n=int(round(2+367*(1-u)**2.2))
    if prev is not None and n!=prev and n<=12: add(tick(True),t,0.8)
    prev=n
add(impact(2.4),16.0,1.15)
groove(16.0,20.0); bass(16.0,20.0)
add(riser(0.9),19.1,0.5)
add(impact(2.5),20.0,1.0)
add(b808(A,3.8),20.0,0.6)
for i in range(4): add(kick()*0.6,22.0+i*B,0.6)
for r in range(16): add(clap()*0.5,23.5+r*B/16,0.2+0.05*r)
add(riser(0.5),23.5,0.55)
add(impact(),24.0,1.15)
groove(24.0,32.0); bass(24.0,32.0)
for s_ in np.arange(16.5,32.0,1.0): add(tick(True),s_,0.9,pan=0.1); add(tick(False),s_+0.5,0.35,pan=-0.1)
mix=np.stack([L,R],1)
# fade out last 0.6s, fade in 0.05
fo=np.clip((DUR-np.arange(N)/SR)/0.6,0,1)[:,None]; mix*=fo
mix=mix/np.max(np.abs(mix))*0.98
mix=np.tanh(mix*1.25)/np.tanh(1.25)*0.95
w=wave.open('work/music_wide.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix*32767).astype(np.int16).tobytes()); w.close(); print('ok')
