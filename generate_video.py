#!/usr/bin/env python3
"""Video Bot v9 - Kusursuz sistem"""

import sys, os, json, time, requests, subprocess, re, struct, math
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── ENV ─────────────────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
TELEGRAM_BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID      = os.environ["TELEGRAM_CHAT_ID"]
PEXELS_API_KEY        = os.environ.get("PEXELS_API_KEY", "")

WORK = Path("./output")
WORK.mkdir(exist_ok=True)

GEMINI_MODELS = [
    ("gemini-2.5-flash", "v1beta"),
    ("gemini-2.0-flash", "v1"),
    ("gemini-2.0-flash-lite", "v1"),
]

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
def tg(mesaj, emoji=""):
    text = f"{emoji} {mesaj}".strip()
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10)
    except: pass
    print(text)

def tg_foto(dosya, aciklama):
    try:
        with open(dosya, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": aciklama, "parse_mode": "HTML"},
                files={"photo": f}, timeout=30)
    except: pass

# ─── KOMUT ───────────────────────────────────────────────────────────────────
def komut_isle(cmd):
    p = [x.strip() for x in cmd.strip().split(",")]
    if len(p) == 5:
        # Eski format: Konu,Dakika,Resim,GG.AA.YYYY,SS:DD
        konu, sure, resim, tarih, saat = p
        video_sayisi = 0
    elif len(p) == 6:
        # Yeni format: Konu,Dakika,Resim,VideoSayisi,GG.AA.YYYY,SS:DD
        konu, sure, resim, video_sayisi, tarih, saat = p
        video_sayisi = int(video_sayisi)
    else:
        raise ValueError("Format: Konu,Dakika,Resim,VideoSayisi,GG.AA.YYYY,SS:DD")
    yayin = datetime.strptime(f"{tarih} {saat}", "%d.%m.%Y %H:%M")
    return {
        "konu": konu, "sure": int(sure), "resim": int(resim),
        "video_sayisi": video_sayisi,
        "yayin_dt": yayin, "yayin_iso": yayin.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    }

# ─── GEMİNİ ──────────────────────────────────────────────────────────────────
def gemini(prompt, max_tokens=8192):
    for model, api_ver in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens}}
        for _ in range(3):
            try:
                r = requests.post(url, headers=headers, json=body, timeout=120)
                if r.status_code == 200:
                    cands = r.json().get("candidates", [])
                    if cands:
                        t = cands[0].get("content",{}).get("parts",[{}])[0].get("text","").strip()
                        if t: return t, model
                    time.sleep(10)
                elif r.status_code == 429:
                    time.sleep(20)
                elif r.status_code == 503:
                    break
                else:
                    err = r.json().get("error",{}).get("message","")[:60]
                    tg(f"{model} hata: {err}", "⚠"); break
            except requests.Timeout:
                time.sleep(10)
    raise Exception("Hicbir Gemini modeli yanit vermedi")

def json_cikart(ham):
    ham = re.sub(r"```json\s*|```\s*", "", ham).strip()
    try: return json.loads(ham)
    except: pass
    s = ham.find("{"); e = ham.rfind("}") + 1
    if s != -1 and e > s:
        seg = ham[s:e]
        try: return json.loads(seg)
        except: pass
        try:
            temiz = re.sub(r"(?<=[^\s{,:\[])'(?=[^\s},:!'\]])", "", seg)
            return json.loads(temiz)
        except: pass
    veri = {}
    for alan, pat in [
        ("baslik", r'"baslik"\s*:\s*"([^"]{1,120})"'),
        ("aciklama", r'"aciklama"\s*:\s*"([^"]{1,1000})"'),
        ("thumbnail_metin", r'"thumbnail_metin"\s*:\s*"([^"]{1,60})"'),
        ("thumbnail_prompt", r'"thumbnail_prompt"\s*:\s*"([^"]{1,400})"'),
        ("renk", r'"renk"\s*:\s*"(#[0-9a-fA-F]{6})"'),
    ]:
        m = re.search(pat, ham)
        if m: veri[alan] = m.group(1)
    tm = re.search(r'"etiketler"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
    if tm: veri["etiketler"] = re.findall(r'"([^"]+)"', tm.group(1))
    im = re.search(r'"gorseller"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
    if im: veri["gorseller"] = re.findall(r'"([^"]+)"', im.group(1))
    vm = re.search(r'"video_aramalar"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
    if vm: veri["video_aramalar"] = re.findall(r'"([^"]+)"', vm.group(1))
    if "baslik" in veri: return veri
    raise Exception(f"JSON parse basarisiz: {ham[:80]}")

# ─── TELAFFUZ DÜZELTİCİ ──────────────────────────────────────────────────────
def telaffuz_duzenle(metin):
    """İngilizce kelimeleri Türkçe okunuşa çevir, edge-tts için hazırla"""
    sozluk = {
        r'\bAI\b': 'Ay-Ay', r'\bYouTube\b': 'Yutub', r'\bGoogle\b': 'Gugıl',
        r'\bNASA\b': 'Nasa', r'\bUSA\b': 'ABD', r'\bUK\b': 'İngiltere',
        r'\bCIA\b': 'Si-Ay-Ey', r'\bFBI\b': 'Ef-Bi-Ay',
        r'\bDNA\b': 'De-En-Ey', r'\bRNA\b': 'Ar-En-Ey',
        r'\bBC\b': 'Bi-Si', r'\bCNN\b': 'Si-En-En',
        r'\bOK\b': 'Tamam', r'\bvs\b': 'karşısında',
    }
    for ing, tr in sozluk.items():
        metin = re.sub(ing, tr, metin, flags=re.IGNORECASE)
    # Noktalama sonrası boşluk ekle (doğal duraklamalar)
    metin = re.sub(r'([.!?])\s*', r'\1 ', metin)
    # Çift boşlukları temizle
    metin = re.sub(r' +', ' ', metin)
    return metin.strip()

# ─── SENARYO (BÖLÜMLER HALİNDE) ──────────────────────────────────────────────
def senaryo_uret(konu, sure, resim_sayisi, video_sayisi):
    tg(f"'{konu}' icin icerik uretiliyor...", "📚")
    kelime_hedef = sure * 160

    # ADIM 1: Meta
    tg("Meta ve promptlar uretiliyor...", "📋")
    gorsel_prompt_listesi = ",".join([f'"tarihi sinematik prompt {i+1} ultra detailed 8k dramatic lighting"' for i in range(min(resim_sayisi, 5))])
    video_arama_listesi = ",".join([f'"historical {konu.lower()} scene {i+1}"' for i in range(min(video_sayisi, 5))])

    prompt1 = f"""YouTube belgesel. Konu: {konu}. Sure: {sure} dk.
Apostrof yok. Emoji sadece baslikta.
JSON:
{{"baslik":"baslik 55 karakter emoji","aciklama":"aciklama 400 karakter hashtag","etiketler":["e1","e2","e3","e4","e5","e6","e7","e8"],"gorseller":[{gorsel_prompt_listesi}],"video_aramalar":[{video_arama_listesi}],"thumbnail_metin":"MAX 3 KELIME","thumbnail_prompt":"epic dramatic no text cinematic","renk":"#1a1a2e"}}"""

    meta = None
    for _ in range(4):
        try:
            ham, model = gemini(prompt1, max_tokens=2048)
            meta = json_cikart(ham)
            if "baslik" in meta:
                # Gorsel promptlari tamamla
                while len(meta.get("gorseller", [])) < resim_sayisi:
                    meta.setdefault("gorseller", [])
                    meta["gorseller"].append(f"{konu} dramatic historical cinematic {len(meta['gorseller'])+1} 8k")
                tg(f"Meta hazir ({model}): <b>{meta['baslik']}</b>", "✅")
                break
        except Exception as e:
            tg(f"Meta hatasi: {str(e)[:60]}", "⚠"); time.sleep(10)

    if not meta:
        meta = {
            "baslik": f"{konu} Belgeseli", "aciklama": f"{konu} belgeseli. #belgesel",
            "etiketler": [konu, "belgesel", "tarih"],
            "gorseller": [f"{konu} dramatic historical cinematic scene {i+1} 8k" for i in range(resim_sayisi)],
            "video_aramalar": [f"{konu} historical" for _ in range(video_sayisi)],
            "thumbnail_metin": konu.upper()[:15],
            "thumbnail_prompt": f"{konu} epic dramatic", "renk": "#1a1a2e"
        }

    # ADIM 2: Tum senaryoyu tek seferde yaz
    tg(f"Senaryo yaziliyor ({kelime_hedef} kelime)...", "📝")

    prompt2 = f"""Turkce YouTube belgesel senaryosu. Konu: {konu}. Sure: {sure} dakika.
Tam {kelime_hedef} kelime Turkce duz metin yaz.
Kural: Apostrof yok, emoji yok, gorsel notu yok, baslik yok, sadece duz anlatim.
Uzun ve detayli yaz, {sure} dakikayi dolduracak kadar."""

    senaryo = ""
    for _ in range(5):
        try:
            ham, model = gemini(prompt2, max_tokens=8192)
            ham = re.sub(r'\[.*?\]|\*+|^#+\s.*$', '', ham, flags=re.DOTALL|re.MULTILINE)
            ham = re.sub(r'\n{3,}', '\n\n', ham).strip()
            kelime = len(ham.split())
            if kelime > 200:
                senaryo = ham
                tg(f"Senaryo hazir ({model}): <b>{kelime} kelime</b>", "✅")
                break
            time.sleep(5)
        except Exception as e:
            tg(f"Senaryo hatasi: {str(e)[:60]}", "⚠")
            time.sleep(15)

    if not senaryo:
        senaryo = f"{konu} tarihin en onemli konularindan biridir. Bu belgeselde bu konuyu ele alacagiz."
        tg("Senaryo yedek metin", "⚠")

    senaryo = telaffuz_duzenle(senaryo)
    meta["senaryo"] = senaryo
    tg(f"Toplam: <b>{len(senaryo.split())} kelime</b>", "📊")
    return meta

# ─── MÜZİK (PYTHON WAV) ──────────────────────────────────────────────────────
def muzik_uret(konu, sure_sn):
    tg("Muzik uretiliyor...", "🎵")
    wav = WORK/"muzik.wav"; mp3 = WORK/"muzik.mp3"
    k = konu.lower()
    for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]: k=k.replace(c,r)

    if any(x in k for x in ["viking","savas","osmanli","roma","selcuklu","tarih"]):
        freqs=[55,82,110,165]; label="epic"
    elif any(x in k for x in ["misir","antik","yunan","sumer","babil","mezopotamya"]):
        freqs=[174,261,348,130]; label="ancient"
    elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot","gelecek"]):
        freqs=[220,330,440,110]; label="space"
    elif any(x in k for x in ["doga","hayvan","deniz","orman","okyanus"]):
        freqs=[196,261,329,392]; label="nature"
    elif any(x in k for x in ["gizem","korku","paranormal","komplo"]):
        freqs=[73,110,155,207]; label="mystery"
    else:
        freqs=[130,164,196,261]; label="cinematic"

    sr = 44100
    dur = int(min(sure_sn+30, 3600))
    n = sr*dur
    fade = sr*5
    amps = [0.25,0.18,0.12,0.08]

    try:
        with open(wav,'wb') as f:
            dsize = n*2
            f.write(b'RIFF'); f.write(struct.pack('<I',36+dsize))
            f.write(b'WAVE'); f.write(b'fmt ')
            f.write(struct.pack('<I',16)); f.write(struct.pack('<H',1))
            f.write(struct.pack('<H',1)); f.write(struct.pack('<I',sr))
            f.write(struct.pack('<I',sr*2)); f.write(struct.pack('<H',2))
            f.write(struct.pack('<H',16)); f.write(b'data')
            f.write(struct.pack('<I',dsize))
            chunk=sr
            for start in range(0,n,chunk):
                end=min(start+chunk,n)
                buf=[]
                for i in range(start,end):
                    t=i/sr
                    v=sum(a*math.sin(2*math.pi*fr*t) for a,fr in zip(amps,freqs))
                    v*=(1+0.02*math.sin(2*math.pi*0.3*t))
                    if i<fade: v*=i/fade
                    elif i>n-fade: v*=(n-i)/fade
                    v=max(-0.85,min(0.85,v))
                    buf.append(struct.pack('<h',int(v*32767)))
                f.write(b''.join(buf))

        r=subprocess.run(["ffmpeg","-y","-i",str(wav),
            "-af","aecho=0.5:0.6:60:0.15,volume=0.55",
            "-c:a","mp3","-b:a","128k",str(mp3)],
            capture_output=True,text=True,timeout=120)
        if r.returncode==0 and mp3.exists() and mp3.stat().st_size>1000:
            tg(f"Muzik hazir! ({label}, {dur//60}dk)", "✅")
            return str(mp3)
    except Exception as e:
        tg(f"Muzik hatasi: {str(e)[:60]}", "⚠")
    return ""

# ─── PEXELS VİDEO ────────────────────────────────────────────────────────────
def pexels_video_indir(arama, sure_min, sure_max, index):
    """Pexels'tan telif ödenmez video klip indir"""
    if not PEXELS_API_KEY:
        return None
    yol = WORK / f"pexels_{index:02d}.mp4"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": arama, "per_page": 10, "min_duration": sure_min, "max_duration": sure_max}
    try:
        r = requests.get("https://api.pexels.com/videos/search",
            headers=headers, params=params, timeout=15)
        if r.status_code != 200: return None
        videos = r.json().get("videos", [])
        if not videos: return None
        # HD veya Full HD video sec
        video = videos[index % len(videos)]
        best_file = None
        for vf in video.get("video_files", []):
            if vf.get("quality") in ["hd","full_hd"] and vf.get("width", 0) >= 1280:
                best_file = vf
                break
        if not best_file and video.get("video_files"):
            best_file = video["video_files"][0]
        if not best_file: return None

        dl = requests.get(best_file["link"], timeout=60, stream=True)
        if dl.status_code == 200:
            with open(yol, 'wb') as f:
                for chunk in dl.iter_content(65536):
                    f.write(chunk)
            if yol.stat().st_size > 100000:
                tg(f"Video klip {index+1} indirildi (Pexels)", "🎬")
                return str(yol)
    except Exception as e:
        tg(f"Pexels hata: {str(e)[:40]}", "⚠")
    return None

def videolar_indir(aramalar):
    """Tum video klipleri indir"""
    if not PEXELS_API_KEY or not aramalar:
        return []
    tg(f"{len(aramalar)} video klip indiriliyor (Pexels)...", "🎬")
    sonuclar = []
    for i, arama in enumerate(aramalar):
        yol = pexels_video_indir(arama, 5, 10, i)
        if yol: sonuclar.append(yol)
        else:
            # Alternatif arama
            yol2 = pexels_video_indir("cinematic historical", 5, 10, i)
            if yol2: sonuclar.append(yol2)
        time.sleep(1)
    tg(f"{len(sonuclar)}/{len(aramalar)} video klip indirildi", "✅")
    return sonuclar

# ─── GORSEL - 50/50 POLLINATIONS + PICSUM (KONUYA UYGUN) ────────────────────
# Picsum kategori ID'leri - konuya gore
PICSUM_KATEGORILER = {
    "savas":      [11, 26, 42, 76, 83, 110, 159, 177, 193, 240],
    "tarih":      [10, 22, 27, 30, 37, 45, 50, 64, 91, 130],
    "doga":       [12, 14, 18, 20, 24, 33, 35, 40, 57, 65],
    "sehir":      [13, 15, 17, 19, 29, 55, 59, 60, 70, 75],
    "deniz":      [16, 25, 28, 43, 53, 68, 77, 88, 99, 120],
    "uzay":       [11, 42, 83, 110, 159, 177, 193, 240, 250, 260],
    "karanlik":   [26, 42, 76, 83, 100, 110, 150, 200, 210, 220],
    "varsayilan": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
}

def picsum_kategori_sec(konu):
    """Konuya gore uygun Picsum kategori sec"""
    k = konu.lower()
    for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]:
        k = k.replace(c,r)
    if any(x in k for x in ["savas","viking","osmanli","roma","selcuklu","savasc"]): return PICSUM_KATEGORILER["savas"]
    if any(x in k for x in ["tarih","antik","misir","yunan","sumer","babil"]): return PICSUM_KATEGORILER["tarih"]
    if any(x in k for x in ["doga","orman","bitki","hayvan"]): return PICSUM_KATEGORILER["doga"]
    if any(x in k for x in ["sehir","teknoloji","yapay","robot","gelecek"]): return PICSUM_KATEGORILER["sehir"]
    if any(x in k for x in ["deniz","okyanus","su","balik"]): return PICSUM_KATEGORILER["deniz"]
    if any(x in k for x in ["uzay","gezegen","yildiz","evren"]): return PICSUM_KATEGORILER["uzay"]
    if any(x in k for x in ["gizem","korku","karanlik","paranormal"]): return PICSUM_KATEGORILER["karanlik"]
    return PICSUM_KATEGORILER["varsayilan"]

def gorsel_indir(i, prompt, toplam, konu=""):
    yol = WORK / f"img_{i+1:02d}.jpg"
    kisa = prompt[:100].replace('"','').replace("'",'')
    stil = "cyberpunk neon dramatic lighting" if i % 2 == 1 else "cinematic historical dramatic lighting"

    if i % 2 == 0:
        # Cift index: Pollinations (AI gorsel)
        enc = quote(f"{kisa} {stil} 4k ultra detailed")
        url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={i*7+42}&nologo=true&model=flux"
        try:
            r = requests.get(url, timeout=25)
            if r.status_code == 200 and len(r.content) > 10000 and r.content[:2] == b'\xff\xd8':
                yol.write_bytes(r.content)
                tg(f"Gorsel {i+1}/{toplam} ✓ (AI-Pollinations)", "🖼")
                return str(yol)
        except:
            pass
        tg(f"Gorsel {i+1} Pollinations basarisiz, Picsum'a gec", "⚠")
    # Tek index veya Pollinations basarisiz: Picsum (gercek fotograf)
    ids = picsum_kategori_sec(konu)
    pic_id = ids[i % len(ids)]
    try:
        url2 = f"https://picsum.photos/id/{pic_id}/1920/1080.jpg"
        r2 = requests.get(url2, timeout=20, allow_redirects=True)
        if r2.status_code == 200 and len(r2.content) > 5000:
            yol.write_bytes(r2.content)
            tg(f"Gorsel {i+1}/{toplam} ✓ (Picsum-konuya uygun)", "🖼")
            return str(yol)
    except:
        pass

    # Son yedek: renkli arka plan
    renkler = ["0x8B4513","0x4A0E0E","0x0A1628","0x2D1B69","0x003333","0x330033"]
    renk = renkler[i % len(renkler)]
    subprocess.run(["ffmpeg","-y","-f","lavfi",
        "-i",f"color=c={renk}:size=1920x1080:rate=1",
        "-vframes","1","-q:v","2",str(yol)], capture_output=True)
    tg(f"Gorsel {i+1} yedek renk", "⚠")
    return str(yol)

def gorseller_uret(promptlar, konu=""):
    n = len(promptlar)
    tg(f"{n} gorsel uretiliyor (50% AI + 50% gercek foto, konuya uygun)...", "🎨")
    return [gorsel_indir(i, p, n, konu) for i, p in enumerate(promptlar)]

# ─── THUMBNAIL ────────────────────────────────────────────────────────────────
def thumbnail_uret(prompt, metin, renk, konu):
    tg("Thumbnail uretiliyor...", "🖼")
    enc=quote(f"{prompt}, youtube thumbnail dramatic vibrant no text professional")
    url=f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=777&nologo=true&model=flux"
    base=WORK/"thumb_base.jpg"; final=WORK/"thumbnail.jpg"
    for _ in range(4):
        try:
            r=requests.get(url,timeout=60)
            if r.status_code==200 and len(r.content)>5000 and r.content[:2]==b'\xff\xd8':
                base.write_bytes(r.content); break
            time.sleep(10)
        except: time.sleep(10)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi",
            "-i",f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1",
            "-vframes","1",str(base)],capture_output=True)
    m=metin.upper()[:25].replace("'","").replace(":","\\:")
    k=konu.upper()[:20].replace("'","").replace(":","\\:")
    fs=80 if len(m)<=10 else 60 if len(m)<=18 else 44
    vf=(f"drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.42:color=black@0.72:t=fill,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=black@0.4:x=(w-text_w)/2+2:y=h*0.62+2:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=white:x=(w-text_w)/2:y=h*0.62:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{k}':fontsize=30:fontcolor=yellow:x=20:y=20:font=DejaVu Sans:style=Bold")
    r=subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",vf,"-q:v","2",str(final)],capture_output=True,text=True)
    if r.returncode!=0 or not final.exists(): subprocess.run(["cp",str(base),str(final)])
    if final.exists(): tg_foto(str(final),f"Thumbnail: {m}")
    tg("Thumbnail hazir!", "✅")
    return str(final)

# ─── SES + ALTYAZI ───────────────────────────────────────────────────────────
def ses_uret(senaryo):
    tg("Derin belgesel sesi sentezleniyor...", "🎙")
    sf=WORK/"senaryo.txt"; rf=WORK/"ses_ham.mp3"; ff=WORK/"ses.mp3"
    sub_vtt=WORK/"altyazi.vtt"; sub_srt=WORK/"altyazi.srt"
    sf.write_text(senaryo, encoding="utf-8")

    basarili=False
    for rate,pitch,vol in [("-8%","-10Hz","+15%"),("-5%","-5Hz","+10%"),("0%","0Hz","0%")]:
        r=subprocess.run([
            "edge-tts","--voice","tr-TR-AhmetNeural",
            "--file",str(sf),"--write-media",str(rf),
            "--write-subtitles",str(sub_vtt),
            f"--rate={rate}",f"--pitch={pitch}",f"--volume={vol}"
        ],capture_output=True,text=True,timeout=300)
        if r.returncode==0 and rf.exists() and rf.stat().st_size>1000:
            basarili=True
            tg(f"Ses uretildi (rate={rate})", "✅")
            break
        time.sleep(3)

    if not basarili:
        r2=subprocess.run(["edge-tts","--voice","tr-TR-AhmetNeural",
            "--file",str(sf),"--write-media",str(rf),
            "--write-subtitles",str(sub_vtt)],capture_output=True,text=True,timeout=300)
        if r2.returncode!=0 or not rf.exists():
            raise Exception(f"TTS basarisiz: {r2.stderr[-80:]}")

    # EQ
    subprocess.run(["ffmpeg","-y","-i",str(rf),"-af",
        "equalizer=f=80:width_type=o:width=2:g=5,"
        "equalizer=f=200:width_type=o:width=2:g=3,"
        "equalizer=f=3000:width_type=o:width=2:g=-3,"
        "equalizer=f=8000:width_type=o:width=2:g=-5,"
        "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,"
        "volume=1.3","-c:a","mp3","-b:a","192k",str(ff)],capture_output=True)
    kullan=str(ff) if ff.exists() else str(rf)

    # VTT → SRT donustur (satir numarasiz)
    if sub_vtt.exists():
        vtt_icerik = sub_vtt.read_text(encoding="utf-8")
        srt_satirlar = []
        sayac = 1
        for blok in re.split(r'\n\n+', vtt_icerik):
            if '-->' in blok:
                satirlar = blok.strip().split('\n')
                zaman_satiri = next((s for s in satirlar if '-->' in s), None)
                if zaman_satiri:
                    # Milisaniye nokta → virgul (SRT formatı)
                    zaman_satiri = re.sub(r'(\d{2}:\d{2}:\d{2})\.(\d{3})', r'\1,\2', zaman_satiri)
                    # Sadece zaman kısmını al
                    zaman_satiri = zaman_satiri.strip()
                    metin_satirlari = [s for s in satirlar
                                      if '-->' not in s and s.strip()
                                      and not s.startswith('NOTE')
                                      and not s.strip().isdigit()]
                    if metin_satirlari:
                        srt_satirlar.append(str(sayac))
                        srt_satirlar.append(zaman_satiri)
                        srt_satirlar.extend(metin_satirlari)
                        srt_satirlar.append('')
                        sayac += 1
        sub_srt.write_text('\n'.join(srt_satirlar), encoding="utf-8")

    probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",kullan],capture_output=True,text=True)
    sure=float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b>", "✅")
    return kullan, sure, str(sub_srt) if sub_srt.exists() else ""

# ─── SES MİKS ────────────────────────────────────────────────────────────────
def ses_miksle(anlati, muzik, sure):
    if not muzik or not os.path.exists(muzik):
        tg("Muzik yok, sadece anlatici", "⚠")
        return anlati
    try:
        p = subprocess.run(["ffprobe","-v","quiet","-print_format","json",
            "-show_format",muzik],capture_output=True,text=True)
        if float(json.loads(p.stdout)["format"]["duration"]) < 5:
            return anlati
    except:
        return anlati

    tg("Ses + Muzik karistiriliyor...", "🎚")
    miksl = WORK/"miksl.mp3"
    # En basit yontem: iki sesi farkli volume ile cak
    cmd = ["ffmpeg","-y",
           "-i", anlati,
           "-i", muzik,
           "-filter_complex",
           "[0:a]volume=1.0[v1];"
           "[1:a]volume=0.15,aloop=loop=-1:size=2e+09,atrim=0:"+str(int(sure)+5)+"[v2];"
           "[v1][v2]amix=inputs=2:duration=first[out]",
           "-map","[out]",
           "-c:a","mp3","-b:a","192k","-t",str(sure),
           str(miksl)]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=300)
    if r.returncode==0 and miksl.exists() and miksl.stat().st_size>10000:
        tg("Muzik eklendi!", "✅")
        return str(miksl)
    tg("Miks hatasi, sadece anlatici", "⚠")
    return anlati

# ─── VIDEO MONTAJ + ALTYAZI ───────────────────────────────────────────────────
def video_montaj(gorseller, video_klipleri, ses, altyazi_srt, toplam_sure):
    tg(f"Video montajlaniyor...\n{len(gorseller)} gorsel + {len(video_klipleri)} klip\n⏳ ~{len(gorseller)//2+8} dk","🎬")
    cikis=WORK/"video_raw.mp4"; cikis_son=WORK/"video.mp4"; liste=WORK/"liste.txt"
    her_biri=toplam_sure/max(len(gorseller)+len(video_klipleri),1)
    fps=25

    tg(f"Toplam: {toplam_sure/60:.1f} dk | Medya basina: {her_biri:.1f}s","⚙")

    # Tum medyayi isle
    segmentler=[]
    tum_medya = []

    # Gorseller ve video klipleri karistir
    for i, g in enumerate(gorseller): tum_medya.append(("gorsel", i, g))
    for i, v in enumerate(video_klipleri): tum_medya.append(("video", i, v))

    for idx, (tip, i, yol) in enumerate(tum_medya):
        seg=WORK/f"seg_{idx:03d}.mp4"
        fo=max(0,her_biri-0.6); fr=max(int(her_biri*fps),25); d=idx%4

        if tip=="video":
            # Video klibi isle: sure ayarla, yeniden boyutlandir
            cmd_v=["ffmpeg","-y","-i",yol,
                   "-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,setsar=1",
                   "-t",str(her_biri),
                   "-c:v","libx264","-preset","ultrafast","-crf","26",
                   "-an","-pix_fmt","yuv420p",str(seg)]
            r=subprocess.run(cmd_v,capture_output=True,text=True,timeout=120)
            if r.returncode==0 and seg.exists():
                segmentler.append(str(seg))
                tg(f"Klip {idx+1}/{len(tum_medya)} ok","🎬")
                continue

        # Gorsel isle: zoom efekti
        if d==0:   z,x,y="min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        elif d==1: z,x,y="min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)+on*0.5","ih/2-(ih/zoom/2)"
        elif d==2: z,x,y="if(lte(on,1),1.1,max(zoom-0.0008,1.0))","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        else:      z,x,y="min(zoom+0.0006,1.08)","iw/2-(iw/zoom/2)-on*0.4","ih/2-(ih/zoom/2)"

        cmd1=["ffmpeg","-y","-loop","1","-t",str(her_biri+1),"-i",yol,
              "-vf",f"scale=iw*2:ih*2,zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s=1920x1080:fps={fps},"
                    f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
              "-t",str(her_biri),"-c:v","libx264","-preset","ultrafast","-crf","28",
              "-an","-pix_fmt","yuv420p",str(seg)]
        r=subprocess.run(cmd1,capture_output=True,text=True,timeout=300)
        if r.returncode==0 and seg.exists() and seg.stat().st_size>500:
            segmentler.append(str(seg)); tg(f"Seg {idx+1}/{len(tum_medya)} zoom ok","🎬")
        else:
            cmd2=["ffmpeg","-y","-loop","1","-t",str(her_biri),"-i",yol,
                  "-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,"
                        f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
                  "-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
            r2=subprocess.run(cmd2,capture_output=True,text=True,timeout=120)
            if r2.returncode==0 and seg.exists():
                segmentler.append(str(seg)); tg(f"Seg {idx+1} fade ok","⚠")

    if not segmentler: raise Exception("Hicbir segment olusturulamadi!")

    with open(liste,"w") as f:
        for s in segmentler: f.write(f"file '{os.path.abspath(s)}'\n")

    # Video + ses birlestir
    cmd_son=["ffmpeg","-y","-f","concat","-safe","0","-i",str(liste),
             "-i",ses,"-c:v","copy","-c:a","aac","-b:a","192k",
             "-shortest","-movflags","+faststart",str(cikis)]
    r=subprocess.run(cmd_son,capture_output=True,text=True,timeout=3600)
    if r.returncode!=0:
        # copy basarisizsa encode
        cmd_enc=["ffmpeg","-y","-f","concat","-safe","0","-i",str(liste),
                 "-i",ses,"-c:v","libx264","-preset","ultrafast","-crf","26",
                 "-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(cikis)]
        r=subprocess.run(cmd_enc,capture_output=True,text=True,timeout=3600)
        if r.returncode!=0: raise Exception(f"Video birlestirme hatasi: {r.stderr[-150:]}")

    # Altyazi ekle (sarı, siyah çerçeve)
    if altyazi_srt and os.path.exists(altyazi_srt):
        tg("Altyazi ekleniyor (sari, siyah cerceve)...", "📝")
        safe_srt = os.path.abspath(altyazi_srt).replace('\\','/').replace(':','\\:')
        vf_sub = (f"subtitles='{safe_srt}':force_style='"
                  "FontName=DejaVu Sans,FontSize=14,PrimaryColour=&H00FFFF00,"
                  "OutlineColour=&H00000000,BackColour=&H80000000,"
                  "Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=30'")
        cmd_sub=["ffmpeg","-y","-i",str(cikis),"-vf",vf_sub,
                 "-c:v","libx264","-preset","fast","-crf","22",
                 "-c:a","copy",str(cikis_son)]
        r=subprocess.run(cmd_sub,capture_output=True,text=True,timeout=3600)
        if r.returncode==0 and cikis_son.exists():
            tg("Altyazi eklendi!", "✅")
        else:
            tg(f"Altyazi eklenemedi, altyazisiz devam: {r.stderr[-80:]}", "⚠")
            subprocess.run(["cp",str(cikis),str(cikis_son)])
    else:
        subprocess.run(["cp",str(cikis),str(cikis_son)])

    mb=os.path.getsize(cikis_son)/1024/1024
    tg(f"Video hazir! <b>{mb:.0f} MB</b>", "✅")
    return str(cikis_son)

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────
def yt_token():
    r=requests.post("https://oauth2.googleapis.com/token",
        data={"client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,
              "refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},timeout=30)
    if r.status_code!=200: raise Exception(f"YT token: {r.text[:100]}")
    return r.json()["access_token"]

def youtube_yukle(video,thumb,baslik,aciklama,etiketler,yayin_iso):
    tg("YouTube'a yukleniyor...", "📤")
    token=yt_token()
    meta={"snippet":{"title":baslik[:100],"description":aciklama[:5000],
                     "tags":etiketler[:15],"categoryId":"27"},
          "status":{"privacyStatus":"private","publishAt":yayin_iso,"selfDeclaredMadeForKids":False}}
    boyut=os.path.getsize(video)
    init=requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json",
                 "X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(boyut)},
        json=meta,timeout=30)
    if init.status_code!=200: raise Exception(f"YT init: {init.text[:100]}")
    tg(f"Video yukleniyor ({boyut//1024//1024} MB)...", "⏳")
    with open(video,"rb") as f:
        r=requests.put(init.headers["Location"],headers={"Content-Type":"video/mp4"},data=f,timeout=3600)
    if r.status_code not in [200,201]: raise Exception(f"YT yukleme: {r.text[:100]}")
    vid_id=r.json()["id"]; vid_url=f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}", "✅")
    try:
        with open(thumb,"rb") as tf:
            tr=requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},data=tf,timeout=60)
        tg("Thumbnail yuklendi!" if tr.status_code in[200,201] else f"Thumbnail atildi({tr.status_code})",
           "✅" if tr.status_code in[200,201] else "⚠")
    except Exception as e: tg(f"Thumbnail: {str(e)[:40]}","⚠")
    return vid_url,vid_id

# ─── ANA ─────────────────────────────────────────────────────────────────────
def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else ""
    if not cmd: sys.exit(1)
    try: p=komut_isle(cmd)
    except Exception as e: tg(str(e),"❌"); sys.exit(1)

    tg(f"<b>Video Bot v9 Basladi!</b>\n\n"
       f"Konu: <b>{p['konu']}</b>\n"
       f"Sure: {p['sure']} dakika\n"
       f"Gorsel: {p['resim']} adet\n"
       f"Video klip: {p['video_sayisi']} adet\n"
       f"Yayin: {p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}\n"
       f"Altyazi: Sari, siyah cerceve\n"
       f"Stil: Tarihi + Cyberpunk karisimlı","🚀")

    try:
        icerik=senaryo_uret(p["konu"],p["sure"],p["resim"],p["video_sayisi"])
        (WORK/"metadata.json").write_text(json.dumps(icerik,ensure_ascii=False,indent=2))

        muzik=muzik_uret(p["konu"],p["sure"]*60+120)

        gorsel_promptlar=icerik.get("gorseller",[])
        while len(gorsel_promptlar)<p["resim"]:
            gorsel_promptlar.append(f"{p['konu']} dramatic historical cinematic scene {len(gorsel_promptlar)+1} 8k")
        gorseller=gorseller_uret(gorsel_promptlar, p["konu"])

        video_aramalar=icerik.get("video_aramalar",[])
        video_klipleri=videolar_indir(video_aramalar[:p["video_sayisi"]]) if p["video_sayisi"]>0 else []

        thumb=thumbnail_uret(
            icerik.get("thumbnail_prompt", f"{p['konu']} epic dramatic cinematic"),
            icerik.get("thumbnail_metin", p['konu'].upper()[:15]),
            icerik.get("renk","#1a1a2e"),
            p["konu"]
        )
        ses,sure,altyazi=ses_uret(icerik["senaryo"])
        miksli=ses_miksle(ses,muzik,sure)
        video=video_montaj(gorseller,video_klipleri,miksli,altyazi,sure)
        vid_url,_=youtube_yukle(video,thumb,icerik["baslik"],icerik["aciklama"],
                                 icerik["etiketler"],p["yayin_iso"])

        tg(f"<b>TAMAMLANDI!</b>\n\n<b>{icerik['baslik']}</b>\n\n{vid_url}\n\n"
           f"Yayin: <b>{p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}</b>","🎉")
        (WORK/"result.json").write_text(json.dumps({"status":"success","video_url":vid_url,
            "title":icerik["baslik"]},ensure_ascii=False))

    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:300]}","❌")
        (WORK/"result.json").write_text(json.dumps({"status":"error","error":str(e)}))
        sys.exit(1)

if __name__=="__main__":
    main()