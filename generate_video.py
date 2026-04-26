#!/usr/bin/env python3
"""
Video Bot v4
- Konuya göre otomatik arkaplan müziği (FreePD - CC0, telif yok)
- Derin belgesel sesi (pitch -15Hz, rate -5%)
- Her 10 saniyede görsel efekt (zoom pulse + crossfade)
- Gemini 2.5 Flash
- Paralel görsel indirme
"""

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

_img_lock  = threading.Lock()
_img_done  = 0
_img_total = 0

# ═══════════════════════════════════════════════════════════════════════════════
# MÜZİK KATEGORİ HARİTASI
# FreePD.com — CC0 (tamamen ücretsiz, telif hakkı yok, YouTube'da sorun çıkmaz)
# ═══════════════════════════════════════════════════════════════════════════════
GITHUB_RAW = "https://raw.githubusercontent.com/taklaciguvercinn/video-bot/main"

MUSIC_MAP = {
    # Savaş / Viking / Osmanlı / Roma
    "viking":      ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "savaş":       ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "osmanlı":     ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "selçuklu":    ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "roma":        ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "şövalye":     ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "orta çağ":    ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "savaşçı":     ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    # Antik / Mısır / Yunan / Sümer
    "mısır":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "antik":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "yunan":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "sümer":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "mezopotamya": ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "aztek":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "maya":        ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "firavun":     ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    # Uzay / Teknoloji / Yapay Zeka
    "uzay":        ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "yapay zeka":  ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "teknoloji":   ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "bilim":       ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "robot":       ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "evren":       ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "gelecek":     ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    # Doğa / Hayvanlar
    "doğa":        ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "hayvan":      ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "deniz":       ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "orman":       ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "okyanus":     ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    # Gizem / Korku / Mitoloji
    "gizem":       ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "korku":       ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "mitoloji":    ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "paranormal":  ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "komplo":      ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "gizemli":     ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    # Motivasyon / İlham / Ambient
    "motivasyon":  ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
    "başarı":      ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
    "liderlik":    ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
    "ilham":       ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
}
DEFAULT_MUSIC = ("cinematic", f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3")

def get_music_for_topic(topic: str) -> tuple:
    """Konuya göre müzik seç"""
    topic_lower = topic.lower()
    for keyword, music_info in MUSIC_MAP.items():
        if keyword in topic_lower:
            return music_info
    return DEFAULT_MUSIC

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════════
def tg(msg: str, emoji: str = ""):
    text = f"{emoji} {msg}".strip()
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass
    print(text)

def tg_photo(path: str, caption: str):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=30
            )
    except Exception as e:
        print(f"[TG FOTO] {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# KOMUT PARSE
# ═══════════════════════════════════════════════════════════════════════════════
def parse_command(cmd: str) -> dict:
    parts = [p.strip() for p in cmd.strip().split(",")]
    if len(parts) != 5:
        raise ValueError(f"Format: Konu,Dakika,Resim,GG.AA.YYYY,SS:DD\nAlınan: {cmd}")
    topic, dur, imgs, date_s, time_s = parts
    pub = datetime.strptime(f"{date_s} {time_s}", "%d.%m.%Y %H:%M")
    return {
        "topic":       topic,
        "duration":    int(dur),
        "img_count":   int(imgs),
        "publish_dt":  pub,
        "publish_iso": pub.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    }

# ═══════════════════════════════════════════════════════════════════════════════
# GEMİNİ API
# ═══════════════════════════════════════════════════════════════════════════════
def gemini(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 8192}
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                tg(f"Gemini rate limit, {wait}s bekleniyor...", "⏳")
                time.sleep(wait)
                continue
            raise Exception(f"Gemini {r.status_code}: {r.text[:300]}")
        except requests.Timeout:
            time.sleep(10)
    raise Exception("Gemini 3 denemede yanıt vermedi")

# ═══════════════════════════════════════════════════════════════════════════════
# ARAŞTIRMA + SENARYO + SEO
# ═══════════════════════════════════════════════════════════════════════════════
def research_and_script(topic: str, duration: int, img_count: int) -> dict:
    tg(f"<b>'{topic}'</b> araştırılıyor ve senaryo yazılıyor...", "📚")
    words = duration * 160  # 160 kelime/dakika → daha uzun video
    raw = gemini(f"""Sen profesyonel bir YouTube belgesel içerik uzmanısın.
'{topic}' konusunda {duration} dakikalık Türkçe belgesel tarzı video hazırla.

GÖREVLER:
1. Konuyu kapsamlı araştır, gerçek ve doğru bilgiler kullan
2. Tam {words} kelimelik akıcı, merak uyandıran Türkçe senaryo yaz
   - Giriş (dikkat çekici soru veya gerçek ile başla)
   - Gelişme (bölümlere ayrılmış, her bölüm bir görsel ile eşleşecek)
   - Sonuç (güçlü kapanış)
3. Tam {img_count} adet görsel için ayrı ayrı İngilizce sinematik prompt yaz
4. YouTube SEO optimizasyonu yap
5. Thumbnail tasarımı öner

SADECE şu JSON formatında yanıt ver, başka HİÇBİR şey yazma:
{{
  "seo_title": "Başlık (60 karakter max, emoji ile, merak uyandıran)",
  "seo_description": "Açıklama (500 karakter, #hashtag ile bitir)",
  "seo_tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12","tag13","tag14","tag15"],
  "script": "Tam senaryo buraya — {words} kelime olmalı...",
  "image_prompts": ["prompt 1 — cinematic, dramatic lighting, ultra detailed, 8k"],
  "thumbnail_text": "BÜYÜK HARF MAX 4 KELİME",
  "thumbnail_prompt": "Thumbnail için epik İngilizce görsel prompt, no text, dramatic",
  "thumbnail_bg_color": "#1a1a2e"
}}""")

    raw  = re.sub(r"```json\s*|```\s*", "", raw).strip()
    raw  = raw[raw.find("{"):raw.rfind("}")+1]
    data = json.loads(raw)

    if len(data.get("image_prompts", [])) < img_count:
        base = data["image_prompts"][-1] if data.get("image_prompts") else f"{topic} cinematic scene"
        while len(data["image_prompts"]) < img_count:
            data["image_prompts"].append(base + f" variation {len(data['image_prompts'])+1}")

    tg(
        f"✅ Senaryo hazır!\n"
        f"📺 <b>{data['seo_title']}</b>\n"
        f"📝 {len(data['script'].split())} kelime\n"
        f"🖼 {len(data['image_prompts'])} görsel promptu",
        ""
    )
    return data

# ═══════════════════════════════════════════════════════════════════════════════
# MÜZİK İNDİR
# ═══════════════════════════════════════════════════════════════════════════════
def download_music(topic: str) -> str:
    music_type, music_url = get_music_for_topic(topic)
    tg(f"Arkaplan müziği indiriliyor: <b>{music_type}</b>", "🎵")
    music_path = WORK / "background_music.mp3"

    for attempt in range(3):
        try:
            r = requests.get(music_url, timeout=30)
            if r.status_code == 200 and len(r.content) > 10000:
                music_path.write_bytes(r.content)
                tg("Müzik indirildi!", "✅")
                return str(music_path)
            time.sleep(5)
        except Exception as e:
            tg(f"Müzik indirme hatası: {e}", "⚠")
            time.sleep(5)

    tg("Müzik indirilemedi, müziksiz devam edilecek", "⚠")
    return ""

# ═══════════════════════════════════════════════════════════════════════════════
# SES MİKSİ (anlatıcı + arkaplan müziği)
# ═══════════════════════════════════════════════════════════════════════════════
def mix_audio(narration: str, music: str, total_duration: float) -> str:
    """Anlatıcı sesini müzikle karıştır — müzik %20 ses seviyesinde"""
    mixed_path = WORK / "mixed_audio.mp3"

    if not music or not os.path.exists(music):
        return narration

    tg("Ses ve müzik karıştırılıyor...", "🎚")

    # Müziği döngüye al ve anlatıcı sesiyle karıştır
    # amix: anlatıcı %100, müzik %20 (sesi bastırmaz)
    cmd = [
        "ffmpeg", "-y",
        "-i", narration,
        "-stream_loop", "-1", "-i", music,
        "-filter_complex",
        f"[1:a]volume=0.18,atrim=0:{total_duration+1}[music];"
        f"[0:a][music]amix=inputs=2:duration=first:weights=1 0.18[out]",
        "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_duration),
        str(mixed_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tg("Ses karıştırma başarısız, sadece anlatıcı sesiyle devam", "⚠")
        return narration

    tg("Ses karışımı hazır! (Anlatıcı %100 + Müzik %18)", "✅")
    return str(mixed_path)

# ═══════════════════════════════════════════════════════════════════════════════
# GÖRSEL ÜRET — PARALELLEŞTİRİLMİŞ
# ═══════════════════════════════════════════════════════════════════════════════
def _download_one_image(args) -> tuple:
    global _img_done
    i, prompt, total = args
    enc = quote(f"{prompt}, cinematic 4k ultra detailed professional photography")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={i*7+13}&nologo=true&model=flux"
    p   = WORK / f"img_{i+1:02d}.jpg"

    for attempt in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 8000:
                p.write_bytes(r.content)
                with _img_lock:
                    _img_done += 1
                    done = _img_done
                tg(f"Görsel {done}/{total} ✓", "🖼")
                return (i, str(p), True)
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(8)

    subprocess.run(["ffmpeg","-y","-f","lavfi",
        "-i","color=c=0x1a1a2e:size=1920x1080:rate=1",
        "-vframes","1", str(p)], capture_output=True)
    with _img_lock:
        _img_done += 1
    tg(f"Görsel {i+1} yedekle tamamlandı", "⚠")
    return (i, str(p), False)

def generate_images(prompts: list) -> list:
    global _img_done, _img_total
    _img_done  = 0
    _img_total = len(prompts)
    tg(f"<b>{_img_total} görsel paralel üretiliyor...</b>\n⏳ Tahmini: ~{max(5,_img_total//5)} dk", "🎨")
    args_list = [(i, p, _img_total) for i, p in enumerate(prompts)]
    results   = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_download_one_image, a): a[0] for a in args_list}
        for fut in as_completed(futures):
            idx, path, ok = fut.result()
            results[idx]  = path
    return [results[i] for i in range(len(prompts))]

# ═══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL
# ═══════════════════════════════════════════════════════════════════════════════
def generate_thumbnail(prompt: str, text: str, bg_color: str, topic: str) -> str:
    tg("Thumbnail üretiliyor...", "🖼")
    enc        = quote(f"{prompt}, youtube thumbnail, dramatic lighting, no text, vibrant colors")
    url        = f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=42&nologo=true&model=flux"
    base_path  = WORK / "thumb_base.jpg"
    final_path = WORK / "thumbnail.jpg"

    downloaded = False
    for _ in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                base_path.write_bytes(r.content)
                downloaded = True
                break
            time.sleep(8)
        except Exception:
            time.sleep(8)

    if not downloaded:
        subprocess.run(["ffmpeg","-y","-f","lavfi",
            "-i", f"color=c={bg_color.replace('#','0x')}:size=1280x720:rate=1",
            "-vframes","1", str(base_path)], capture_output=True)

    safe_text  = text.upper().replace("'","\\'").replace(":","\\:")
    safe_topic = topic.upper().replace("'","\\'").replace(":","\\:")
    fsize      = 88 if len(text) <= 12 else 64 if len(text) <= 20 else 48

    vf = (
        f"drawbox=x=0:y=ih*0.60:w=iw:h=ih*0.40:color=black@0.70:t=fill,"
        f"drawtext=text='{safe_text}':fontsize={fsize}:fontcolor=black@0.5"
        f":x=(w-text_w)/2+3:y=h*0.63+3:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{safe_text}':fontsize={fsize}:fontcolor=white"
        f":x=(w-text_w)/2:y=h*0.63:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{safe_topic}':fontsize=32:fontcolor=yellow@0.95"
        f":x=24:y=24:font=DejaVu Sans:style=Bold"
    )
    r = subprocess.run(
        ["ffmpeg","-y","-i",str(base_path),"-vf",vf,"-q:v","2",str(final_path)],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not final_path.exists():
        subprocess.run(["cp", str(base_path), str(final_path)])

    if final_path.exists():
        tg_photo(str(final_path), f"🖼 <b>Thumbnail:</b> {text.upper()}")
    tg("Thumbnail hazır!", "✅")
    return str(final_path)

# ═══════════════════════════════════════════════════════════════════════════════
# SES — DERİN BELGESEL SESİ
# ═══════════════════════════════════════════════════════════════════════════════
def generate_audio(script: str) -> tuple:
    """Derin belgesel sesi — EQ ile bas güçlendirilmiş"""
    tg("Derin belgesel sesi sentezleniyor...", "🎙")
    script_f  = WORK / "script.txt"
    raw_f     = WORK / "narration_raw.mp3"
    final_f   = WORK / "narration.mp3"
    script_f.write_text(script, encoding="utf-8")

    # edge-tts: parametreler ayrı ayrı string olmalı, boşluk olmamalı
    r = subprocess.run([
        "edge-tts",
        "--voice", "tr-TR-AhmetNeural",
        "--file",  str(script_f),
        "--write-media", str(raw_f),
        "--rate",   "-8%",
        "--pitch",  "-10Hz",
        "--volume", "+15%",
    ], capture_output=True, text=True)

    if r.returncode != 0 or not raw_f.exists():
        # Yedek: parametresiz dene
        tg("Ses parametreleri başarısız, sade sesle deneniyor...", "⚠")
        r2 = subprocess.run([
            "edge-tts",
            "--voice", "tr-TR-AhmetNeural",
            "--file",  str(script_f),
            "--write-media", str(raw_f),
        ], capture_output=True, text=True)
        if r2.returncode != 0 or not raw_f.exists():
            raise Exception(f"TTS hatası: {r2.stderr[-400:]}")

    # FFmpeg EQ: belgesel tonu — bas güçlendir, tiz azalt
    eq_cmd = [
        "ffmpeg", "-y", "-i", str(raw_f),
        "-af",
        (
            "equalizer=f=80:width_type=o:width=2:g=5,"
            "equalizer=f=180:width_type=o:width=2:g=3,"
            "equalizer=f=3000:width_type=o:width=2:g=-2,"
            "equalizer=f=8000:width_type=o:width=2:g=-4,"
            "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,"
            "volume=1.3"
        ),
        "-c:a", "mp3", "-b:a", "192k",
        str(final_f)
    ]
    eq_r = subprocess.run(eq_cmd, capture_output=True, text=True)
    if eq_r.returncode != 0 or not final_f.exists():
        subprocess.run(["cp", str(raw_f), str(final_f)])
        tg("EQ atlandı, ham ses kullanıldı", "⚠")

    probe = subprocess.run([
        "ffprobe","-v","quiet","-print_format","json",
        "-show_format", str(final_f)
    ], capture_output=True, text=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazır! Süre: <b>{dur/60:.1f} dakika</b> | Derin belgesel tonu ✓", "✅")
    return str(final_f), dur

# ═══════════════════════════════════════════════════════════════════════════════
# VİDEO MONTAJ — HER 10 SANİYEDE EFEKT
# ═══════════════════════════════════════════════════════════════════════════════
def create_video(images: list, audio: str, total_duration: float) -> str:
    tg(
        f"Video montajlanıyor...\n"
        f"🖼 {len(images)} görsel | Her 10s efekt\n"
        f"⏳ Tahmini: ~{len(images)//3+8} dakika",
        "🎬"
    )
    out   = WORK / "final_video.mp4"
    lst_f = WORK / "imglist.txt"

    each   = total_duration / len(images)
    fps    = 25
    frames = max(int(each * fps), 50)

    tg(f"Toplam: {total_duration/60:.1f} dk | Görsel başına: {each:.1f}s", "⚙")

    with open(lst_f, "w") as f:
        for p in images:
            f.write(f"file '{os.path.abspath(p)}'\n")
            f.write(f"duration {each:.3f}\n")
        f.write(f"file '{os.path.abspath(images[-1])}'\n")

    # Her görsel için efekt:
    # - Zoom pulse: her 10 saniyede hafif zoom in/out
    # - Fade in/out geçişleri
    # - Çift-tek yön değişimi
    filter_parts = []
    maps = []

    for i in range(len(images)):
        # Zoom yönü: çift = sol→sağ, tek = sağ→sol
        if i % 2 == 0:
            zoom_expr = "if(lte(on,1),1.05,zoom-0.0004)"
            x_expr    = "iw/2-(iw/zoom/2)"
            y_expr    = "ih/2-(ih/zoom/2)"
        else:
            zoom_expr = "if(lte(on,1),1.0,min(zoom+0.0004,1.08))"
            x_expr    = "iw/2-(iw/zoom/2)"
            y_expr    = "ih/2-(ih/zoom/2)+sin(on/50)*20"

        # Her 10 saniyede bir "pulse" efekti için brightness dalgası
        pulse = f"eq=brightness='0.02*sin(2*PI*t/10)':contrast=1.05"

        filter_parts.append(
            f"[{i}:v]scale=3840:-1,"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={frames}:s=1920x1080:fps={fps},"
            f"{pulse},"
            f"fade=t=in:st=0:d=0.8,"
            f"fade=t=out:st={max(0,each-0.8):.2f}:d=0.8"
            f"[v{i}]"
        )
        maps.append(f"[v{i}]")

    filter_parts.append(f"{''.join(maps)}concat=n={len(images)}:v=1:a=0[outv]")
    filt = ";".join(filter_parts)

    in_args = []
    for p in images:
        in_args += ["-loop","1","-t",str(each+2),"-i", p]

    cmd = [
        "ffmpeg","-y",
        *in_args, "-i", audio,
        "-filter_complex", filt,
        "-map","[outv]",
        "-map", f"{len(images)}:a",
        "-c:v","libx264","-preset","fast","-crf","22",
        "-c:a","aac","-b:a","192k",
        "-shortest","-movflags","+faststart",
        str(out)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        tg("Efektli versiyon başarısız → basit versiyon...", "⚠")
        cmd2 = [
            "ffmpeg","-y",
            "-f","concat","-safe","0","-i",str(lst_f),
            "-i", audio,
            "-vf","scale=1920:1080:force_original_aspect_ratio=decrease,"
                 "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:v","libx264","-preset","fast","-crf","22",
            "-c:a","aac","-b:a","192k",
            "-shortest","-movflags","+faststart",
            str(out)
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True)
        if r2.returncode != 0:
            raise Exception(f"FFmpeg: {r2.stderr[-600:]}")

    mb = os.path.getsize(out) / 1024 / 1024
    tg(f"Video hazır! Boyut: <b>{mb:.0f} MB</b>", "✅")
    return str(out)

# ═══════════════════════════════════════════════════════════════════════════════
# YOUTUBE
# ═══════════════════════════════════════════════════════════════════════════════
def yt_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type":    "refresh_token"
    }, timeout=30)
    if r.status_code != 200:
        raise Exception(f"YT token: {r.text}")
    return r.json()["access_token"]

def upload_youtube(video: str, thumb: str,
                   title: str, desc: str, tags: list, pub_iso: str):
    tg("YouTube'a yükleniyor...", "📤")
    token = yt_token()
    meta  = {
        "snippet": {
            "title":       title[:100],
            "description": desc[:5000],
            "tags":        tags[:15],
            "categoryId":  "27"
        },
        "status": {
            "privacyStatus":           "private",
            "publishAt":               pub_iso,
            "selfDeclaredMadeForKids": False
        }
    }
    fsize = os.path.getsize(video)
    init  = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization":           f"Bearer {token}",
            "Content-Type":            "application/json",
            "X-Upload-Content-Type":   "video/mp4",
            "X-Upload-Content-Length": str(fsize)
        },
        json=meta, timeout=30
    )
    if init.status_code != 200:
        raise Exception(f"YT init: {init.text[:300]}")

    upload_url = init.headers["Location"]
    tg(f"Video yükleniyor ({fsize/1024/1024:.0f} MB)...", "⏳")
    with open(video, "rb") as f:
        up = requests.put(
            upload_url,
            headers={"Content-Type":"video/mp4"},
            data=f, timeout=900
        )
    if up.status_code not in [200, 201]:
        raise Exception(f"YT yükleme: {up.text[:300]}")

    vid_id  = up.json()["id"]
    vid_url = f"https://youtu.be/{vid_id}"
    tg(f"Video yüklendi!\n🔗 {vid_url}", "✅")

    # Thumbnail
    tg("Thumbnail yükleniyor...", "🖼")
    try:
        with open(thumb, "rb") as tf:
            tr = requests.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},
                data=tf, timeout=60
            )
        tg("Thumbnail yüklendi!" if tr.status_code in [200,201] else f"Thumbnail atlandı ({tr.status_code})",
           "✅" if tr.status_code in [200,201] else "⚠")
    except Exception as e:
        tg(f"Thumbnail hatası: {e}", "⚠")

    return vid_url, vid_id

# ═══════════════════════════════════════════════════════════════════════════════
# ANA AKIŞ
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if not cmd:
        print("Kullanım: python generate_video.py 'Konu,Dakika,Resim,GG.AA.YYYY,SS:DD'")
        sys.exit(1)

    try:
        p = parse_command(cmd)
    except Exception as e:
        tg(str(e), "❌"); sys.exit(1)

    music_type, _ = get_music_for_topic(p["topic"])
    tg(
        f"<b>🎬 Video Bot v4 Başladı!</b>\n\n"
        f"📌 Konu  : <b>{p['topic']}</b>\n"
        f"⏱ Süre  : {p['duration']} dakika\n"
        f"🖼 Görsel: {p['img_count']} adet\n"
        f"📅 Yayın : {p['publish_dt'].strftime('%d.%m.%Y %H:%M')}\n"
        f"🎵 Müzik : {music_type} (CC0 ücretsiz)\n"
        f"🎙 Ses   : Derin belgesel tonu\n"
        f"✨ Efekt : Her 10s zoom pulse",
        "🚀"
    )

    try:
        # 1. Senaryo + SEO
        content = research_and_script(p["topic"], p["duration"], p["img_count"])
        (WORK/"metadata.json").write_text(json.dumps(content, ensure_ascii=False, indent=2))

        # 2. Müzik indir (görseller indirilirken paralel)
        music_path = download_music(p["topic"])

        # 3. Görseller
        images = generate_images(content["image_prompts"])

        # 4. Thumbnail
        thumb = generate_thumbnail(
            content["thumbnail_prompt"],
            content["thumbnail_text"],
            content.get("thumbnail_bg_color","#1a1a2e"),
            p["topic"]
        )

        # 5. Ses
        audio, duration = generate_audio(content["script"])

        # 6. Ses + Müzik karıştır
        mixed_audio = mix_audio(audio, music_path, duration)

        # 7. Video
        video = create_video(images, mixed_audio, duration)

        # 8. YouTube
        vid_url, vid_id = upload_youtube(
            video, thumb,
            content["seo_title"],
            content["seo_description"],
            content["seo_tags"],
            p["publish_iso"]
        )

        pub_str = p["publish_dt"].strftime("%d.%m.%Y saat %H:%M")
        tg(
            f"<b>🎉 TAMAMLANDI!</b>\n\n"
            f"📺 <b>{content['seo_title']}</b>\n\n"
            f"🔗 {vid_url}\n\n"
            f"📅 Yayın: <b>{pub_str}</b>\n\n"
            f"🎵 Müzik: {music_type}\n"
            f"🏷 Etiketler: {', '.join(content['seo_tags'][:5])}...\n\n"
            f"✅ Bilgisayarın kapalı olsa bile YouTube otomatik yayınlayacak!",
            ""
        )

        (WORK/"result.json").write_text(json.dumps({
            "status":    "success",
            "video_url": vid_url,
            "video_id":  vid_id,
            "title":     content["seo_title"],
            "publish":   p["publish_iso"]
        }, ensure_ascii=False, indent=2))

    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:400]}", "❌")
        (WORK/"result.json").write_text(json.dumps({"status":"error","error":str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
