#!/usr/bin/env python3
"""
Video Bot v3
- Gemini API (ücretsiz, senaryo + SEO)
- Paralel görsel indirme (50 resim ~8 dk)
- 2 GitHub hesabı desteği (dönüşümlü)
- Telegram anlık bildirim
- AI Thumbnail + SEO
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

# ─── SAYAÇLAR (thread-safe) ───────────────────────────────────────────────────
_img_lock      = threading.Lock()
_img_done      = 0
_img_total     = 0

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
    except Exception as e:
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
# GEMİNİ API  (ücretsiz — 1500 istek/gün, 1M token/dk)
# ═══════════════════════════════════════════════════════════════════════════════
def gemini(prompt: str) -> str:
    """Gemini 1.5 Flash ile metin üret — tamamen ücretsiz"""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash-preview-04-17:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.8,
            "maxOutputTokens": 8192,
        }
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            # 429 = rate limit → bekle
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

    words    = duration * 130   # ~130 kelime/dakika
    # 50 resim için Pollinations'ın aşırı yüklenmemesi adına
    # resim promptlarını 5'lik gruplara böleceğiz, ama hepsini burada üretelim
    raw = gemini(f"""Sen profesyonel bir YouTube içerik uzmanısın.
'{topic}' konusunda {duration} dakikalık Türkçe belgesel tarzı video hazırla.

GÖREVLER:
1. Konuyu kapsamlı araştır, gerçek ve doğru bilgiler kullan
2. Tam {words} kelimelik akıcı, merak uyandıran Türkçe senaryo yaz
   - Giriş (dikkat çekici soru veya gerçek ile başla)
   - Gelişme (bölümlere ayrılmış, her bölüm bir görsel ile eşleşecek)
   - Sonuç (güçlü kapanış)
3. Tam {img_count} adet görsel için ayrı ayrı İngilizce sinematik prompt yaz
   - Her prompt o bölümün içeriğiyle eşleşmeli
   - "cinematic, dramatic lighting, ultra detailed, 8k" ile bitirmeli
4. YouTube SEO optimizasyonu yap
5. Thumbnail tasarımı öner

SADECE şu JSON formatında yanıt ver, başka HİÇBİR şey yazma:
{{
  "seo_title": "Başlık (60 karakter max, emoji ile, merak uyandıran)",
  "seo_description": "Açıklama (ilk 2 satır en kritik — anahtar kelime yoğun, 500 karakter, #hashtag ile bitir)",
  "seo_tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12","tag13","tag14","tag15"],
  "script": "Tam senaryo buraya — {words} kelime olmalı...",
  "image_prompts": [
    "prompt 1 — cinematic, dramatic lighting, ultra detailed, 8k",
    "prompt 2 — cinematic, dramatic lighting, ultra detailed, 8k"
  ],
  "thumbnail_text": "BÜYÜK HARF MAX 4 KELİME",
  "thumbnail_prompt": "Thumbnail için epik İngilizce görsel prompt, no text, dramatic",
  "thumbnail_bg_color": "#1a1a2e"
}}""")

    raw  = re.sub(r"```json\s*|```\s*", "", raw).strip()
    # Bazen Gemini ekstra whitespace bırakır
    raw  = raw[raw.find("{"):raw.rfind("}")+1]
    data = json.loads(raw)

    # Güvenli kontrol
    if len(data.get("image_prompts", [])) < img_count:
        # Eksik promptları tamamla
        base = data["image_prompts"][-1] if data.get("image_prompts") else f"{topic} cinematic scene"
        while len(data["image_prompts"]) < img_count:
            data["image_prompts"].append(base + f" variation {len(data['image_prompts'])+1}")

    tg(
        f"✅ Senaryo hazır!\n"
        f"📺 <b>{data['seo_title']}</b>\n"
        f"📝 {len(data['script'].split())} kelime\n"
        f"🖼 {len(data['image_prompts'])} görsel promptu\n"
        f"🏷 {len(data['seo_tags'])} SEO etiketi",
        ""
    )
    return data

# ═══════════════════════════════════════════════════════════════════════════════
# GÖRSEL ÜRET — PARALELLEŞTİRİLMİŞ
# ═══════════════════════════════════════════════════════════════════════════════
def _download_one_image(args) -> tuple:
    """Tek bir görseli indir — thread içinde çalışır"""
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

    # Yedek: koyu renkli placeholder
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

    tg(
        f"<b>{_img_total} görsel paralel üretiliyor...</b>\n"
        f"⏳ Tahmini süre: ~{max(5, _img_total//5)} dakika",
        "🎨"
    )

    # Pollinations aşırı yük almadan: max 5 eş zamanlı istek
    MAX_WORKERS = 5
    args_list   = [(i, p, _img_total) for i, p in enumerate(prompts)]
    results     = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_download_one_image, a): a[0] for a in args_list}
        for fut in as_completed(futures):
            idx, path, ok = fut.result()
            results[idx]  = path

    # Sıraya göre döndür
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
        tg_photo(str(final_path), f"🖼 <b>Thumbnail önizleme:</b> {text.upper()}")
    tg("Thumbnail hazır!", "✅")
    return str(final_path)

# ═══════════════════════════════════════════════════════════════════════════════
# SES
# ═══════════════════════════════════════════════════════════════════════════════
def generate_audio(script: str) -> str:
    tg("Türkçe ses sentezleniyor...", "🎙")
    script_f = WORK / "script.txt"
    audio_f  = WORK / "narration.mp3"
    script_f.write_text(script, encoding="utf-8")

    r = subprocess.run([
        "edge-tts",
        "--voice", "tr-TR-AhmetNeural",
        "--file",  str(script_f),
        "--write-media", str(audio_f),
        "--rate",  "+5%"
    ], capture_output=True, text=True)

    if r.returncode != 0 or not audio_f.exists():
        raise Exception(f"TTS hatası: {r.stderr[-400:]}")

    probe = subprocess.run([
        "ffprobe","-v","quiet","-print_format","json",
        "-show_format", str(audio_f)
    ], capture_output=True, text=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazır! Gerçek süre: <b>{dur/60:.1f} dakika</b>", "✅")
    return str(audio_f)

# ═══════════════════════════════════════════════════════════════════════════════
# VİDEO MONTAJ
# ═══════════════════════════════════════════════════════════════════════════════
def create_video(images: list, audio: str) -> str:
    tg(
        f"Video montajlanıyor...\n"
        f"🖼 {len(images)} görsel | Ken Burns efekti\n"
        f"⏳ Tahmini süre: ~{len(images)//3 + 5} dakika",
        "🎬"
    )
    out   = WORK / "final_video.mp4"
    lst_f = WORK / "imglist.txt"

    probe = subprocess.run([
        "ffprobe","-v","quiet","-print_format","json",
        "-show_format", audio
    ], capture_output=True, text=True)
    total = float(json.loads(probe.stdout)["format"]["duration"])
    each  = total / len(images)
    fps   = 25
    frames = max(int(each * fps), 50)

    tg(f"Toplam: {total/60:.1f} dk | Görsel başına: {each:.1f}s", "⚙")

    # concat listesi
    with open(lst_f, "w") as f:
        for p in images:
            f.write(f"file '{os.path.abspath(p)}'\n")
            f.write(f"duration {each:.3f}\n")
        f.write(f"file '{os.path.abspath(images[-1])}'\n")

    # 50 görsel için FFmpeg filter_complex çok büyür → concat demuxer kullan
    # Ken Burns: zoompan filtresi her görsel için
    filter_parts = []
    maps         = []
    for i in range(len(images)):
        # Çift-tek görseller farklı yönde zoom
        if i % 2 == 0:
            zoom_expr = "min(zoom+0.0006,1.06)"
            x_expr    = "iw/2-(iw/zoom/2)"
            y_expr    = "ih/2-(ih/zoom/2)"
        else:
            zoom_expr = "min(zoom+0.0006,1.06)"
            x_expr    = "iw/2-(iw/zoom/2)+20*on/d"
            y_expr    = "ih/2-(ih/zoom/2)"

        filter_parts.append(
            f"[{i}:v]scale=3840:-1,"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={frames}:s=1920x1080:fps={fps},"
            f"fade=t=in:st=0:d=0.5,"
            f"fade=t=out:st={max(0,each-0.5):.2f}:d=0.5"
            f"[v{i}]"
        )
        maps.append(f"[v{i}]")

    filter_parts.append(f"{''.join(maps)}concat=n={len(images)}:v=1:a=0[outv]")
    filt = ";".join(filter_parts)

    in_args = []
    for p in images:
        in_args += ["-loop","1","-t",str(each + 2),"-i", p]

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
        tg("Ken Burns başarısız → basit versiyon...", "⚠")
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

    meta = {
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

    tg(
        f"<b>🎬 Video Bot v3 Başladı!</b>\n\n"
        f"📌 Konu  : <b>{p['topic']}</b>\n"
        f"⏱ Süre  : {p['duration']} dakika\n"
        f"🖼 Görsel: {p['img_count']} adet\n"
        f"📅 Yayın : {p['publish_dt'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"⚙️ Motor  : Gemini 1.5 Flash (ücretsiz)\n"
        f"🎨 Görsel : Pollinations.ai (ücretsiz, paralel)",
        "🚀"
    )

    try:
        # 1. Senaryo + SEO
        content = research_and_script(p["topic"], p["duration"], p["img_count"])
        (WORK/"metadata.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2))

        # 2. Görseller (paralel)
        images = generate_images(content["image_prompts"])

        # 3. Thumbnail
        thumb = generate_thumbnail(
            content["thumbnail_prompt"],
            content["thumbnail_text"],
            content.get("thumbnail_bg_color","#1a1a2e"),
            p["topic"]
        )

        # 4. Ses
        audio = generate_audio(content["script"])

        # 5. Video
        video = create_video(images, audio)

        # 6. YouTube
        vid_url, vid_id = upload_youtube(
            video, thumb,
            content["seo_title"],
            content["seo_description"],
            content["seo_tags"],
            p["publish_iso"]
        )

        # 7. Final bildirim
        pub_str = p["publish_dt"].strftime("%d.%m.%Y saat %H:%M")
        tg(
            f"<b>🎉 TAMAMLANDI!</b>\n\n"
            f"📺 <b>{content['seo_title']}</b>\n\n"
            f"🔗 {vid_url}\n\n"
            f"📅 Yayın: <b>{pub_str}</b>\n\n"
            f"🏷 Etiketler: {', '.join(content['seo_tags'][:6])}...\n\n"
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
