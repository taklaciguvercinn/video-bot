#!/usr/bin/env python3
"""Video Bot v6 - Tum problemler cozuldu, production ready"""

import sys, os, json, time, requests, subprocess, re
import threading
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

WORK = Path("./output")
WORK.mkdir(exist_ok=True)
_lock = threading.Lock()
_done = 0

# ─── MUZİK HARİTASI ──────────────────────────────────────────────────────────
GH = "https://raw.githubusercontent.com/taklaciguvercinn/video-bot/main"
MUZIK = {
    "viking":      f"{GH}/nastelbom-epic-501714.mp3",
    "savas":       f"{GH}/nastelbom-epic-501714.mp3",
    "osmanli":     f"{GH}/nastelbom-epic-501714.mp3",
    "selcuklu":    f"{GH}/nastelbom-epic-501714.mp3",
    "roma":        f"{GH}/nastelbom-epic-501714.mp3",
    "ortacag":     f"{GH}/nastelbom-epic-501714.mp3",
    "misir":       f"{GH}/onetent-ancient-181070.mp3",
    "antik":       f"{GH}/onetent-ancient-181070.mp3",
    "yunan":       f"{GH}/onetent-ancient-181070.mp3",
    "sumer":       f"{GH}/onetent-ancient-181070.mp3",
    "mezopotamya": f"{GH}/onetent-ancient-181070.mp3",
    "uzay":        f"{GH}/the_mountain-space-438391.mp3",
    "yapay":       f"{GH}/the_mountain-space-438391.mp3",
    "teknoloji":   f"{GH}/the_mountain-space-438391.mp3",
    "bilim":       f"{GH}/the_mountain-space-438391.mp3",
    "doga":        f"{GH}/sonican-background-music-new-age-nature-465069.mp3",
    "hayvan":      f"{GH}/sonican-background-music-new-age-nature-465069.mp3",
    "deniz":       f"{GH}/sonican-background-music-new-age-nature-465069.mp3",
    "gizem":       f"{GH}/studiokolomna-risk-136788.mp3",
    "korku":       f"{GH}/studiokolomna-risk-136788.mp3",
    "mitoloji":    f"{GH}/studiokolomna-risk-136788.mp3",
}
MUZIK_DEFAULT = f"{GH}/atlasaudio-ambient-soundscapes-511893.mp3"

def muzik_sec(konu):
    k = konu.lower()
    k = k.replace("ş","s").replace("ğ","g").replace("ı","i")
    k = k.replace("ö","o").replace("ü","u").replace("ç","c")
    for anahtar, url in MUZIK.items():
        if anahtar in k:
            return anahtar, url
    return "cinematic", MUZIK_DEFAULT

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
                files={"photo": f},
                timeout=30
            )
    except: pass

# ─── KOMUT PARSE ─────────────────────────────────────────────────────────────
def komut_isle(cmd):
    p = [x.strip() for x in cmd.strip().split(",")]
    if len(p) != 5:
        raise ValueError(f"Yanlis format! Dogru: Konu,Dakika,Resim,GG.AA.YYYY,SS:DD")
    konu, sure, resim, tarih, saat = p
    yayın = datetime.strptime(f"{tarih} {saat}", "%d.%m.%Y %H:%M")
    return {
        "konu": konu, "sure": int(sure), "resim": int(resim),
        "yayin_dt": yayın, "yayin_iso": yayın.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    }

# ─── GEMİNİ API - DUZELTİLMİS ────────────────────────────────────────────────
def gemini(prompt):
    """
    FIX: API key header'da gonderilmeli, URL'de degil
    FIX: Kisa prompt → timeout yok
    FIX: thinkingConfig ile daha hizli yanit
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY  # KEY HEADER'DA - duzeltildi
    }
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "thinkingConfig": {"thinkingBudget": 0}  # Dusunme modu kapali = hizli
        }
    }
    for deneme in range(5):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=120)
            if r.status_code == 200:
                veri = r.json()
                adaylar = veri.get("candidates", [])
                if adaylar:
                    metin = adaylar[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    if metin:
                        return metin
                # Bos yanit - tekrar dene
                tg(f"Gemini bos yanit ({deneme+1}/5), bekleniyor...", "⏳")
                time.sleep(15)
                continue
            elif r.status_code == 429:
                bekle = 30 * (deneme + 1)
                tg(f"Gemini rate limit, {bekle}s bekleniyor...", "⏳")
                time.sleep(bekle)
            elif r.status_code == 503:
                tg(f"Gemini mesgul ({deneme+1}/5), 20s bekleniyor...", "⏳")
                time.sleep(20)
            else:
                hata = r.json().get("error", {}).get("message", r.text[:100])
                raise Exception(f"Gemini HTTP {r.status_code}: {hata}")
        except requests.Timeout:
            tg(f"Gemini timeout ({deneme+1}/5), tekrar deneniyor...", "⏳")
            time.sleep(10)
    raise Exception("Gemini 5 denemede yanit vermedi")

# ─── SENARYO + SEO ───────────────────────────────────────────────────────────
def senaryo_uret(konu, sure, resim_sayisi):
    tg(f"'{konu}' arastiriliyor ve senaryo yaziliyor...", "📚")
    kelime = sure * 150

    # KISA PROMPT - timeout yok
    prompt = f"""YouTube belgesel videosu icin JSON uret. Konu: {konu}. Sure: {sure} dakika.

KRITIK: JSON string icinde tek tirnak (') KULLANMA. Apostrof yerine baska kelime sec.
KRITIK: Senaryo SADECE seslendirilecek metin - hicbir gorsel notu veya teknik bilgi yok.
KRITIK: Emojileri SADECE baslik alaninda kullan.

Tam bu JSON formatini dondur:
{{
"baslik": "YouTube basligi max 55 karakter emoji ile",
"aciklama": "YouTube aciklamasi 400 karakter #hashtag ile biter",
"etiketler": ["etiket1","etiket2","etiket3","etiket4","etiket5","etiket6","etiket7","etiket8"],
"senaryo": "Seslendirilecek Turkce belgesel metni. {kelime} kelime. Apostrof yok.",
"gorseller": ["sinematik ingilizce prompt 1 dramatic 8k","sinematik ingilizce prompt 2 dramatic 8k","sinematik ingilizce prompt 3 dramatic 8k"],
"thumbnail_metin": "MAX 3 KELIME",
"thumbnail_prompt": "epic dramatic cinematic scene no text",
"renk": "#1a1a2e"
}}"""

    for deneme in range(5):
        try:
            ham = gemini(prompt)

            # JSON cikart
            ham = re.sub(r"```json\s*|```\s*", "", ham).strip()
            veri = None

            # Yontem 1: Direkt
            try:
                veri = json.loads(ham)
            except: pass

            # Yontem 2: { } arasi
            if not veri:
                s = ham.find("{")
                e = ham.rfind("}") + 1
                if s != -1 and e > s:
                    try:
                        veri = json.loads(ham[s:e])
                    except: pass

            # Yontem 3: Apostrof temizle
            if not veri:
                s = ham.find("{")
                e = ham.rfind("}") + 1
                if s != -1 and e > s:
                    try:
                        temiz = ham[s:e]
                        # String icindeki apostrof kaldir
                        temiz = re.sub(r"(?<=[a-zA-ZğüşıöçĞÜŞİÖÇ])'(?=[a-zA-ZğüşıöçĞÜŞİÖÇ])", "", temiz)
                        veri = json.loads(temiz)
                    except: pass

            # Yontem 4: Alan alan regex
            if not veri:
                veri = {}
                for alan, desen in [
                    ("baslik",    r'"baslik"\s*:\s*"([^"]{1,80})"'),
                    ("aciklama",  r'"aciklama"\s*:\s*"([^"]{1,600})"'),
                    ("thumbnail_metin", r'"thumbnail_metin"\s*:\s*"([^"]{1,40})"'),
                    ("thumbnail_prompt", r'"thumbnail_prompt"\s*:\s*"([^"]{1,200})"'),
                    ("renk",      r'"renk"\s*:\s*"([^"]{4,20})"'),
                ]:
                    m = re.search(desen, ham)
                    if m:
                        veri[alan] = m.group(1)

                # Uzun senaryo
                sm = re.search(r'"senaryo"\s*:\s*"([\s\S]{50,}?)"(?=\s*,\s*"(?:gorsel|thumb|etiket|renk))', ham)
                if sm:
                    veri["senaryo"] = sm.group(1)

                tm = re.search(r'"etiketler"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
                if tm:
                    veri["etiketler"] = re.findall(r'"([^"]+)"', tm.group(1))

                im = re.search(r'"gorseller"\s*:\s*\[(.*?)\]', ham, re.DOTALL)
                if im:
                    veri["gorseller"] = re.findall(r'"([^"]+)"', im.group(1))

            if not veri or "baslik" not in veri:
                raise Exception(f"JSON alinamadi: {ham[:80]}")

            if "senaryo" not in veri or len(veri.get("senaryo", "")) < 50:
                raise Exception("Senaryo bos veya cok kisa")

            # Temizle
            sc = veri["senaryo"]
            sc = re.sub(r'\[.*?\]', '', sc, flags=re.DOTALL)
            sc = re.sub(r'Gorsel\s*\d+\s*:', '', sc)
            sc = re.sub(r'Resim\s*\d+\s*:', '', sc)
            sc = re.sub(r'\n{3,}', '\n\n', sc)
            veri["senaryo"] = sc.strip()

            # Gorsel promptlari tamamla
            gorseller = veri.get("gorseller", [])
            while len(gorseller) < resim_sayisi:
                gorseller.append(f"{konu} dramatic cinematic historical scene {len(gorseller)+1}, 8k")
            veri["gorseller"] = gorseller

            # Varsayilanlar
            veri.setdefault("thumbnail_metin", konu.upper()[:15])
            veri.setdefault("thumbnail_prompt", f"{konu} epic dramatic cinematic")
            veri.setdefault("renk", "#1a1a2e")
            veri.setdefault("etiketler", [konu, "belgesel", "tarih", "youtube"])
            veri.setdefault("aciklama", f"{konu} hakkinda belgesel. #belgesel #tarih")

            tg(
                f"Senaryo hazir!\n"
                f"<b>{veri['baslik']}</b>\n"
                f"{len(veri['senaryo'].split())} kelime | {len(veri['gorseller'])} gorsel",
                "✅"
            )
            return veri

        except Exception as e:
            tg(f"Senaryo hatasi ({deneme+1}/5): {str(e)[:100]}", "⚠")
            time.sleep(20)

    raise Exception("Senaryo 5 denemede uretilemedi")

# ─── MUZİK İNDİR ─────────────────────────────────────────────────────────────
def muzik_indir(konu):
    tip, url = muzik_sec(konu)
    tg(f"Muzik indiriliyor: {tip}", "🎵")
    yol = WORK / "muzik.mp3"

    # Private repo icin GitHub token gerekli
    gh_token = os.environ.get("GITHUB_TOKEN_A", "")
    basliklar = {
        "User-Agent": "Mozilla/5.0 (compatible; VideoBot/6.0)",
        "Accept": "application/octet-stream"
    }
    if gh_token:
        basliklar["Authorization"] = f"token {gh_token}"

    for deneme in range(4):
        try:
            r = requests.get(url, headers=basliklar, timeout=90, stream=True)
            if r.status_code == 200:
                veri = b"".join(r.iter_content(8192))
                if len(veri) > 10000:
                    yol.write_bytes(veri)
                    tg(f"Muzik indirildi! ({len(veri)//1024} KB)", "✅")
                    return str(yol)
            tg(f"Muzik HTTP {r.status_code} ({deneme+1}/4)", "⚠")
            time.sleep(8)
        except Exception as e:
            tg(f"Muzik hatasi ({deneme+1}/4): {str(e)[:60]}", "⚠")
            time.sleep(8)

    tg("Muzik indirilemedi, muziksiz devam", "⚠")
    return ""

# ─── GORSEL URET ─────────────────────────────────────────────────────────────
def _gorsel_indir(args):
    global _done
    i, prompt, toplam = args
    yol = WORK / f"img_{i+1:02d}.jpg"

    # 3 farkli seed dene
    for seed in [i*7+42, i*13+7, i*3+99]:
        enc = quote(f"{prompt}, ultra detailed 4k cinematic photography")
        url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={seed}&nologo=true&model=flux"
        for _ in range(3):
            try:
                r = requests.get(url, timeout=120)
                if r.status_code == 200 and len(r.content) > 15000:
                    if r.content[:2] == b'\xff\xd8':  # Gecerli JPEG
                        yol.write_bytes(r.content)
                        with _lock:
                            _done += 1; d = _done
                        tg(f"Gorsel {d}/{toplam} hazir", "🖼")
                        return (i, str(yol))
                time.sleep(6)
            except:
                time.sleep(8)

    # Yedek: renkli gradient
    renkler = ["0x1a1a2e", "0x2d1b69", "0x1a3a1a", "0x3a1a1a"]
    renk = renkler[i % len(renkler)]
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={renk}:size=1920x1080:rate=1",
        "-vframes", "1", "-q:v", "2", str(yol)], capture_output=True)
    with _lock:
        _done += 1
    tg(f"Gorsel {i+1} yedek renk kullanildi", "⚠")
    return (i, str(yol))

def gorseller_uret(promptlar):
    global _done
    _done = 0
    tg(f"{len(promptlar)} gorsel uretiliyor... (~{max(3,len(promptlar)//5)} dk)", "🎨")
    sonuclar = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        isler = {ex.submit(_gorsel_indir, (i, p, len(promptlar))): i for i, p in enumerate(promptlar)}
        for f in as_completed(isler):
            idx, yol = f.result()
            sonuclar[idx] = yol
    return [sonuclar[i] for i in range(len(promptlar))]

# ─── THUMBNAİL ───────────────────────────────────────────────────────────────
def thumbnail_uret(prompt, metin, renk, konu):
    tg("Thumbnail uretiliyor...", "🖼")
    enc = quote(f"{prompt}, youtube thumbnail, no text, dramatic lighting, vibrant")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=99&nologo=true&model=flux"
    base = WORK / "thumb_base.jpg"
    final = WORK / "thumbnail.jpg"

    for _ in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                base.write_bytes(r.content)
                break
            time.sleep(8)
        except:
            time.sleep(8)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1",
            "-vframes", "1", str(base)], capture_output=True)

    # Metin ekle
    m = metin.upper()[:25].replace("'", "").replace(":", "\\:")
    k = konu.upper()[:20].replace("'", "").replace(":", "\\:")
    boyut = 80 if len(m) <= 10 else 60 if len(m) <= 18 else 44
    vf = (
        f"drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.42:color=black@0.72:t=fill,"
        f"drawtext=text='{m}':fontsize={boyut}:fontcolor=black@0.4"
        f":x=(w-text_w)/2+2:y=h*0.62+2:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{m}':fontsize={boyut}:fontcolor=white"
        f":x=(w-text_w)/2:y=h*0.62:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{k}':fontsize=30:fontcolor=yellow"
        f":x=20:y=20:font=DejaVu Sans:style=Bold"
    )
    r = subprocess.run(["ffmpeg", "-y", "-i", str(base), "-vf", vf, "-q:v", "2", str(final)],
        capture_output=True, text=True)
    if r.returncode != 0 or not final.exists():
        subprocess.run(["cp", str(base), str(final)])

    if final.exists():
        tg_foto(str(final), f"Thumbnail: {m}")
    tg("Thumbnail hazir!", "✅")
    return str(final)

# ─── SES ─────────────────────────────────────────────────────────────────────
def ses_uret(senaryo):
    """FIX: edge-tts parametre formati duzeltildi"""
    tg("Derin belgesel sesi sentezleniyor...", "🎙")
    sc_f = WORK / "senaryo.txt"
    ham_f = WORK / "ses_ham.mp3"
    son_f = WORK / "ses.mp3"
    sc_f.write_text(senaryo, encoding="utf-8")

    # Derin ses - duzeltilmis parametreler
    r = subprocess.run([
        "edge-tts",
        "--voice", "tr-TR-AhmetNeural",
        "--file", str(sc_f),
        "--write-media", str(ham_f),
        "--rate=-8%",    # FIX: = isareti ile bitisik
        "--pitch=-10Hz", # FIX: = isareti ile bitisik
        "--volume=+15%"  # FIX: = isareti ile bitisik
    ], capture_output=True, text=True)

    if r.returncode != 0 or not ham_f.exists():
        tg("Parametreli ses basarisiz, sade ses deneniyor...", "⚠")
        r2 = subprocess.run([
            "edge-tts", "--voice", "tr-TR-AhmetNeural",
            "--file", str(sc_f), "--write-media", str(ham_f)
        ], capture_output=True, text=True)
        if r2.returncode != 0 or not ham_f.exists():
            raise Exception(f"TTS tamamen basarisiz: {r2.stderr[-150:]}")

    # EQ - belgesel tonu (bas + derin)
    eq = subprocess.run([
        "ffmpeg", "-y", "-i", str(ham_f), "-af",
        "equalizer=f=80:width_type=o:width=2:g=5,"
        "equalizer=f=200:width_type=o:width=2:g=3,"
        "equalizer=f=3000:width_type=o:width=2:g=-3,"
        "equalizer=f=8000:width_type=o:width=2:g=-5,"
        "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,"
        "volume=1.3",
        "-c:a", "mp3", "-b:a", "192k", str(son_f)
    ], capture_output=True, text=True)

    kullan = str(son_f) if (eq.returncode == 0 and son_f.exists()) else str(ham_f)

    probe = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", kullan], capture_output=True, text=True)
    sure = float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b> | Derin belgesel tonu", "✅")
    return kullan, sure

# ─── SES MİKSİ ───────────────────────────────────────────────────────────────
def ses_miksle(anlati, muzik, sure):
    if not muzik or not os.path.exists(muzik):
        return anlati
    tg("Ses ve muzik karistiriliyor... (Anlati %100, Muzik %18)", "🎚")
    miksl = WORK / "miksl.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", anlati,
        "-stream_loop", "-1", "-i", muzik,
        "-filter_complex",
        f"[1:a]volume=0.18,atrim=0:{sure+2}[muz];"
        f"[0:a][muz]amix=inputs=2:duration=first:weights=1 0.18[cikis]",
        "-map", "[cikis]",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(sure),
        str(miksl)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and miksl.exists():
        tg("Muzik karisimi hazir!", "✅")
        return str(miksl)
    tg("Muzik karistirma basarisiz, sadece anlati", "⚠")
    return anlati

# ─── VİDEO MONTAJ ────────────────────────────────────────────────────────────
def video_montaj(gorseller, ses, toplam_sure):
    tg(
        f"Video montajlaniyor...\n"
        f"🖼 {len(gorseller)} gorsel | Zoom + Fade efektleri\n"
        f"⏳ Tahmini: ~{len(gorseller)//2 + 5} dakika",
        "🎬"
    )
    cikis = WORK / "video.mp4"
    liste = WORK / "liste.txt"
    her_biri = toplam_sure / len(gorseller)
    fps = 25
    tg(f"Toplam: {toplam_sure/60:.1f} dk | Her gorsel: {her_biri:.1f}s", "⚙")

    segmentler = []
    for i, gorsel in enumerate(gorseller):
        seg = WORK / f"seg_{i:02d}.mp4"
        d = i % 4
        fo = max(0, her_biri - 0.6)
        fr = max(int(her_biri * fps), 25)

        # RAM dostu zoom - 2x scale yeterli
        if d == 0:   z,x,y = "min(zoom+0.0008,1.1)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif d == 1: z,x,y = "min(zoom+0.0008,1.1)", "iw/2-(iw/zoom/2)+on*0.5", "ih/2-(ih/zoom/2)"
        elif d == 2: z,x,y = "if(lte(on,1),1.1,max(zoom-0.0008,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        else:        z,x,y = "min(zoom+0.0006,1.08)", "iw/2-(iw/zoom/2)-on*0.4", "ih/2-(ih/zoom/2)"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(her_biri + 1), "-i", gorsel,
            "-vf",
            f"scale=2*iw:-1,"  # RAM dostu - sadece 2x buyut
            f"crop=iw/2:ih/2,"  # Merkezi kes
            f"scale=1920:1080,"  # 1080p'e getir
            f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s=1920x1080:fps={fps},"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
            "-t", str(her_biri),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", "-pix_fmt", "yuv420p", str(seg)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and seg.exists() and seg.stat().st_size > 500:
            segmentler.append(str(seg))
            tg(f"Segment {i+1}/{len(gorseller)} zoom ok", "🎬")
        else:
            # Yedek: basit pan efekti
            pan_x = f"if(lte(on,1),0,min(on*{2 if i%2==0 else -2},iw*0.05))"
            cmd2 = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", str(her_biri), "-i", gorsel,
                "-vf",
                f"scale=2000:1125,"
                f"crop=1920:1080:x='{pan_x}':y=0,"
                f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-an", "-pix_fmt", "yuv420p", str(seg)
            ]
            r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
            if r2.returncode == 0 and seg.exists():
                segmentler.append(str(seg))
                tg(f"Segment {i+1} pan efekti ok", "⚠")
            else:
                # Son yedek: sadece fade
                cmd3 = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-t", str(her_biri), "-i", gorsel,
                    "-vf",
                    f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                    f"pad=1920:1080:-1:-1,"
                    f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-an", "-pix_fmt", "yuv420p", str(seg)
                ]
                r3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=120)
                if r3.returncode == 0:
                    segmentler.append(str(seg))
                    tg(f"Segment {i+1} fade ok", "⚠")
                else:
                    tg(f"Segment {i+1} atildi!", "❌")

    if not segmentler:
        raise Exception("Hicbir segment olusturulamadi!")

    # Birlestir
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
        raise Exception(f"Birlestirme hatasi: {r.stderr[-300:]}")

    mb = os.path.getsize(cikis) / 1024 / 1024
    tg(f"Video hazir! Boyut: <b>{mb:.0f} MB</b>", "✅")
    return str(cikis)

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────
def yt_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID, "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN, "grant_type": "refresh_token"
    }, timeout=30)
    if r.status_code != 200:
        raise Exception(f"YT token hatasi: {r.text[:200]}")
    return r.json()["access_token"]

def youtube_yukle(video, thumbnail, baslik, aciklama, etiketler, yayin_iso):
    tg("YouTube'a yukleniyor...", "📤")
    token = yt_token()
    meta = {
        "snippet": {
            "title": baslik[:100], "description": aciklama[:5000],
            "tags": etiketler[:15], "categoryId": "27"
        },
        "status": {
            "privacyStatus": "private", "publishAt": yayin_iso,
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
        raise Exception(f"YT baslangic hatasi: {init.text[:200]}")

    yukle_url = init.headers["Location"]
    tg(f"Video dosyasi yukleniyor ({boyut//1024//1024} MB)...", "⏳")
    with open(video, "rb") as f:
        r = requests.put(yukle_url, headers={"Content-Type": "video/mp4"}, data=f, timeout=900)
    if r.status_code not in [200, 201]:
        raise Exception(f"YT yukleme hatasi: {r.text[:200]}")

    vid_id = r.json()["id"]
    vid_url = f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}", "✅")

    # Thumbnail yukle
    tg("Thumbnail yukleniyor...", "🖼")
    try:
        with open(thumbnail, "rb") as tf:
            tr = requests.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                data=tf, timeout=60
            )
        tg("Thumbnail yuklendi!" if tr.status_code in [200,201] else f"Thumbnail atildi ({tr.status_code})",
           "✅" if tr.status_code in [200,201] else "⚠")
    except Exception as e:
        tg(f"Thumbnail hatasi: {str(e)[:60]}", "⚠")

    return vid_url, vid_id

# ─── ANA AKIS ────────────────────────────────────────────────────────────────
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

    muzik_tipi, _ = muzik_sec(p["konu"])
    tg(
        f"<b>Video Bot v6 Basladi!</b>\n\n"
        f"Konu: <b>{p['konu']}</b>\n"
        f"Sure: {p['sure']} dakika\n"
        f"Gorsel: {p['resim']} adet\n"
        f"Yayin: {p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Muzik: {muzik_tipi}\n"
        f"Ses: Derin belgesel tonu",
        "🚀"
    )

    try:
        # 1. Senaryo + SEO
        icerik = senaryo_uret(p["konu"], p["sure"], p["resim"])
        (WORK / "metadata.json").write_text(json.dumps(icerik, ensure_ascii=False, indent=2))

        # 2. Muzik indir
        muzik = muzik_indir(p["konu"])

        # 3. Gorseller
        gorsel_listesi = gorseller_uret(icerik["gorseller"])

        # 4. Thumbnail
        thumb = thumbnail_uret(
            icerik["thumbnail_prompt"], icerik["thumbnail_metin"],
            icerik["renk"], p["konu"]
        )

        # 5. Ses
        ses, sure = ses_uret(icerik["senaryo"])

        # 6. Muzik miksle
        miksli = ses_miksle(ses, muzik, sure)

        # 7. Video montaj
        video = video_montaj(gorsel_listesi, miksli, sure)

        # 8. YouTube'a yukle
        vid_url, vid_id = youtube_yukle(
            video, thumb,
            icerik["baslik"], icerik["aciklama"],
            icerik["etiketler"], p["yayin_iso"]
        )

        yayin_str = p["yayin_dt"].strftime("%d.%m.%Y saat %H:%M")
        tg(
            f"<b>TAMAMLANDI!</b>\n\n"
            f"<b>{icerik['baslik']}</b>\n\n"
            f"{vid_url}\n\n"
            f"Yayin: <b>{yayin_str}</b>\n\n"
            f"Bilgisayarin kapali olsa bile YouTube otomatik yayinlayacak!",
            "🎉"
        )

        (WORK / "result.json").write_text(json.dumps({
            "status": "success", "video_url": vid_url,
            "title": icerik["baslik"], "publish": p["yayin_iso"]
        }, ensure_ascii=False))

    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:400]}", "❌")
        (WORK / "result.json").write_text(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
