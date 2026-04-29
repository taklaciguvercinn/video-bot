#!/usr/bin/env python3
"""Video Bot v8 - Kusursuz, tum problemler cozuldu"""

import sys, os, json, time, requests, subprocess, re
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

# Deneme sirasi - ilki calismassa otomatikolarak digerine gec
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
def tg(mesaj, emoji=""):
    text = f"{emoji} {mesaj}".strip()
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass
    print(text)

def tg_foto(dosya, aciklama):
    try:
        with open(dosya, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": aciklama, "parse_mode": "HTML"},
                files={"photo": f}, timeout=30
            )
    except: pass

# ─── KOMUT ───────────────────────────────────────────────────────────────────
def komut_isle(cmd):
    p = [x.strip() for x in cmd.strip().split(",")]
    if len(p) != 5:
        raise ValueError("Format: Konu,Dakika,Resim,GG.AA.YYYY,SS:DD")
    konu, sure, resim, tarih, saat = p
    yayin = datetime.strptime(f"{tarih} {saat}", "%d.%m.%Y %H:%M")
    return {
        "konu": konu, "sure": int(sure), "resim": int(resim),
        "yayin_dt": yayin,
        "yayin_iso": yayin.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    }

# ─── GEMİNİ - COKLU MODEL DESTEKLI ──────────────────────────────────────────
def gemini(prompt, max_tokens=8192):
    """
    Birden fazla model dener. Biri calismazsa digerine gececek.
    thinkingConfig yok - eski modeller desteklemiyor.
    """
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens,
            }
        }
        for deneme in range(3):
            try:
                r = requests.post(url, headers=headers, json=body, timeout=120)
                if r.status_code == 200:
                    cands = r.json().get("candidates", [])
                    if cands:
                        metin = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        if metin:
                            return metin, model
                    time.sleep(10)
                    continue
                elif r.status_code == 429:
                    tg(f"{model} rate limit, 20s bekleniyor...", "⏳")
                    time.sleep(20)
                elif r.status_code == 503:
                    tg(f"{model} mesgul, baska model deneniyor...", "⏳")
                    break  # Bu modeli birak, digerine gec
                else:
                    err = r.json().get("error", {}).get("message", "")[:80]
                    tg(f"{model} hata: {err}", "⚠")
                    break
            except requests.Timeout:
                tg(f"{model} timeout ({deneme+1}/3)", "⏳")
                time.sleep(10)
            except Exception as e:
                tg(f"{model} exception: {str(e)[:60]}", "⚠")
                break

    raise Exception("Hicbir Gemini modeli yanit vermedi. API key'i kontrol et.")

# ─── JSON PARSE ───────────────────────────────────────────────────────────────
def json_cikart(ham):
    ham = re.sub(r"```json\s*|```\s*", "", ham).strip()
    # Direkt
    try: return json.loads(ham)
    except: pass
    # { } arasi
    s = ham.find("{"); e = ham.rfind("}") + 1
    if s != -1 and e > s:
        seg = ham[s:e]
        try: return json.loads(seg)
        except: pass
        # Apostrof temizle
        try:
            temiz = re.sub(r"(?<=[^\s{,:\[])'(?=[^\s},:!'\]])", "", seg)
            return json.loads(temiz)
        except: pass
    # Alan alan regex
    veri = {}
    for alan, pat in [
        ("baslik",           r'"baslik"\s*:\s*"([^"]{1,120})"'),
        ("aciklama",         r'"aciklama"\s*:\s*"([^"]{1,1000})"'),
        ("thumbnail_metin",  r'"thumbnail_metin"\s*:\s*"([^"]{1,60})"'),
        ("thumbnail_prompt", r'"thumbnail_prompt"\s*:\s*"([^"]{1,400})"'),
        ("renk",             r'"renk"\s*:\s*"(#[0-9a-fA-F]{6})"'),
    ]:
        m = re.search(pat, ham)
        if m: veri[alan] = m.group(1)

    tm = re.search(r'"etiketler"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
    if tm: veri["etiketler"] = re.findall(r'"([^"]+)"', tm.group(1))

    im = re.search(r'"gorseller"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
    if im: veri["gorseller"] = re.findall(r'"([^"]+)"', im.group(1))

    if "baslik" in veri:
        return veri
    raise Exception(f"JSON parse basarisiz: {ham[:80]}")

# ─── SENARYO ─────────────────────────────────────────────────────────────────
def senaryo_uret(konu, sure, resim_sayisi):
    tg(f"'{konu}' icin icerik uretiliyor...", "📚")
    kelime_hedef = sure * 160

    # ADIM 1: Meta + gorsel promptlari
    tg("Adim 1/2: Baslik, SEO, gorsel promptlari...", "📋")
    prompt1 = f"""YouTube belgesel videosu icin icerik uret. Konu: {konu}. Sure: {sure} dakika.
Onemli: JSON string icinde apostrof (tek tirnak) kullanma!
Onemli: Emojileri sadece baslik alaninda kullan.

Asagidaki JSON formatini kesinlikle dondur:
{{
  "baslik": "YouTube basligi maksimum 55 karakter emoji ile",
  "aciklama": "YouTube aciklamasi 400 karakter #hashtag ile biter",
  "etiketler": ["etiket1","etiket2","etiket3","etiket4","etiket5","etiket6","etiket7","etiket8"],
  "gorseller": ["ingilizce sinematik fotograf prompt 1 dramatic lighting 8k ultra detailed","ingilizce sinematik fotograf prompt 2 dramatic lighting 8k ultra detailed","ingilizce sinematik fotograf prompt 3 dramatic lighting 8k ultra detailed"],
  "thumbnail_metin": "KISA ETKILEYICI BASLIK",
  "thumbnail_prompt": "epic dramatic cinematic scene no text vibrant",
  "renk": "#1a1a2e"
}}"""

    meta = None
    for _ in range(5):
        try:
            ham, model = gemini(prompt1, max_tokens=2048)
            meta = json_cikart(ham)
            if "baslik" in meta:
                tg(f"Meta hazir ({model}): <b>{meta['baslik']}</b>", "✅")
                break
        except Exception as e:
            tg(f"Meta hatasi: {str(e)[:80]}", "⚠")
            time.sleep(10)

    if not meta:
        meta = {
            "baslik": f"{konu} - Kapsamli Belgesel",
            "aciklama": f"{konu} hakkinda kapsamli belgesel. #belgesel #tarih #youtube",
            "etiketler": [konu, "belgesel", "tarih", "youtube", "egitim"],
            "gorseller": [f"{konu} dramatic cinematic historical scene {i+1} ultra detailed 8k" for i in range(resim_sayisi)],
            "thumbnail_metin": konu.upper()[:20],
            "thumbnail_prompt": f"{konu} epic dramatic cinematic",
            "renk": "#1a1a2e"
        }
        tg("Meta varsayilan degerlerle devam ediyor", "⚠")

    # Gorsel promptlari tamamla
    while len(meta.get("gorseller", [])) < resim_sayisi:
        meta["gorseller"].append(f"{konu} historical dramatic scene {len(meta['gorseller'])+1} cinematic 8k")

    # ADIM 2: Bolumler halinde senaryo uret (her Gemini cagrisinda 800-1000 kelime)
    tg(f"Adim 2/2: Senaryo bolumler halinde yaziliyor ({kelime_hedef} kelime hedef)...", "📝")
    bolum_sayisi = max(3, sure // 5)  # Her 5 dakika icin 1 bolum
    bolum_kelime = kelime_hedef // bolum_sayisi

    tum_bolumler = []
    for b in range(bolum_sayisi):
        tg(f"Bolum {b+1}/{bolum_sayisi} yaziliyor ({bolum_kelime} kelime)...", "📝")

        if b == 0:
            yon = "Giris: Izleyiciyi aninda ceken, carpici bir gercek veya soru ile basla"
        elif b == bolum_sayisi - 1:
            yon = "Sonuc: Konunun onemini vurgulayan guclu bir kapanis yaz"
        else:
            yon = f"Bolum {b}: {konu} konusunun {b}. ana basligi - detayli ve akici"

        onceki = tum_bolumler[-1][-300:] if tum_bolumler else ""
        baglam = f"Bir onceki bolumun sonu:\n\"{onceki}\"\n\nBu metnin devami olarak yaz.\n\n" if onceki else ""

        prompt_b = f"""{baglam}YouTube belgesel senaryosu - Konu: {konu}

{yon}

Yaklasik {bolum_kelime} kelimelik Turkce duz metin yaz.
Kurallar: Apostrof yok, emoji yok, baslik yok, sadece duz anlatim metni."""

        for _ in range(3):
            try:
                ham, model = gemini(prompt_b, max_tokens=8192)
                ham = re.sub(r'\[.*?\]', '', ham, flags=re.DOTALL)
                ham = re.sub(r'^\*+\s*|\*\*(.*?)\*\*', r'\1', ham)
                ham = re.sub(r'^#+\s.*$', '', ham, flags=re.MULTILINE)
                ham = re.sub(r'\n{3,}', '\n\n', ham).strip()
                if len(ham.split()) > 100:
                    tum_bolumler.append(ham)
                    tg(f"Bolum {b+1}: {len(ham.split())} kelime ({model})", "✅")
                    break
                time.sleep(5)
            except Exception as e:
                tg(f"Bolum {b+1} hatasi: {str(e)[:60]}", "⚠")
                time.sleep(10)

    senaryo = "\n\n".join(tum_bolumler) if tum_bolumler else f"{konu} tarihin en onemli konularindan biridir."
    toplam = len(senaryo.split())
    meta["senaryo"] = senaryo
    tg(f"Senaryo tamamlandi: <b>{toplam} kelime</b> (~{toplam/130:.0f} dk ses) | {resim_sayisi} gorsel promptu", "📊")
    return meta

# ─── MUZİK - FFmpeg (her zaman calisiyor) ────────────────────────────────────
def muzik_uret(konu, sure_sn):
    tg("Konuya ozel muzik uretiliyor...", "🎵")
    yol = WORK / "muzik.mp3"
    k = konu.lower()
    for c, r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]:
        k = k.replace(c, r)

    if any(x in k for x in ["viking","savas","osmanli","roma","selcuklu","tarih","savasc"]):
        # Epik savas tonu
        f1 = "aevalsrc=0.3*sin(55*2*PI*t)+0.2*sin(110*2*PI*t)+0.15*sin(82*2*PI*t)+0.08*sin(41*2*PI*t):s=44100"
    elif any(x in k for x in ["misir","antik","yunan","sumer","babil","mezopotamya","fenike"]):
        # Mistik antik
        f1 = "aevalsrc=0.25*sin(174*2*PI*t)+0.2*sin(261*2*PI*t)+0.15*sin(348*2*PI*t)+0.1*sin(130*2*PI*t):s=44100"
    elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot","gelecek","dijital"]):
        # Uzay ambient
        f1 = "aevalsrc=0.2*sin(220*2*PI*t*(1+0.005*sin(0.1*2*PI*t)))+0.15*sin(330*2*PI*t)+0.1*sin(440*2*PI*t):s=44100"
    elif any(x in k for x in ["doga","hayvan","deniz","orman","okyanus","bitki"]):
        # Doga
        f1 = "aevalsrc=0.15*sin(196*2*PI*t)+0.12*sin(261*2*PI*t)+0.1*sin(329*2*PI*t)+0.08*sin(392*2*PI*t):s=44100"
    elif any(x in k for x in ["gizem","korku","paranormal","komplo","kara","karanl"]):
        # Gizem / karanlık
        f1 = "aevalsrc=0.2*sin(73*2*PI*t)+0.15*sin(110*2*PI*t)+0.1*sin(155*2*PI*t)+0.08*sin(207*2*PI*t):s=44100"
    else:
        # Genel sinematik
        f1 = "aevalsrc=0.2*sin(130*2*PI*t)+0.18*sin(164*2*PI*t)+0.15*sin(196*2*PI*t)+0.1*sin(261*2*PI*t):s=44100"

    fade_out = max(0, sure_sn - 5)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f1,
        "-af", f"aecho=0.8:0.9:100:0.3,afade=t=in:st=0:d=3,afade=t=out:st={fade_out}:d=5,volume=0.6",
        "-t", str(sure_sn + 20),
        "-c:a", "mp3", "-b:a", "128k", str(yol)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and yol.exists():
        tg("Muzik hazir! (Konuya ozel)", "✅")
        return str(yol)
    tg("Muzik basarisiz, muziksiz devam", "⚠")
    return ""

# ─── GORSEL - AKILLI PARALEL İNDİRME ────────────────────────────────────────
def gorsel_indir(i, prompt, toplam):
    """Tek gorsel indir - paralel cagrilacak"""
    yol = WORK / f"img_{i+1:02d}.jpg"

    for model in ["flux", "turbo"]:
        seeds = [i*7+42, i*13+17, i*3+99] if model == "flux" else [i*31+7]
        for seed in seeds:
            enc = quote(f"{prompt}, ultra detailed 4k cinematic photography")
            url = (f"https://image.pollinations.ai/prompt/{enc}"
                   f"?width=1920&height=1080&seed={seed}&nologo=true&model={model}")
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200 and len(r.content) > 10000 and r.content[:2] == b'\xff\xd8':
                    yol.write_bytes(r.content)
                    tg(f"Gorsel {i+1}/{toplam} ✓ ({model})", "🖼")
                    return str(yol)
                elif r.status_code == 429:
                    time.sleep(20)
                else:
                    time.sleep(3)
            except:
                time.sleep(5)

    # FFmpeg gradient yedek
    renkler = [("0x1a1a2e","0x16213e"),("0x2d1b00","0x4a2f00"),
               ("0x0d1b0d","0x1a3a1a"),("0x1a0000","0x3a1a1a"),("0x1a0d1a","0x2d1b2d")]
    r1, _ = renkler[i % len(renkler)]
    subprocess.run(["ffmpeg","-y","-f","lavfi",
        "-i",f"color=c={r1}:size=1920x1080:rate=1",
        "-vframes","1","-q:v","2",str(yol)], capture_output=True)
    tg(f"Gorsel {i+1} yedek", "⚠")
    return str(yol)

def gorseller_uret(promptlar):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    n = len(promptlar)
    # Max 3 paralel - rate limit olmadan hizli
    max_w = min(3, n)
    tg(f"{n} gorsel indiriliyor ({max_w} paralel)\n⏳ Tahmini: ~{max(2, n//max_w)} dk", "🎨")

    sonuclar = {}
    with ThreadPoolExecutor(max_workers=max_w) as ex:
        isler = {ex.submit(gorsel_indir, i, p, n): i for i, p in enumerate(promptlar)}
        for f in as_completed(isler):
            idx = isler[f]
            try:
                sonuclar[idx] = f.result()
            except Exception as e:
                tg(f"Gorsel {idx+1} hata: {str(e)[:40]}", "⚠")
                # Yedek
                yol = WORK / f"img_{idx+1:02d}.jpg"
                subprocess.run(["ffmpeg","-y","-f","lavfi",
                    "-i","color=c=0x1a1a2e:size=1920x1080:rate=1",
                    "-vframes","1",str(yol)], capture_output=True)
                sonuclar[idx] = str(yol)

    return [sonuclar[i] for i in range(n)]

# ─── THUMBNAİL ───────────────────────────────────────────────────────────────
def thumbnail_uret(prompt, metin, renk, konu):
    tg("Thumbnail uretiliyor...", "🖼")
    enc = quote(f"{prompt}, youtube thumbnail dramatic vibrant no text professional")
    url = (f"https://image.pollinations.ai/prompt/{enc}"
           f"?width=1280&height=720&seed=777&nologo=true&model=flux&enhance=true")
    base = WORK / "thumb_base.jpg"
    final = WORK / "thumbnail.jpg"

    for _ in range(5):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200 and len(r.content) > 5000 and r.content[:2] == b'\xff\xd8':
                base.write_bytes(r.content)
                break
            time.sleep(15)
        except:
            time.sleep(15)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi",
            "-i",f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1",
            "-vframes","1",str(base)], capture_output=True)

    m = metin.upper()[:25].replace("'","").replace(":","\\:").replace('"',"")
    k = konu.upper()[:20].replace("'","").replace(":","\\:").replace('"',"")
    fs = 80 if len(m) <= 10 else 60 if len(m) <= 18 else 44
    vf = (
        f"drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.42:color=black@0.72:t=fill,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=black@0.4"
        f":x=(w-text_w)/2+2:y=h*0.62+2:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=white"
        f":x=(w-text_w)/2:y=h*0.62:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{k}':fontsize=30:fontcolor=yellow"
        f":x=20:y=20:font=DejaVu Sans:style=Bold"
    )
    r = subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",vf,"-q:v","2",str(final)],
        capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        subprocess.run(["cp", str(base), str(final)])
    if final.exists():
        tg_foto(str(final), f"Thumbnail: {m}")
    tg("Thumbnail hazir!", "✅")
    return str(final)

# ─── SES ─────────────────────────────────────────────────────────────────────
def ses_uret(senaryo):
    tg("Derin belgesel sesi sentezleniyor...", "🎙")
    sf = WORK / "senaryo.txt"
    rf = WORK / "ses_ham.mp3"
    ff = WORK / "ses.mp3"
    sf.write_text(senaryo, encoding="utf-8")

    # Kelime sayisi kontrol - minimum sure icin
    kelime_sayisi = len(senaryo.split())
    tg(f"Senaryo: {kelime_sayisi} kelime → tahmini {kelime_sayisi/130:.1f} dk ses", "📊")

    # Yontem 1: Parametreli (rate/pitch/volume)
    basarili = False
    for rate, pitch, vol in [("-8%", "-10Hz", "+15%"), ("-5%", "-5Hz", "+10%"), ("0%", "0Hz", "0%")]:
        r = subprocess.run([
            "edge-tts",
            "--voice", "tr-TR-AhmetNeural",
            "--file", str(sf),
            "--write-media", str(rf),
            f"--rate={rate}",
            f"--pitch={pitch}",
            f"--volume={vol}"
        ], capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and rf.exists() and rf.stat().st_size > 1000:
            basarili = True
            tg(f"Ses uretildi (rate={rate}, pitch={pitch})", "✅")
            break
        time.sleep(3)

    if not basarili:
        tg("Tum parametreler basarisiz, sade ses deneniyor...", "⚠")
        r2 = subprocess.run([
            "edge-tts", "--voice", "tr-TR-AhmetNeural",
            "--file", str(sf), "--write-media", str(rf)
        ], capture_output=True, text=True, timeout=300)
        if r2.returncode != 0 or not rf.exists():
            raise Exception(f"TTS tamamen basarisiz: {r2.stderr[-100:]}")

    # Ses suresi kontrol
    probe1 = subprocess.run(["ffprobe","-v","quiet","-print_format","json",
        "-show_format", str(rf)], capture_output=True, text=True)
    sure_ham = float(json.loads(probe1.stdout)["format"]["duration"])
    tg(f"Ham ses suresi: {sure_ham/60:.1f} dakika", "⏱")

    if sure_ham < 60:
        tg(f"UYARI: Ses cok kisa! ({sure_ham:.0f}s) Senaryo yeterince uzun degil.", "⚠")

    # EQ - derin belgesel tonu
    eq = subprocess.run([
        "ffmpeg", "-y", "-i", str(rf), "-af",
        ("equalizer=f=80:width_type=o:width=2:g=5,"
         "equalizer=f=200:width_type=o:width=2:g=3,"
         "equalizer=f=3000:width_type=o:width=2:g=-3,"
         "equalizer=f=8000:width_type=o:width=2:g=-5,"
         "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,"
         "volume=1.3"),
        "-c:a", "mp3", "-b:a", "192k", str(ff)
    ], capture_output=True, text=True)

    kullan = str(ff) if (eq.returncode == 0 and ff.exists()) else str(rf)
    probe2 = subprocess.run(["ffprobe","-v","quiet","-print_format","json",
        "-show_format", kullan], capture_output=True, text=True)
    sure = float(json.loads(probe2.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b>", "✅")
    return kullan, sure

# ─── SES MİKS ────────────────────────────────────────────────────────────────
def ses_miksle(anlati, muzik, sure):
    if not muzik or not os.path.exists(muzik):
        return anlati
    tg("Ses + Muzik karistiriliyor (Anlati %100 + Muzik %15)...", "🎚")
    miksl = WORK / "miksl.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", anlati,
        "-stream_loop", "-1", "-i", muzik,
        "-filter_complex",
        f"[1:a]volume=0.15,atrim=0:{sure+2}[muz];"
        f"[0:a][muz]amix=inputs=2:duration=first:weights=1 0.15[out]",
        "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(sure), str(miksl)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and miksl.exists():
        tg("Ses karisimi hazir!", "✅")
        return str(miksl)
    return anlati

# ─── VIDEO MONTAJ ────────────────────────────────────────────────────────────
def video_montaj(gorseller, ses, toplam_sure):
    tg(f"Video montajlaniyor...\n"
       f"🖼 {len(gorseller)} gorsel | Zoom + Pan + Fade\n"
       f"⏳ Tahmini: ~{len(gorseller)//2 + 5} dakika", "🎬")

    cikis = WORK / "video.mp4"
    liste = WORK / "liste.txt"
    her_biri = toplam_sure / len(gorseller)
    fps = 25
    tg(f"Toplam: {toplam_sure/60:.1f} dk | Her gorsel: {her_biri:.1f}s", "⚙")

    segmentler = []
    for i, gorsel in enumerate(gorseller):
        seg = WORK / f"seg_{i:02d}.mp4"
        fo = max(0, her_biri - 0.7)
        fr = max(int(her_biri * fps), 25)
        d = i % 4

        if d == 0:   z,x,y = "min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        elif d == 1: z,x,y = "min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)+on*0.5","ih/2-(ih/zoom/2)"
        elif d == 2: z,x,y = "if(lte(on,1),1.1,max(zoom-0.0008,1.0))","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        else:        z,x,y = "min(zoom+0.0006,1.08)","iw/2-(iw/zoom/2)-on*0.4","ih/2-(ih/zoom/2)"

        # Yontem 1: Zoom (RAM dostu - 2x scale)
        cmd1 = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(her_biri + 1), "-i", gorsel,
            "-vf",
            f"scale=iw*2:ih*2,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s=1920x1080:fps={fps},"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
            "-t", str(her_biri),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", "-pix_fmt", "yuv420p", str(seg)
        ]
        r = subprocess.run(cmd1, capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and seg.exists() and seg.stat().st_size > 500:
            segmentler.append(str(seg))
            tg(f"Seg {i+1}/{len(gorseller)} zoom ok", "🎬")
            continue

        # Yontem 2: Pan efekti
        pan = str(min(i*3, 80)) if i % 2 == 0 else str(max(-80, -i*3))
        cmd2 = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(her_biri), "-i", gorsel,
            "-vf",
            f"scale=2100:1181,crop=1920:1080:{pan}:50,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", "-pix_fmt", "yuv420p", str(seg)
        ]
        r = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and seg.exists():
            segmentler.append(str(seg))
            tg(f"Seg {i+1} pan ok", "⚠")
            continue

        # Yontem 3: Sadece fade
        cmd3 = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(her_biri), "-i", gorsel,
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:-1:-1,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", "-pix_fmt", "yuv420p", str(seg)
        ]
        r = subprocess.run(cmd3, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            segmentler.append(str(seg))
            tg(f"Seg {i+1} fade ok", "⚠")

    if not segmentler:
        raise Exception("Hicbir segment olusturulamadi!")

    with open(liste, "w") as f:
        for s in segmentler:
            f.write(f"file '{os.path.abspath(s)}'\n")

    cmd_son = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(liste),
        "-i", ses,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(cikis)
    ]
    r = subprocess.run(cmd_son, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise Exception(f"Birlestirme hatasi: {r.stderr[-200:]}")

    mb = os.path.getsize(cikis) / 1024 / 1024
    tg(f"Video hazir! <b>{mb:.0f} MB</b>", "✅")
    return str(cikis)

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────
def yt_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }, timeout=30)
    if r.status_code != 200:
        raise Exception(f"YT token: {r.text[:100]}")
    return r.json()["access_token"]

def youtube_yukle(video, thumb, baslik, aciklama, etiketler, yayin_iso):
    tg("YouTube'a yukleniyor...", "📤")
    token = yt_token()
    meta = {
        "snippet": {
            "title": baslik[:100],
            "description": aciklama[:5000],
            "tags": etiketler[:15],
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": yayin_iso,
            "selfDeclaredMadeForKids": False
        }
    }
    boyut = os.path.getsize(video)
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(boyut)
        },
        json=meta, timeout=30
    )
    if init.status_code != 200:
        raise Exception(f"YT init: {init.text[:100]}")

    tg(f"Video dosyasi yukleniyor ({boyut//1024//1024} MB)...", "⏳")
    with open(video, "rb") as f:
        r = requests.put(
            init.headers["Location"],
            headers={"Content-Type": "video/mp4"},
            data=f, timeout=900
        )
    if r.status_code not in [200, 201]:
        raise Exception(f"YT yukleme: {r.text[:100]}")

    vid_id = r.json()["id"]
    vid_url = f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}", "✅")

    try:
        with open(thumb, "rb") as tf:
            tr = requests.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                data=tf, timeout=60
            )
        tg("Thumbnail yuklendi!" if tr.status_code in [200, 201]
           else f"Thumbnail atildi ({tr.status_code})",
           "✅" if tr.status_code in [200, 201] else "⚠")
    except Exception as e:
        tg(f"Thumbnail: {str(e)[:50]}", "⚠")

    return vid_url, vid_id

# ─── ANA ─────────────────────────────────────────────────────────────────────
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if not cmd:
        print("Kullanim: python generate_video.py 'Konu,Dakika,Resim,GG.AA.YYYY,SS:DD'")
        sys.exit(1)

    try:
        p = komut_isle(cmd)
    except Exception as e:
        tg(str(e), "❌")
        sys.exit(1)

    tg(
        f"<b>Video Bot v8 Basladi!</b>\n\n"
        f"Konu: <b>{p['konu']}</b>\n"
        f"Sure: {p['sure']} dakika\n"
        f"Gorsel: {p['resim']} adet\n"
        f"Yayin: {p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Muzik: FFmpeg (garantili)\n"
        f"AI: Gemini coklu model (garantili)",
        "🚀"
    )

    try:
        icerik = senaryo_uret(p["konu"], p["sure"], p["resim"])
        (WORK / "metadata.json").write_text(
            json.dumps(icerik, ensure_ascii=False, indent=2))

        muzik = muzik_uret(p["konu"], p["sure"] * 60 + 120)
        gorseller = gorseller_uret(icerik["gorseller"])
        thumb = thumbnail_uret(
            icerik["thumbnail_prompt"], icerik["thumbnail_metin"],
            icerik.get("renk", "#1a1a2e"), p["konu"]
        )
        ses, sure = ses_uret(icerik["senaryo"])
        miksli = ses_miksle(ses, muzik, sure)
        video = video_montaj(gorseller, miksli, sure)
        vid_url, _ = youtube_yukle(
            video, thumb, icerik["baslik"], icerik["aciklama"],
            icerik["etiketler"], p["yayin_iso"]
        )

        tg(
            f"<b>TAMAMLANDI!</b>\n\n"
            f"<b>{icerik['baslik']}</b>\n\n"
            f"{vid_url}\n\n"
            f"Yayin: <b>{p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"Bilgisayarin kapali olsa bile YouTube otomatik yayinlayacak!",
            "🎉"
        )
        (WORK / "result.json").write_text(
            json.dumps({"status": "success", "video_url": vid_url,
                        "title": icerik["baslik"]}, ensure_ascii=False))

    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:300]}", "❌")
        (WORK / "result.json").write_text(
            json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()