#!/usr/bin/env python3
"""Video Bot v10 - Final"""

import sys,os,json,time,requests,subprocess,re,struct,math
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

GEMINI_API_KEY=os.environ["GEMINI_API_KEY"]
YOUTUBE_CLIENT_ID=os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET=os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN=os.environ["YOUTUBE_REFRESH_TOKEN"]
TELEGRAM_BOT_TOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID=os.environ["TELEGRAM_CHAT_ID"]

WORK=Path("./output")
WORK.mkdir(exist_ok=True)

GEMINI_MODELS=[("gemini-2.5-flash","v1beta"),("gemini-2.0-flash","v1"),("gemini-2.0-flash-lite","v1")]

def tg(m,e=""):
    t=f"{e} {m}".strip()
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",json={"chat_id":TELEGRAM_CHAT_ID,"text":t,"parse_mode":"HTML"},timeout=10)
    except: pass
    print(t)

def tg_foto(d,c):
    try:
        with open(d,"rb") as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",data={"chat_id":TELEGRAM_CHAT_ID,"caption":c,"parse_mode":"HTML"},files={"photo":f},timeout=30)
    except: pass

def komut_isle(cmd):
    p=[x.strip() for x in cmd.strip().split(",")]
    if len(p)==5: konu,sure,resim,tarih,saat=p; vs=0
    elif len(p)==6: konu,sure,resim,vs,tarih,saat=p; vs=int(vs)
    else: raise ValueError("Format: Konu,Dakika,Resim,VideoSayisi,GG.AA.YYYY,SS:DD")
    y=datetime.strptime(f"{tarih} {saat}","%d.%m.%Y %H:%M")
    return {"konu":konu,"sure":int(sure),"resim":int(resim),"video_sayisi":vs,"yayin_dt":y,"yayin_iso":y.strftime("%Y-%m-%dT%H:%M:%S+00:00")}

def gemini(prompt,max_tokens=8192):
    for model,api in GEMINI_MODELS:
        url=f"https://generativelanguage.googleapis.com/{api}/models/{model}:generateContent"
        headers={"Content-Type":"application/json","x-goog-api-key":GEMINI_API_KEY}
        body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"maxOutputTokens":max_tokens}}
        for _ in range(2):
            try:
                r=requests.post(url,headers=headers,json=body,timeout=90)
                if r.status_code==200:
                    c=r.json().get("candidates",[])
                    if c:
                        t=c[0].get("content",{}).get("parts",[{}])[0].get("text","").strip()
                        if t: return t,model
                    time.sleep(5)
                elif r.status_code==429: time.sleep(15)
                elif r.status_code==503: break
                else: tg(f"{model}: {r.json().get('error',{}).get('message','')[:50]}","⚠"); break
            except requests.Timeout: time.sleep(10)
    raise Exception("Gemini yanit vermedi")

def json_cikart(ham):
    ham=re.sub(r"```json\s*|```\s*","",ham).strip()
    try: return json.loads(ham)
    except: pass
    s=ham.find("{"); e=ham.rfind("}")+1
    if s!=-1 and e>s:
        seg=ham[s:e]
        try: return json.loads(seg)
        except: pass
        try: return json.loads(re.sub(r"(?<=[^\s{,:\[])'(?=[^\s},:!'\]])", "",seg))
        except: pass
    veri={}
    for a,pat in [("baslik",r'"baslik"\s*:\s*"([^"]{1,120})"'),("aciklama",r'"aciklama"\s*:\s*"([^"]{1,800})"'),("thumbnail_metin",r'"thumbnail_metin"\s*:\s*"([^"]{1,50})"')]:
        m=re.search(pat,ham)
        if m: veri[a]=m.group(1)
    tm=re.search(r'"etiketler"\s*:\s*\[(.*?)\]',ham,re.DOTALL)
    if tm: veri["etiketler"]=re.findall(r'"([^"]+)"',tm.group(1))
    if "baslik" in veri: return veri
    raise Exception(f"JSON: {ham[:60]}")

def telaffuz(metin):
    for ing,tr in [(r'\bAI\b','Ay-Ay'),(r'\bYouTube\b','Yutub'),(r'\bGoogle\b','Gugil'),(r'\bNASA\b','Nasa'),(r'\bUSA\b','ABD'),(r'\bOK\b','tamam')]:
        metin=re.sub(ing,tr,metin,flags=re.IGNORECASE)
    return re.sub(r' +',' ',metin).strip()

def senaryo_uret(konu,sure,resim_sayisi,video_sayisi):
    tg(f"'{konu}' icin icerik uretiliyor...","📚")
    kelime=sure*160
    # Konuya ozgu anahtar kelimeler
    k=konu.lower()
    for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]: k=k.replace(c,r)
    
    mekan_sozlugu = {
        "cin seddi": ["Great Wall of China ancient stone watchtower","Chinese fortress mountain mist","ancient Chinese battlefield landscape","Ming dynasty stone architecture"],
        "osmanli": ["Ottoman Empire palace architecture","Byzantine Constantinople cityscape","Ottoman army fortress medieval","Topkapi palace golden era"],
        "misir": ["ancient Egyptian pyramid Giza desert","Egyptian temple hieroglyphics stone","Nile river ancient civilization","Egyptian pharaoh tomb dark"],
        "viking": ["Viking longship ocean storm","Norse village wooden houses","Viking battlefield axes shields","Scandinavian fjord dramatic landscape"],
        "roma": ["ancient Roman Colosseum architecture","Roman legionnaire fortress","Roman aqueduct stone landscape","ancient Rome Forum ruins"],
        "uzay": ["deep space nebula galaxy","space station orbit Earth","astronaut spacewalk cosmos","alien planet landscape dramatic"],
        "doga": ["tropical rainforest waterfall","mountain glacier landscape dramatic","ocean waves cliffs dramatic","ancient forest mystical fog"],
    }
    
    # Konuya uyan mekan promptlarini bul
    bulunan = []
    for anahtar, promptlar in mekan_sozlugu.items():
        if anahtar in k:
            bulunan = promptlar
            break
    
    if not bulunan:
        # Genel tarihi mimari
        bulunan = [
            f"ancient {konu} landscape dramatic architecture no people",
            f"historical {konu} ruins stone dramatic lighting no people",
            f"epic {konu} environment cinematic landscape",
            f"mystical {konu} ancient site dramatic atmosphere",
        ]
    
    gorseller=[]
    for i in range(resim_sayisi):
        base = bulunan[i % len(bulunan)]
        if i % 3 == 2:
            base += ", aerial view, wide shot, dramatic clouds"
        elif i % 3 == 1:
            base += ", close up detail, dramatic shadow, golden hour"
        gorseller.append(base)
    meta={"baslik":f"{konu}: Tarihin Gizli Sirri!","aciklama":f"{konu} hakkinda kapsamli Turkce belgesel. #belgesel #tarih #{konu.replace(' ','')}","etiketler":[konu,"belgesel","tarih","youtube","turkce","egitim","gizem","kesfet"],"gorseller":gorseller,"thumbnail_metin":konu.upper()[:15],"thumbnail_prompt":f"{konu} epic dramatic historical cinematic no text","renk":"#1a1a2e"}
    tg("SEO optimize ediliyor...","📋")
    try:
        h,model=gemini(f"YouTube belgesel. Konu: {konu}. {sure} dk. Apostrof yok. JSON: {{\"baslik\":\"etkileyici 55 karakter emoji\",\"aciklama\":\"400 karakter hashtag\",\"etiketler\":[\"e1\",\"e2\",\"e3\",\"e4\",\"e5\",\"e6\",\"e7\",\"e8\"],\"thumbnail_metin\":\"3 KELIME\"}}",max_tokens=512)
        mini=json_cikart(h)
        for k in ["baslik","aciklama","etiketler","thumbnail_metin"]:
            if mini.get(k): meta[k]=mini[k]
        tg(f"SEO hazir: <b>{meta['baslik']}</b>","✅")
    except: tg("SEO varsayilan","⚠")
    tg(f"Senaryo yaziliyor ({kelime} kelime)...","📝")
    senaryo=""
    for _ in range(4):
        try:
            prompt_s=f"""Sen bir belgesel anlaticisisin. {konu} hakkinda {sure} dakikalik bir belgesel icin metin yazacaksin.

KESIN KURALLAR:
- Sadece duz Turkce anlatim metni yaz
- Hicbir sahne yonergesi, muzik notu, anlatici etiketi yazma
- Parantez icinde hicbir sey olmasin
- Apostrof kullanma, emoji kullanma
- Baslik veya alt baslik kullanma

{kelime} kelimelik duz Turkce metin yaz:"""
            h,model=gemini(prompt_s,max_tokens=8192)
            for bad in ["Giris Muzigi","Kapanis muzigi","Jenerik","Anlatici:","Kelime Sayimi","Iste bu","Simdi yaziyorum","tarzinda","belgesel metni:"]:
                h=re.sub(bad,'',h,flags=re.IGNORECASE)
            h=re.sub(r'\[.*?\]','',h,flags=re.DOTALL)
            h=re.sub(r'\(.*?\)','',h,flags=re.DOTALL)
            h=re.sub(r'^#+\s.*$','',h,flags=re.MULTILINE)
            h=re.sub(r'\*+','',h)
            h=re.sub(r'\n{3,}','\n\n',h).strip()
            if len(h.split())>200: senaryo=h; tg(f"Senaryo hazir ({model}): <b>{len(h.split())} kelime</b>","✅"); break
            time.sleep(5)
        except Exception as e: tg(f"Senaryo: {str(e)[:50]}","⚠"); time.sleep(10)
    if not senaryo: senaryo=f"{konu} tarihin en onemli konularindan biridir."
    meta["senaryo"]=telaffuz(senaryo)
    tg(f"Toplam: <b>{len(senaryo.split())} kelime</b>","📊")
    return meta

def muzik_uret(konu,sure_sn):
    tg("Muzik uretiliyor...","🎵")
    wav=WORK/"muzik.wav"; mp3=WORK/"muzik.mp3"
    k=konu.lower()
    for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]: k=k.replace(c,r)
    if any(x in k for x in ["viking","savas","osmanli","roma","selcuklu","tarih","cin","mogol"]): freqs=[55,82,110,165,220]; label="epic"
    elif any(x in k for x in ["misir","antik","yunan","sumer","babil","mezopotamya"]): freqs=[174,261,348,130,87]; label="ancient"
    elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot"]): freqs=[220,330,440,550,110]; label="space"
    elif any(x in k for x in ["doga","hayvan","deniz","orman"]): freqs=[196,261,329,392,130]; label="nature"
    elif any(x in k for x in ["gizem","korku","paranormal","komplo"]): freqs=[73,110,155,207,87]; label="mystery"
    else: freqs=[130,164,196,261,87]; label="cinematic"
    sr=44100; dur=int(min(sure_sn+30,7200)); n=sr*dur; fade=sr*5; amps=[0.22,0.16,0.11,0.07,0.04]
    try:
        with open(wav,'wb') as f:
            dsize=n*2
            f.write(b'RIFF'); f.write(struct.pack('<I',36+dsize))
            f.write(b'WAVEfmt '); f.write(struct.pack('<I',16))
            f.write(struct.pack('<H',1)); f.write(struct.pack('<H',1))
            f.write(struct.pack('<I',sr)); f.write(struct.pack('<I',sr*2))
            f.write(struct.pack('<H',2)); f.write(struct.pack('<H',16))
            f.write(b'data'); f.write(struct.pack('<I',dsize))
            for start in range(0,n,sr):
                end=min(start+sr,n); buf=[]
                for i in range(start,end):
                    t=i/sr; v=sum(a*math.sin(2*math.pi*fr*t) for a,fr in zip(amps,freqs))
                    v*=(1+0.015*math.sin(2*math.pi*0.25*t))
                    if i<fade: v*=i/fade
                    elif i>n-fade: v*=(n-i)/fade
                    buf.append(struct.pack('<h',int(max(-0.85,min(0.85,v))*32767)))
                f.write(b''.join(buf))
        r=subprocess.run(["ffmpeg","-y","-i",str(wav),
            "-af","volume=1.8,aecho=0.5:0.6:60:0.2",
            "-c:a","mp3","-b:a","128k",str(mp3)],capture_output=True,text=True,timeout=180)
        if r.returncode==0 and mp3.exists() and mp3.stat().st_size>1000:
            kb=mp3.stat().st_size//1024
            tg(f"Muzik hazir! ({label}, {kb}KB)","✅"); return str(mp3)
    except Exception as e: tg(f"Muzik WAV hatasi: {str(e)[:60]}","⚠")
    return ""

def gorsel_indir(i,prompt,toplam,konu=""):
    yol=WORK/f"img_{i+1:02d}.jpg"
    # Konudan anahtar kelimeler al, insan/araba yasak
    kisa = prompt[:80].replace('"','').replace("'",'')
    # Konuyu spesifik tut, insan ve arac yok
    tam_prompt = f"{kisa}, no people, no humans, no cars, no vehicles, cinematic landscape architecture 8k dramatic lighting"
    
    for seed in [i*7+42, i*13+17, i*3+99]:
        enc=quote(tam_prompt[:200])
        url=f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={seed}&nologo=true&model=flux&enhance=true"
        try:
            r=requests.get(url,timeout=90)
            if r.status_code==200 and len(r.content)>10000 and r.content[:2]==b'\xff\xd8':
                yol.write_bytes(r.content)
                tg(f"Gorsel {i+1}/{toplam} ✓","🖼")
                time.sleep(6)
                return str(yol)
            if r.status_code==429: time.sleep(30)
            else: time.sleep(8)
        except: time.sleep(8)
    
    renkler=["0x3D1C02","0x4A0E0E","0x0A1628","0x2D1B69","0x003333","0x1A3A1A","0x330033","0x1A1A00"]
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={renkler[i%len(renkler)]}:size=1920x1080:rate=1","-vframes","1","-q:v","2",str(yol)],capture_output=True)
    tg(f"Gorsel {i+1} yedek","⚠")
    return str(yol)

def gorseller_uret(promptlar,konu=""):
    n=len(promptlar)
    tg(f"{n} gorsel uretiliyor (sirali, konuya ozgu)...","🎨")
    # SIRALI - rate limit yok, konuyu her gorsele ekle
    return [gorsel_indir(i,p,n,konu) for i,p in enumerate(promptlar)]

def thumbnail_uret(prompt,metin,renk,konu):
    tg("Thumbnail uretiliyor...","🖼")
    enc=quote(f"{prompt}, youtube thumbnail dramatic vibrant no text")
    url=f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=777&nologo=true&model=flux"
    base=WORK/"thumb_base.jpg"; final=WORK/"thumbnail.jpg"
    for _ in range(3):
        try:
            r=requests.get(url,timeout=60)
            if r.status_code==200 and len(r.content)>5000 and r.content[:2]==b'\xff\xd8': base.write_bytes(r.content); break
            time.sleep(10)
        except: time.sleep(10)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1","-vframes","1",str(base)],capture_output=True)
    m=metin.upper()[:25].replace("'","").replace(":","\\:")
    k=konu.upper()[:20].replace("'","").replace(":","\\:")
    fs=80 if len(m)<=10 else 60 if len(m)<=18 else 44
    vf=(f"drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.42:color=black@0.72:t=fill,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=black@0.4:x=(w-text_w)/2+2:y=h*0.62+2:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=white:x=(w-text_w)/2:y=h*0.62:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{k}':fontsize=30:fontcolor=yellow:x=20:y=20:font=DejaVu Sans:style=Bold")
    r=subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",vf,"-q:v","2",str(final)],capture_output=True)
    if r.returncode!=0 or not final.exists(): subprocess.run(["cp",str(base),str(final)])
    if final.exists(): tg_foto(str(final),f"Thumbnail: {m}")
    tg("Thumbnail hazir!","✅"); return str(final)

def ses_uret(senaryo):
    tg("Derin belgesel sesi sentezleniyor...","🎙")
    sf=WORK/"senaryo.txt"; rf=WORK/"ses_ham.mp3"; ff=WORK/"ses.mp3"
    sub_vtt=WORK/"altyazi.vtt"; sub_srt=WORK/"altyazi.srt"
    sf.write_text(senaryo,encoding="utf-8")
    for rate,pitch,vol in [("-8%","-10Hz","+15%"),("-5%","-5Hz","+10%"),("0%","0Hz","0%")]:
        r=subprocess.run(["edge-tts","--voice","tr-TR-EmelNeural","--file",str(sf),"--write-media",str(rf),"--write-subtitles",str(sub_vtt),f"--rate={rate}",f"--pitch={pitch}",f"--volume={vol}"],capture_output=True,text=True,timeout=600)
        if r.returncode==0 and rf.exists() and rf.stat().st_size>1000: tg(f"Ses uretildi (rate={rate})","✅"); break
        time.sleep(3)
    else:
        r2=subprocess.run(["edge-tts","--voice","tr-TR-EmelNeural","--file",str(sf),"--write-media",str(rf),"--write-subtitles",str(sub_vtt)],capture_output=True,text=True,timeout=600)
        if r2.returncode!=0 or not rf.exists(): raise Exception(f"TTS: {r2.stderr[-80:]}")
    subprocess.run(["ffmpeg","-y","-i",str(rf),"-af","equalizer=f=80:width_type=o:width=2:g=5,equalizer=f=200:width_type=o:width=2:g=3,equalizer=f=3000:width_type=o:width=2:g=-3,equalizer=f=8000:width_type=o:width=2:g=-5,acompressor=threshold=-16dB:ratio=3:attack=5:release=60,volume=1.3","-c:a","mp3","-b:a","192k",str(ff)],capture_output=True)
    kullan=str(ff) if ff.exists() else str(rf)
    if sub_vtt.exists():
        vtt=sub_vtt.read_text(encoding="utf-8"); srt=[]; say=1
        for blok in re.split(r'\n\n+',vtt):
            if '-->' in blok:
                sat=blok.strip().split('\n')
                zaman=next((s for s in sat if '-->' in s),None)
                if zaman:
                    zaman=re.sub(r'(\d{2}:\d{2}:\d{2})\.(\d{3})',r'\1,\2',zaman).strip()
                    mt=[s for s in sat if '-->' not in s and s.strip() and not s.startswith('NOTE') and not s.strip().isdigit()]
                    if mt: srt+=[str(say),zaman]+mt+['']; say+=1
        sub_srt.write_text('\n'.join(srt),encoding="utf-8")
    probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",kullan],capture_output=True,text=True)
    sure=float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b>","✅")
    return kullan,sure,str(sub_srt) if sub_srt.exists() else ""

def ses_miksle(anlati,muzik,sure):
    if not muzik or not os.path.exists(muzik):
        tg("Muzik dosyasi yok, sadece anlatici","⚠")
        return anlati
    try:
        pb=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",muzik],capture_output=True,text=True)
        muzik_sure=float(json.loads(pb.stdout)["format"]["duration"])
        if muzik_sure<3:
            tg("Muzik cok kisa","⚠"); return anlati
        tg(f"Muzik bulundu ({muzik_sure:.0f}sn), karistiriliyor...","🎚")
    except Exception as e:
        tg(f"Muzik kontrol hatasi: {str(e)[:40]}","⚠"); return anlati
    
    miksl=WORK/"miksl.mp3"
    # Muzigi once WAV'a cevir - format uyumsuzlugunu onler
    muzik_wav=WORK/"muzik_cevir.wav"
    subprocess.run(["ffmpeg","-y","-i",muzik,"-ar","44100","-ac","1",str(muzik_wav)],capture_output=True)
    anlati_wav=WORK/"anlati_cevir.wav"  
    subprocess.run(["ffmpeg","-y","-i",anlati,"-ar","44100","-ac","1",str(anlati_wav)],capture_output=True)
    
    muzik_src=str(muzik_wav) if muzik_wav.exists() else muzik
    anlati_src=str(anlati_wav) if anlati_wav.exists() else anlati
    
    cmd=["ffmpeg","-y",
         "-i",anlati_src,
         "-stream_loop","-1","-i",muzik_src,
         "-filter_complex",
         f"[0:a]volume=1.0[a1];[1:a]volume=0.35[a2];[a1][a2]amix=inputs=2:duration=first[out]",
         "-map","[out]",
         "-c:a","mp3","-b:a","192k","-t",str(int(sure)),
         str(miksl)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode==0 and miksl.exists() and miksl.stat().st_size>10000:
        tg("Muzik basariyla eklendi!","✅")
        return str(miksl)
    tg(f"Miks hatasi: {r.stderr[-100:]}","⚠")
    return anlati

def video_montaj(gorseller,ses,altyazi_srt,toplam_sure):
    tg(f"Video montajlaniyor...\n{len(gorseller)} gorsel | 6 farkli efekt\n⏳ ~{len(gorseller)//2+5} dk","🎬")
    cikis=WORK/"video_raw.mp4"; cikis_son=WORK/"video.mp4"; liste=WORK/"liste.txt"
    her=toplam_sure/len(gorseller); fps=25
    tg(f"Toplam: {toplam_sure/60:.1f} dk | Gorsel basina: {her:.1f}s","⚙")
    segmentler=[]
    for i,gorsel in enumerate(gorseller):
        seg=WORK/f"seg_{i:03d}.mp4"; fo=max(0,her-0.6); fr=max(int(her*fps),25); ef=i%6
        ef=i%8
        if ef==0:   # Zoom in
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0008,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==1: # Zoom out
            vf=f"scale=iw*2:ih*2,zoompan=z='if(lte(on,1),1.15,max(zoom-0.001,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==2: # Sol sag pan
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)+on*0.8':y='ih/2-(ih/zoom/2)':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==3: # Sag sol pan
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)-on*0.8':y='ih/2-(ih/zoom/2)':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==4: # Asagi yukari
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0006,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*0.6':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==5: # Yukari asagi + vignette
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0006,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-on*0.6':d={fr}:s=1920x1080:fps={fps},vignette=angle=PI/5,fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        elif ef==6: # Ken Burns diagonal
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0007,1.1)':x='iw/2-(iw/zoom/2)+on*0.4':y='ih/2-(ih/zoom/2)+on*0.3':d={fr}:s=1920x1080:fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        else:       # Zoom in + brightness pulse
            vf=f"scale=iw*2:ih*2,zoompan=z='min(zoom+0.0008,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s=1920x1080:fps={fps},eq=brightness='0.03*sin(2*PI*t/8)':contrast=1.05,fade=t=in:st=0:d=0.6,fade=t=out:st={fo:.2f}:d=0.6"
        cmd1=["ffmpeg","-y","-loop","1","-t",str(her+1),"-i",gorsel,"-vf",vf,"-t",str(her),"-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
        r=subprocess.run(cmd1,capture_output=True,text=True,timeout=300)
        if r.returncode==0 and seg.exists() and seg.stat().st_size>500: segmentler.append(str(seg)); tg(f"Seg {i+1}/{len(gorseller)} ef{ef+1} ok","🎬")
        else:
            cmd2=["ffmpeg","-y","-loop","1","-t",str(her),"-i",gorsel,"-vf",f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5","-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
            r2=subprocess.run(cmd2,capture_output=True,text=True,timeout=120)
            if r2.returncode==0 and seg.exists(): segmentler.append(str(seg)); tg(f"Seg {i+1} yedek","⚠")
    if not segmentler: raise Exception("Segment olusturulamadi!")
    with open(liste,"w") as f:
        for s in segmentler: f.write(f"file '{os.path.abspath(s)}'\n")
    cmd_son=["ffmpeg","-y","-f","concat","-safe","0","-i",str(liste),"-i",ses,"-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(cikis)]
    r=subprocess.run(cmd_son,capture_output=True,text=True,timeout=3600)
    if r.returncode!=0:
        r=subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(liste),"-i",ses,"-c:v","libx264","-preset","ultrafast","-crf","26","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(cikis)],capture_output=True,text=True,timeout=3600)
        if r.returncode!=0: raise Exception(f"Birlestirme: {r.stderr[-150:]}")
    if altyazi_srt and os.path.exists(altyazi_srt):
        tg("Altyazi ekleniyor (sari, siyah cerceve)...","📝")
        safe=os.path.abspath(altyazi_srt).replace('\\','/').replace(':','\\:')
        vf_sub=f"subtitles='{safe}':force_style='FontName=DejaVu Sans,FontSize=14,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=30'"
        cmd_sub=["ffmpeg","-y","-i",str(cikis),"-vf",vf_sub,"-c:v","libx264","-preset","ultrafast","-crf","26","-c:a","copy",str(cikis_son)]
        r=subprocess.run(cmd_sub,capture_output=True,text=True,timeout=3600)
        if r.returncode==0 and cikis_son.exists(): tg("Altyazi eklendi!","✅")
        else: subprocess.run(["cp",str(cikis),str(cikis_son)])
    else: subprocess.run(["cp",str(cikis),str(cikis_son)])
    mb=os.path.getsize(cikis_son)/1024/1024; tg(f"Video hazir! <b>{mb:.0f} MB</b>","✅"); return str(cikis_son)

def yt_token():
    r=requests.post("https://oauth2.googleapis.com/token",data={"client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,"refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},timeout=30)
    if r.status_code!=200: raise Exception(f"YT token: {r.text[:100]}")
    return r.json()["access_token"]

def youtube_yukle(video,thumb,baslik,aciklama,etiketler,yayin_iso):
    tg("YouTube'a yukleniyor...","📤")
    token=yt_token()
    meta={"snippet":{"title":baslik[:100],"description":aciklama[:5000],"tags":etiketler[:15],"categoryId":"27"},"status":{"privacyStatus":"private","publishAt":yayin_iso,"selfDeclaredMadeForKids":False}}
    boyut=os.path.getsize(video)
    init=requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",headers={"Authorization":f"Bearer {token}","Content-Type":"application/json","X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(boyut)},json=meta,timeout=30)
    if init.status_code!=200: raise Exception(f"YT init: {init.text[:100]}")
    tg(f"Video yukleniyor ({boyut//1024//1024} MB)...","⏳")
    with open(video,"rb") as f:
        r=requests.put(init.headers["Location"],headers={"Content-Type":"video/mp4"},data=f,timeout=3600)
    if r.status_code not in [200,201]: raise Exception(f"YT: {r.text[:100]}")
    vid_id=r.json()["id"]; vid_url=f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}","✅")
    try:
        with open(thumb,"rb") as tf:
            tr=requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},data=tf,timeout=60)
        tg("Thumbnail yuklendi!" if tr.status_code in[200,201] else f"Thumbnail({tr.status_code})","✅" if tr.status_code in[200,201] else "⚠")
    except: pass
    return vid_url,vid_id

def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else ""
    if not cmd: sys.exit(1)
    try: p=komut_isle(cmd)
    except Exception as e: tg(str(e),"❌"); sys.exit(1)
    tg(f"<b>Video Bot v10 Basladi!</b>\n\nKonu: <b>{p['konu']}</b>\nSure: {p['sure']} dk\nGorsel: {p['resim']} adet\nYayin: {p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}\nMuzik: Konuya ozel\nAltyazi: Sari+siyah cerceve\nEfektler: 6 farkli","🚀")
    try:
        icerik=senaryo_uret(p["konu"],p["sure"],p["resim"],p["video_sayisi"])
        (WORK/"metadata.json").write_text(json.dumps(icerik,ensure_ascii=False,indent=2))
        muzik=muzik_uret(p["konu"],p["sure"]*60+120)
        gp=icerik.get("gorseller",[])
        while len(gp)<p["resim"]: gp.append(f"{p['konu']} dramatic historical cinematic scene {len(gp)+1} 8k")
        gorseller=gorseller_uret(gp,p["konu"])
        thumb=thumbnail_uret(icerik.get("thumbnail_prompt",f"{p['konu']} epic dramatic cinematic"),icerik.get("thumbnail_metin",p["konu"].upper()[:15]),icerik.get("renk","#1a1a2e"),p["konu"])
        ses,sure,altyazi=ses_uret(icerik["senaryo"])
        miksli=ses_miksle(ses,muzik,sure)
        video=video_montaj(gorseller,miksli,altyazi,sure)
        vid_url,_=youtube_yukle(video,thumb,icerik.get("baslik",p["konu"]+" Belgeseli"),icerik.get("aciklama",p["konu"]+" belgeseli. #belgesel"),icerik.get("etiketler",[p["konu"],"belgesel","tarih"]),p["yayin_iso"])
        tg(f"<b>TAMAMLANDI!</b>\n\n<b>{icerik.get('baslik',p['konu'])}</b>\n\n{vid_url}\n\nYayin: <b>{p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}</b>","🎉")
        (WORK/"result.json").write_text(json.dumps({"status":"success","video_url":vid_url},ensure_ascii=False))
    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:300]}","❌")
        (WORK/"result.json").write_text(json.dumps({"status":"error","error":str(e)}))
        sys.exit(1)

if __name__=="__main__":
    main()