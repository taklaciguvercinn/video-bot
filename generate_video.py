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

    bulunan = []
    for anahtar, promptlar in mekan_sozlugu.items():
        if anahtar in k:
            bulunan = promptlar
            break

    if not bulunan:
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

def muzik_uret(konu, sure_sn):
    tg("Muzik uretiliyor...", "🎵")
    wav = WORK / "muzik.wav"
    mp3 = WORK / "muzik.mp3"

    k = konu.lower()
    for c, r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]:
        k = k.replace(c, r)

    import hashlib
    seed_val = int(hashlib.md5(konu.encode()).hexdigest()[:8], 16) % 1000

    if any(x in k for x in ["viking","savas","osmanli","roma","selcuklu","tarih","cin","mogol"]):
        kategoriler = [
            {"base":[55,110,165,220,82],"amps":[0.28,0.18,0.12,0.07,0.20],"chords":[1.0,1.12,0.94,1.06],"dur":6,"label":"epic_1"},
            {"base":[41,82,123,165,55], "amps":[0.26,0.20,0.13,0.06,0.22],"chords":[1.0,1.19,0.89,1.12],"dur":5,"label":"epic_2"},
            {"base":[55,110,220,165,82],"amps":[0.24,0.18,0.15,0.08,0.20],"chords":[1.0,1.06,1.12,0.94],"dur":7,"label":"epic_3"},
        ]
        bpm = 80
    elif any(x in k for x in ["misir","antik","yunan","sumer","babil","mezopotamya"]):
        kategoriler = [
            {"base":[174,261,348,130,87],"amps":[0.22,0.17,0.12,0.10,0.18],"chords":[1.0,1.12,1.26,1.06],"dur":8,"label":"ancient_1"},
            {"base":[196,294,392,147,98],"amps":[0.20,0.16,0.13,0.11,0.17],"chords":[1.0,1.19,0.94,1.12],"dur":7,"label":"ancient_2"},
            {"base":[164,246,328,123,82],"amps":[0.24,0.17,0.11,0.09,0.19],"chords":[1.0,1.06,1.19,0.89],"dur":6,"label":"ancient_3"},
        ]
        bpm = 65
    elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot","gelecek"]):
        kategoriler = [
            {"base":[220,330,440,550,110],"amps":[0.18,0.14,0.10,0.06,0.16],"chords":[1.0,1.12,1.33,1.06],"dur":9,"label":"space_1"},
            {"base":[196,294,392,490,98], "amps":[0.20,0.15,0.11,0.05,0.15],"chords":[1.0,1.19,1.06,1.26],"dur":8,"label":"space_2"},
            {"base":[233,349,466,582,116],"amps":[0.16,0.13,0.12,0.07,0.17],"chords":[1.0,1.06,1.33,0.94],"dur":10,"label":"space_3"},
        ]
        bpm = 90
    elif any(x in k for x in ["doga","hayvan","deniz","orman","okyanus"]):
        kategoriler = [
            {"base":[196,261,329,392,130],"amps":[0.18,0.14,0.12,0.08,0.16],"chords":[1.0,1.12,1.25,1.06],"dur":8,"label":"nature_1"},
            {"base":[174,232,293,349,116],"amps":[0.20,0.15,0.11,0.07,0.15],"chords":[1.0,1.19,1.06,1.12],"dur":7,"label":"nature_2"},
            {"base":[207,276,347,415,138],"amps":[0.16,0.13,0.13,0.09,0.17],"chords":[1.0,1.06,1.19,0.94],"dur":9,"label":"nature_3"},
        ]
        bpm = 60
    elif any(x in k for x in ["gizem","korku","paranormal","komplo","karanlik"]):
        kategoriler = [
            {"base":[73,110,155,207,87], "amps":[0.22,0.16,0.11,0.07,0.20],"chords":[1.0,1.06,0.89,1.12],"dur":7,"label":"mystery_1"},
            {"base":[65,98,138,184,77],  "amps":[0.24,0.17,0.10,0.06,0.21],"chords":[1.0,0.94,1.06,1.19],"dur":6,"label":"mystery_2"},
            {"base":[82,123,174,232,98], "amps":[0.20,0.15,0.12,0.08,0.19],"chords":[1.0,1.12,0.89,1.06],"dur":8,"label":"mystery_3"},
        ]
        bpm = 55
    else:
        kategoriler = [
            {"base":[130,164,196,261,87],"amps":[0.20,0.16,0.12,0.07,0.18],"chords":[1.0,1.12,1.25,1.06],"dur":7,"label":"cinematic_1"},
            {"base":[138,174,207,277,92],"amps":[0.18,0.15,0.13,0.08,0.17],"chords":[1.0,1.19,1.06,1.12],"dur":6,"label":"cinematic_2"},
            {"base":[123,155,185,247,82],"amps":[0.22,0.14,0.11,0.06,0.19],"chords":[1.0,1.06,1.19,0.94],"dur":8,"label":"cinematic_3"},
        ]
        bpm = 70

    cfg        = kategoriler[seed_val % len(kategoriler)]
    base_freqs = cfg["base"]
    amps       = cfg["amps"]
    chords     = cfg["chords"]
    chord_dur  = cfg["dur"]
    label      = cfg["label"]

    sr          = 44100
    dur         = int(min(sure_sn + 30, 7200))
    n           = sr * dur
    fade        = sr * 3
    beat_period = int(sr * 60 / bpm)
    beat_env_len= int(sr * 0.20)

    def smooth_env(pos, length):
        if pos >= length: return 0.0
        return math.sin(math.pi * pos / length) ** 2

    try:
        with open(wav, 'wb') as f:
            dsize = n * 2
            f.write(b'RIFF'); f.write(struct.pack('<I', 36 + dsize))
            f.write(b'WAVEfmt '); f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1)); f.write(struct.pack('<H', 1))
            f.write(struct.pack('<I', sr)); f.write(struct.pack('<I', sr * 2))
            f.write(struct.pack('<H', 2)); f.write(struct.pack('<H', 16))
            f.write(b'data'); f.write(struct.pack('<I', dsize))

            for start in range(0, n, sr):
                end = min(start + sr, n)
                buf = []
                for i in range(start, end):
                    t = i / sr

                    # Chord progression
                    chord_idx = int(t / chord_dur) % len(chords)
                    chord_pos = t % chord_dur
                    xfade = 0.5
                    if chord_pos < xfade:
                        prev_idx   = (chord_idx - 1) % len(chords)
                        blend      = chord_pos / xfade
                        multiplier = chords[prev_idx] * (1 - blend) + chords[chord_idx] * blend
                    else:
                        multiplier = chords[chord_idx]

                    # Ana harmonikler
                    v = sum(a * math.sin(2 * math.pi * fr * multiplier * t)
                            for a, fr in zip(amps, base_freqs))

                    # 3. harmonik - dolgunluk
                    v += amps[0] * 0.08 * math.sin(2 * math.pi * base_freqs[0] * multiplier * 3 * t)

                    # Ritim - smooth envelope, patlama yok
                    pos_in_beat = i % beat_period
                    v += 0.10 * smooth_env(pos_in_beat, beat_env_len) * math.sin(2 * math.pi * 70 * multiplier * t)

                    # Hafif tremolo
                    v *= (1 + 0.02 * math.sin(2 * math.pi * 0.15 * t))

                    # Fade in/out
                    if i < fade:   v *= i / fade
                    elif i > n - fade: v *= (n - i) / fade

                    buf.append(struct.pack('<h', int(max(-0.85, min(0.85, v)) * 32767)))

                f.write(b''.join(buf))

        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav),
             "-af", "volume=2.0,highpass=f=40,lowpass=f=8000",
             "-c:a", "mp3", "-b:a", "128k", str(mp3)],
            capture_output=True, text=True, timeout=180
        )
        if r.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
            kb = mp3.stat().st_size // 1024
            tg(f"Muzik hazir! ({label}, {bpm}bpm, {kb}KB)", "✅")
            return str(mp3)

    except Exception as e:
        tg(f"Muzik hatasi: {str(e)[:60]}", "⚠")
    return ""

def gorsel_indir(i,prompt,toplam,konu=""):
    yol=WORK/f"img_{i+1:02d}.jpg"
    kisa = prompt[:80].replace('"','').replace("'",'')
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
        tg("Muzik yok","⚠"); return anlati
    try:
        pb=subprocess.run(["ffprobe","-v","quiet","-print_format","json",
            "-show_format",muzik],capture_output=True,text=True)
        ms=float(json.loads(pb.stdout)["format"]["duration"])
        if ms<3: tg("Muzik cok kisa","⚠"); return anlati
        tg(f"Muzik {ms:.0f}sn, karistiriliyor...","🎚")
    except Exception as e:
        tg(f"Muzik probe hatasi: {e}","⚠"); return anlati

    miksl=WORK/"miksl.mp3"
    cmd=["ffmpeg","-y",
         "-i",anlati,
         "-stream_loop","-1","-i",muzik,
         "-filter_complex",
         "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a1];"
         "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.4[a2];"
         "[a1][a2]amix=inputs=2:duration=first:weights=1 0.6[aout]",
         "-map","[aout]",
         "-c:a","libmp3lame","-b:a","192k",
         "-t",str(int(sure)+2),
         str(miksl)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode==0 and miksl.exists() and miksl.stat().st_size>50000:
        tg(f"Muzik eklendi! ({miksl.stat().st_size//1024}KB)","✅")
        return str(miksl)
    tg("Miksaj hatasi, muzik olmadan devam","⚠")
    return anlati