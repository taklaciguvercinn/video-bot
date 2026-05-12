#!/usr/bin/env python3
"""Video Bot Turkish v12"""

import sys,os,json,time,requests,subprocess,re,struct,math,hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
TELEGRAM_BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID      = os.environ["TELEGRAM_CHAT_ID"]

WORK = Path("./output")
WORK.mkdir(exist_ok=True)

GEMINI_MODELS = [
    ("gemini-2.5-flash","v1beta"),
    ("gemini-2.0-flash","v1"),
    ("gemini-2.0-flash-lite","v1"),
]

def tg(m, e=""):
    t = f"{e} {m}".strip()
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":t,"parse_mode":"HTML"},timeout=10)
    except: pass
    print(t)

def tg_foto(d, c):
    try:
        with open(d,"rb") as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id":TELEGRAM_CHAT_ID,"caption":c,"parse_mode":"HTML"},
                files={"photo":f},timeout=30)
    except: pass

def komut_isle(cmd):
    p = [x.strip() for x in cmd.strip().split(",")]
    if len(p) != 6:
        raise ValueError("Format: Konu,Muzik,Dakika,Resim,GG.AA.YYYY,SS:DD")
    konu, muzik_hint, sure, resim, tarih, saat = p
    y = datetime.strptime(f"{tarih} {saat}","%d.%m.%Y %H:%M")
    return {
        "konu": konu,
        "muzik_hint": muzik_hint.strip().lower(),
        "sure": int(sure),
        "resim": int(resim),
        "yayin_iso": y.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    }

def gemini(prompt, max_tokens=8192):
    for model,api in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/{api}/models/{model}:generateContent"
        headers = {"Content-Type":"application/json","x-goog-api-key":GEMINI_API_KEY}
        body = {"contents":[{"parts":[{"text":prompt}]}],
                "generationConfig":{"temperature":0.7,"maxOutputTokens":max_tokens}}
        for attempt in range(3):
            try:
                r = requests.post(url,headers=headers,json=body,timeout=120)
                if r.status_code == 200:
                    c = r.json().get("candidates",[])
                    if c:
                        t = c[0].get("content",{}).get("parts",[{}])[0].get("text","").strip()
                        if t: return t,model
                    time.sleep(8)
                elif r.status_code == 429:
                    wait = 30 + attempt * 20
                    tg(f"{model} rate limit, {wait}sn bekleniyor...","⏳")
                    time.sleep(wait)
                elif r.status_code == 503:
                    time.sleep(15); break
                else:
                    tg(f"{model}: {r.json().get('error',{}).get('message','')[:50]}","⚠"); break
            except requests.Timeout:
                time.sleep(15)
    raise Exception("Gemini yanit vermedi")

def json_cikart(ham):
    ham = re.sub(r"```json\s*|```\s*","",ham).strip()
    try: return json.loads(ham)
    except: pass
    s=ham.find("{"); e=ham.rfind("}")+1
    if s!=-1 and e>s:
        seg=ham[s:e]
        try: return json.loads(seg)
        except: pass
    veri={}
    for a,pat in [("baslik",r'"baslik"\s*:\s*"([^"]{1,120})"'),
                  ("aciklama",r'"aciklama"\s*:\s*"([^"]{1,800})"'),
                  ("thumbnail_metin",r'"thumbnail_metin"\s*:\s*"([^"]{1,50})"')]:
        m=re.search(pat,ham)
        if m: veri[a]=m.group(1)
    tm=re.search(r'"etiketler"\s*:\s*\[(.*?)\]',ham,re.DOTALL)
    if tm: veri["etiketler"]=re.findall(r'"([^"]+)"',tm.group(1))
    if "baslik" in veri: return veri
    raise Exception(f"JSON: {ham[:60]}")

def telaffuz(metin):
    for ing,tr in [(r'\bAI\b','Ay-Ay'),(r'\bYouTube\b','Yutub'),
                   (r'\bGoogle\b','Gugil'),(r'\bNASA\b','Nasa'),
                   (r'\bUSA\b','ABD'),(r'\bOK\b','tamam')]:
        metin=re.sub(ing,tr,metin,flags=re.IGNORECASE)
    return re.sub(r' +',' ',metin).strip()

# ─── İÇERİK ──────────────────────────────────────────────────────────────────
def senaryo_uret(konu, sure, resim_sayisi):
    tg(f"'{konu}' icin icerik uretiliyor...","📚")
    kelime = sure * 170

    tg(f"{resim_sayisi} gorsel promptu uretiliyor...","🎨")
    gorseller = []
    try:
        p_img = f"""Sen bir görsel sanatçısın. {konu} hakkında bir belgesel için tam olarak {resim_sayisi} adet benzersiz görsel promptu üret.

KURALLAR:
- Her prompt {konu} ile doğrudan ilgili olmalı - spesifik sahneler, mekanlar, nesneler, olaylar
- Görsellerde KESİNLİKLE insan, yüz, yazı olmasın
- Sinematik, dramatik, yüksek kalite fotoğraf tarzı
- Her prompt İNGİLİZCE olsun (görsel üretici İngilizce anlar)
- Her prompt yeni satırda, 1'den {resim_sayisi}'e kadar numaralı
- Her prompt 100 karakterden kısa olsun
- Çeşitli sahneler: geniş çekim, yakın plan, havadan görünüm, atmosferik çekim

Şimdi {resim_sayisi} prompt üret:"""
        raw, _ = gemini(p_img, max_tokens=2048)
        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        for line in lines:
            line = re.sub(r'^\d+[\.\)]\s*','',line).strip()
            if len(line) > 10:
                line += ", no people, no humans, cinematic dramatic lighting 8k"
                gorseller.append(line)
            if len(gorseller) >= resim_sayisi:
                break
        tg(f"{len(gorseller)} gorsel promptu hazir","✅")
    except Exception as e:
        tg(f"Gorsel prompt hatasi: {e}","⚠")

    while len(gorseller) < resim_sayisi:
        i = len(gorseller)
        gorseller.append(f"{konu} cinematic dramatic scene {i+1}, no people, 8k atmospheric lighting")

    meta = {
        "baslik": f"{konu}: Tarihin Gizli Sirri!",
        "aciklama": f"{konu} hakkinda kapsamli Turkce belgesel. #belgesel #tarih #{konu.replace(' ','')}",
        "etiketler": [konu,"belgesel","tarih","youtube","turkce","egitim","gizem","kesfet"],
        "gorseller": gorseller[:resim_sayisi],
        "thumbnail_metin": konu.upper()[:15],
        "thumbnail_prompt": f"{konu} epic dramatic historical cinematic no text no people",
        "renk": "#1a1a2e"
    }

    tg("SEO optimize ediliyor...","📋")
    try:
        h,model = gemini(
            f"YouTube belgesel. Konu: {konu}. {sure} dk. Apostrof yok. "
            f"JSON: {{\"baslik\":\"etkileyici 55 karakter emoji\",\"aciklama\":\"400 karakter hashtag\","
            f"\"etiketler\":[\"e1\",\"e2\",\"e3\",\"e4\",\"e5\",\"e6\",\"e7\",\"e8\"],\"thumbnail_metin\":\"3 KELIME\"}}",
            max_tokens=512)
        mini = json_cikart(h)
        for k2 in ["baslik","aciklama","etiketler","thumbnail_metin"]:
            if mini.get(k2): meta[k2] = mini[k2]
        tg(f"SEO hazir: <b>{meta['baslik']}</b>","✅")
    except: tg("SEO varsayilan","⚠")

    tg(f"Senaryo yaziliyor ({kelime} kelime)...","📝")
    p2 = f"""Sen profesyonel bir belgesel anlatıcısısın. {konu} hakkında {sure} dakikalık bir belgesel için metin yazacaksın.

KESİN KURALLAR:
- MUTLAKA {kelime} kelime veya daha fazla yaz. Kelime sayısını dikkatli say.
- SADECE anlatım metni yaz - düz akan paragraflar
- Hiçbir sahne yönergesi, [köşeli parantez], (parantez), müzik notu yazma
- "Anlatıcı:" yazma, başlık yazma, madde işareti yazma, numara yazma
- {kelime} kelimeye ulaşana kadar yazmayı bırakma - erken durma
- {konu} konusunun tüm tarihini, arka planını, önemli olaylarını, önemini ve mirasını ele al
- Apostrof kullanma, emoji kullanma
- Üslup: ulusal coğrafya belgeseli gibi sürükleyici, dramatik, bilgilendirici

Şimdi başla ve {kelime}+ kelime yaz:"""

    senaryo = ""
    for attempt in range(4):
        try:
            h,model = gemini(p2, max_tokens=8192)
            h = re.sub(r'\[.*?\]','',h,flags=re.DOTALL)
            h = re.sub(r'\(.*?\)','',h,flags=re.DOTALL)
            h = re.sub(r'Anlat[ıi]c[ıi]\s*:','',h,flags=re.IGNORECASE)
            h = re.sub(r'^\*+\s*|^#+\s.*$','',h,flags=re.MULTILINE)
            h = re.sub(r'\n{3,}','\n\n',h).strip()
            wc = len(h.split())
            tg(f"Deneme {attempt+1}: {wc} kelime","📝")
            if wc > 300:
                senaryo = h
                tg(f"Senaryo hazir ({model}): <b>{wc} kelime</b>","✅")
                break
            time.sleep(5)
        except Exception as e:
            tg(f"Senaryo hatasi: {str(e)[:50]}","⚠"); time.sleep(10)

    if not senaryo:
        senaryo = f"{konu} tarihin en onemli konularindan biridir."

    meta["senaryo"] = telaffuz(senaryo)
    tg(f"Toplam: <b>{len(senaryo.split())} kelime</b>","📊")
    return meta

# ─── MÜZİK ───────────────────────────────────────────────────────────────────
def muzik_uret(konu, sure_sn, muzik_hint=""):
    tg("Muzik yukleniyor...","🎵")
    repo_root = Path(os.environ.get("GITHUB_WORKSPACE","."))
    all_mp3 = list(repo_root.glob("*.mp3"))
    if not all_mp3:
        tg("Repoda MP3 yok!","⚠"); return _synth_fallback(konu, sure_sn)

    def clean(s): return re.sub(r"[^a-z0-9]","",s.lower())
    chosen = None

    if muzik_hint:
        hc = clean(muzik_hint)
        for mp3 in all_mp3:
            if hc in clean(mp3.name): chosen = mp3; break
        if not chosen: tg(f"Hint '{muzik_hint}' bulunamadi, kategori kullaniliyor...","⚠")

    if not chosen:
        k = konu.lower()
        for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]: k=k.replace(c,r)
        cat = None
        if any(x in k for x in ["savas","viking","osmanli","roma","tarih","cin","mogol","napoleon","hitler","askeri"]): cat="war"
        elif any(x in k for x in ["misir","antik","yunan","sumer","babil","mezopotamya","gemi","kayip","gizemli"]): cat="mystery"
        elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot","gelecek"]): cat="space"
        elif any(x in k for x in ["doga","hayvan","deniz","orman","okyanus"]): cat="nature"
        elif any(x in k for x in ["gizem","korku","paranormal","komplo","karanlik"]): cat="mystery"
        if cat:
            matches = [m for m in all_mp3 if cat in m.name.lower()]
            if matches:
                seed = int(hashlib.md5(konu.encode()).hexdigest()[:8],16)
                chosen = matches[seed % len(matches)]

    if not chosen:
        seed = int(hashlib.md5(konu.encode()).hexdigest()[:8],16)
        chosen = all_mp3[seed % len(all_mp3)]
        tg(f"Rastgele muzik: {chosen.name}","⚠")

    tg(f"Muzik: <b>{chosen.name}</b> ({chosen.stat().st_size//1024}KB)","✅")
    return str(chosen)

def _synth_fallback(konu, sure_sn):
    wav=WORK/"muzik.wav"; mp3=WORK/"muzik.mp3"
    sr=44100; dur=int(min(sure_sn+30,7200)); n=sr*dur; fade=sr*3
    try:
        with open(wav,'wb') as f:
            dsize=n*2
            f.write(b'RIFF'); f.write(struct.pack('<I',36+dsize))
            f.write(b'WAVEfmt '); f.write(struct.pack('<I',16))
            f.write(struct.pack('<H',1)); f.write(struct.pack('<H',1))
            f.write(struct.pack('<I',sr)); f.write(struct.pack('<I',sr*2))
            f.write(struct.pack('<H',2)); f.write(struct.pack('<H',16))
            f.write(b'data'); f.write(struct.pack('<I',dsize))
            freqs=[130,164,196,261,87]; amps=[0.20,0.16,0.12,0.07,0.18]
            for start in range(0,n,sr):
                end=min(start+sr,n); buf=[]
                for i in range(start,end):
                    t=i/sr; v=sum(a*math.sin(2*math.pi*fr*t) for a,fr in zip(amps,freqs))
                    if i<fade: v*=i/fade
                    elif i>n-fade: v*=(n-i)/fade
                    buf.append(struct.pack('<h',int(max(-0.85,min(0.85,v))*32767)))
                f.write(b''.join(buf))
        r=subprocess.run(["ffmpeg","-y","-i",str(wav),"-af","volume=2.0",
            "-c:a","mp3","-b:a","128k",str(mp3)],capture_output=True,timeout=180)
        if r.returncode==0 and mp3.exists(): return str(mp3)
    except: pass
    return ""

# ─── GÖRSELLER ───────────────────────────────────────────────────────────────
def gorsel_indir(i, prompt, toplam, konu=""):
    yol = WORK/f"img_{i+1:02d}.jpg"
    for attempt, seed in enumerate([i*7+42, i*13+17, i*3+99, i*19+5, i*31+11]):
        enc = quote(prompt[:200])
        url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={seed}&nologo=true&model=flux&enhance=true"
        try:
            r = requests.get(url,timeout=120)
            if r.status_code==200 and len(r.content)>10000 and r.content[:2]==b'\xff\xd8':
                yol.write_bytes(r.content)
                tg(f"Gorsel {i+1}/{toplam} ✓","🖼")
                time.sleep(4)
                return str(yol)
            if r.status_code==429: time.sleep(45)
            else: time.sleep(10)
        except: time.sleep(10)
        if attempt == 1:
            prompt = f"{konu} cinematic dramatic landscape no people 8k"

    renkler=["0x3D1C02","0x4A0E0E","0x0A1628","0x2D1B69","0x003333","0x1A3A1A","0x330033","0x1A1A00"]
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
        f"color=c={renkler[i%len(renkler)]}:size=1920x1080:rate=1",
        "-vframes","1","-q:v","2",str(yol)],capture_output=True)
    tg(f"Gorsel {i+1} yedek","⚠")
    return str(yol)

def gorseller_uret(promptlar, konu=""):
    n = len(promptlar)
    tg(f"{n} gorsel uretiliyor...","🎨")
    return [gorsel_indir(i,p,n,konu) for i,p in enumerate(promptlar)]

# ─── THUMBNAIL ───────────────────────────────────────────────────────────────
def thumbnail_uret(prompt, metin, renk, konu):
    tg("Thumbnail uretiliyor...","🖼")
    enc=quote(f"{prompt}, youtube thumbnail dramatic vibrant no text no people")
    url=f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=777&nologo=true&model=flux"
    base=WORK/"thumb_base.jpg"; final=WORK/"thumbnail.jpg"
    for _ in range(3):
        try:
            r=requests.get(url,timeout=60)
            if r.status_code==200 and len(r.content)>5000 and r.content[:2]==b'\xff\xd8':
                base.write_bytes(r.content); break
            time.sleep(10)
        except: time.sleep(10)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
            f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1",
            "-vframes","1",str(base)],capture_output=True)
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
    tg("Thumbnail hazir!","✅")
    return str(final)

# ─── SES ─────────────────────────────────────────────────────────────────────
def ses_uret(senaryo):
    tg("Turkce seslendirme uretiliyor...","🎙")
    sf=WORK/"senaryo.txt"; rf=WORK/"ses_ham.mp3"
    sub_vtt=WORK/"altyazi.vtt"; sub_srt=WORK/"altyazi.srt"
    sf.write_text(senaryo,encoding="utf-8")

    for rate,pitch,vol in [("-8%","-10Hz","+15%"),("-5%","-5Hz","+10%"),("0%","0Hz","0%")]:
        r=subprocess.run(["edge-tts","--voice","tr-TR-EmelNeural",
            "--file",str(sf),"--write-media",str(rf),
            "--write-subtitles",str(sub_vtt),
            f"--rate={rate}",f"--pitch={pitch}",f"--volume={vol}"],
            capture_output=True,text=True,timeout=600)
        if r.returncode==0 and rf.exists() and rf.stat().st_size>1000:
            tg(f"Ses uretildi (rate={rate})","✅"); break
        time.sleep(3)
    else:
        r2=subprocess.run(["edge-tts","--voice","tr-TR-EmelNeural",
            "--file",str(sf),"--write-media",str(rf),
            "--write-subtitles",str(sub_vtt)],
            capture_output=True,text=True,timeout=600)
        if r2.returncode!=0 or not rf.exists():
            raise Exception(f"TTS: {r2.stderr[-80:]}")

    if sub_vtt.exists():
        vtt=sub_vtt.read_text(encoding="utf-8"); srt=[]; say=1
        for blok in re.split(r'\n\n+',vtt):
            if '-->' in blok:
                sat=blok.strip().split('\n')
                zaman=next((s for s in sat if '-->' in s),None)
                if zaman:
                    zaman=re.sub(r'(\d{2}:\d{2}:\d{2})\.(\d{3})',r'\1,\2',zaman).strip()
                    mt=[s for s in sat if '-->' not in s and s.strip()
                        and not s.startswith('NOTE') and not s.strip().isdigit()]
                    if mt: srt+=[str(say),zaman]+mt+['']; say+=1
        sub_srt.write_text('\n'.join(srt),encoding="utf-8")

    probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",str(rf)],
        capture_output=True,text=True)
    sure=float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b>","✅")
    return str(rf), sure, str(sub_srt) if sub_srt.exists() else ""

# ─── MÜZİK MİKS ──────────────────────────────────────────────────────────────
def ses_miksle(anlati, muzik, sure):
    if not muzik: tg("Muzik yolu yok","⚠"); return anlati
    mp = Path(muzik)
    if not mp.exists(): tg(f"Muzik bulunamadi: {muzik}","⚠"); return anlati
    tg(f"Muzik boyutu: {mp.stat().st_size//1024}KB","🎚")
    try:
        pb=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",str(mp)],
            capture_output=True,text=True)
        ms=float(json.loads(pb.stdout)["format"]["duration"])
        if ms<3: tg("Muzik cok kisa","⚠"); return anlati
        tg(f"Muzik {ms:.0f}sn, karistiriliyor...","🎚")
    except Exception as e:
        tg(f"ffprobe hatasi: {e}","⚠"); return anlati

    miksl=WORK/"miksl.mp3"
    cmd=["ffmpeg","-y","-i",anlati,"-stream_loop","-1","-i",str(mp),
         "-filter_complex",
         "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a1];"
         "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.20[a2];"
         "[a1][a2]amix=inputs=2:duration=first:weights=1 0.6[aout]",
         "-map","[aout]","-c:a","libmp3lame","-b:a","192k",
         "-t",str(int(sure)+2),str(miksl)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode==0 and miksl.exists() and miksl.stat().st_size>50000:
        tg(f"Muzik eklendi! ({miksl.stat().st_size//1024}KB)","✅")
        return str(miksl)
    tg(f"Miksaj hatasi: {r.stderr[-60:]}","⚠")
    return anlati

# ─── VİDEO ───────────────────────────────────────────────────────────────────
def video_uret(gorseller, ses, altyazi_srt, toplam_sure):
    tg(f"Video uretiliyor...\n{len(gorseller)} gorsel | fade + parlama efekti\n⏳ ~{len(gorseller)//2+5} dk","🎬")

    gorsel_sure = toplam_sure / len(gorseller)
    fps         = 30
    fade_sure   = 0.6
    gecisler    = ["fade","dissolve","brightness","fade","dissolve"]
    p_renkler   = ["white","0x4444ff","0xff2222"]

    def make_vf(idx, dur, parlama, p_renk):
        half = max(int(dur * fps) // 2, 1)
        zoom = (
            f"scale=8000:-1,"
            f"crop="
            f"w='iw/(1.0+0.15*if(lte(n,{half}),n/{half},(2*{half}-n)/{half}))':"
            f"h='ih/(1.0+0.15*if(lte(n,{half}),n/{half},(2*{half}-n)/{half}))':"
            f"x='(iw-iw/(1.0+0.15*if(lte(n,{half}),n/{half},(2*{half}-n)/{half})))/2':"
            f"y='(ih-ih/(1.0+0.15*if(lte(n,{half}),n/{half},(2*{half}-n)/{half})))/2',"
            f"scale=1920:1080,vignette=PI/4"
        )
        # Her klipte mutlaka fade in + fade out
        fi = f"fade=t=in:st=0:d={fade_sure}"
        fo = f"fade=t=out:st={dur-fade_sure:.2f}:d={fade_sure}"
        if parlama:
            # Parlama kliplerinde renkli fade
            fi = f"fade=t=in:st=0:d=0.5:color={p_renk}"
            fo = f"fade=t=out:st={dur-0.5:.2f}:d=0.5:color={p_renk}"
        else:
            tip = gecisler[idx % len(gecisler)]
            if tip == "dissolve": fi+=":alpha=1"; fo+=":alpha=1"
            elif tip == "brightness": fi+=":color=black"; fo+=":color=black"
        return f"{zoom},{fi},{fo},format=yuv420p"

    klipler = []
    for idx, gorsel in enumerate(gorseller):
        klip    = WORK/f"clip_{idx:02d}.mp4"
        parlama = (idx % 4 == 3)
        p_renk  = p_renkler[(idx // 4) % len(p_renkler)]
        vf      = make_vf(idx, gorsel_sure, parlama, p_renk)

        r = subprocess.run(
            ["ffmpeg","-y","-loop","1","-i",gorsel,
             "-vf",vf,"-t",str(gorsel_sure),
             "-c:v","libx264","-preset","fast","-crf","20",
             "-r",str(fps),str(klip)],
            capture_output=True,text=True,timeout=300)
        if r.returncode==0 and klip.exists():
            klipler.append(str(klip))
            icon = ("⚡🔵" if p_renk=="0x4444ff" else "⚡🔴" if p_renk=="0xff2222" else "⚡⚪") if parlama else "✓"
            tg(f"Klip {idx+1}/{len(gorseller)} {icon}","🎞")
        else:
            tg(f"Klip {idx+1} hatasi: {r.stderr[-80:]}","⚠")

    if not klipler: raise Exception("Hic klip olusturulamadi")

    concat_list = WORK/"concat.txt"
    concat_list.write_text('\n'.join(f"file '{Path(c).resolve()}'" for c in klipler))
    ham_video = WORK/"video_ham.mp4"
    r = subprocess.run(["ffmpeg","-y","-f","concat","-safe","0",
        "-i",str(concat_list.resolve()),"-c:v","copy",str(ham_video)],
        capture_output=True,text=True,timeout=3600)
    if r.returncode!=0 or not ham_video.exists():
        raise Exception(f"Concat hatasi: {r.stderr[-100:]}")

    final_video = WORK/"final_video.mp4"
    if altyazi_srt and os.path.exists(altyazi_srt):
        srt_esc = str(altyazi_srt).replace('\\','/').replace(':','\\:')
        vf_sub  = (f"subtitles={srt_esc}:force_style='"
                   f"FontSize=14,PrimaryColour=&H00FFFF00,"
                   f"OutlineColour=&H00000000,Outline=2,BorderStyle=1,"
                   f"Alignment=2,MarginV=30'")
        r = subprocess.run(["ffmpeg","-y","-i",str(ham_video),"-i",ses,
            "-vf",vf_sub,"-c:v","libx264","-preset","fast","-crf","20",
            "-c:a","aac","-b:a","192k","-shortest",str(final_video)],
            capture_output=True,text=True,timeout=7200)
    else:
        r = subprocess.run(["ffmpeg","-y","-i",str(ham_video),"-i",ses,
            "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",str(final_video)],
            capture_output=True,text=True,timeout=7200)

    if r.returncode!=0 or not final_video.exists():
        raise Exception(f"Final video hatasi: {r.stderr[-100:]}")

    tg(f"Video hazir! {final_video.stat().st_size//(1024*1024)}MB","✅")
    return str(final_video)

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────
def erisim_tokeni_al():
    r=requests.post("https://oauth2.googleapis.com/token",data={
        "client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,
        "refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},timeout=30)
    return r.json()["access_token"]

def youtube_yukle(video_yolu, meta, yayin_iso):
    tg("YouTube'a yukleniyor...","📤")
    token = erisim_tokeni_al()
    body = {"snippet":{"title":meta["baslik"][:100],"description":meta["aciklama"][:5000],
                       "tags":meta["etiketler"][:500],"categoryId":"27",
                       "defaultLanguage":"tr","defaultAudioLanguage":"tr"},
            "status":{"privacyStatus":"private","publishAt":yayin_iso,"selfDeclaredMadeForKids":False}}
    r=requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json",
                 "X-Upload-Content-Type":"video/mp4"},json=body,timeout=30)
    upload_url = r.headers.get("Location","")
    if not upload_url: raise Exception(f"Upload URL yok: {r.text[:100]}")
    with open(video_yolu,"rb") as f: video_data=f.read()
    r2=requests.put(upload_url,headers={"Content-Type":"video/mp4"},data=video_data,timeout=1800)
    if r2.status_code not in [200,201]: raise Exception(f"Yukleme hatasi: {r2.text[:100]}")
    vid_id=r2.json().get("id","")
    tg(f"Yuklendi! youtube.com/watch?v={vid_id}\nYayin: {yayin_iso}","🎉")
    return vid_id

def thumbnail_yukle(vid_id, thumb_yolu):
    try:
        token=erisim_tokeni_al()
        with open(thumb_yolu,"rb") as f: data=f.read()
        r=requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
            headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},
            data=data,timeout=60)
        if r.status_code==200: tg("Thumbnail yuklendi!","🖼")
    except Exception as e: tg(f"Thumbnail hatasi: {e}","⚠")

# ─── ANA ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv)<2: tg("Komut alinamadi","⚠"); sys.exit(1)
    cmd=" ".join(sys.argv[1:])
    tg(f"Komut: <b>{cmd}</b>","🚀")
    try: params=komut_isle(cmd)
    except Exception as e: tg(f"Komut hatasi: {e}","❌"); sys.exit(1)

    konu=params["konu"]; muzik_hint=params["muzik_hint"]
    sure=params["sure"]; resim=params["resim"]
    yayin_iso=params["yayin_iso"]

    tg(f"<b>{konu}</b> | {sure} dk | {resim} gorsel\n🎵 {muzik_hint}\n📅 {yayin_iso}","📋")
    try:
        meta        = senaryo_uret(konu, sure, resim)
        muzik       = muzik_uret(konu, sure*60, muzik_hint)
        gorseller   = gorseller_uret(meta["gorseller"], konu)
        thumbnail_uret(meta["thumbnail_prompt"],meta["thumbnail_metin"],meta["renk"],konu)
        ses,ses_sure,altyazi = ses_uret(meta["senaryo"])
        final_ses   = ses_miksle(ses, muzik, ses_sure)
        video       = video_uret(gorseller, final_ses, altyazi, ses_sure)
        vid_id      = youtube_yukle(video, meta, yayin_iso)
        thumbnail_yukle(vid_id, str(WORK/"thumbnail.jpg"))
        tg(f"✅ TAMAMLANDI!\nyoutube.com/watch?v={vid_id}","🎬")
    except Exception as e:
        tg(f"Kritik hata: {str(e)[:200]}","❌"); sys.exit(1)

if __name__=="__main__":
    main()