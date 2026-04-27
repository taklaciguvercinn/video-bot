#!/usr/bin/env python3
"""Video Bot v5 - Tum problemler cozuldu"""

import sys, os, json, time, requests, subprocess, re
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
TELEGRAM_BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID      = os.environ["TELEGRAM_CHAT_ID"]

WORK = Path("./output")
WORK.mkdir(exist_ok=True)
_img_lock = threading.Lock()
_img_done = 0

GITHUB_RAW = "https://raw.githubusercontent.com/taklaciguvercinn/video-bot/main"
MUSIC_MAP = {
    "viking":      ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "savas":       ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "osmanli":     ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "selcuklu":    ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "roma":        ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "ortacag":     ("epic_battle", f"{GITHUB_RAW}/nastelbom-epic-501714.mp3"),
    "misir":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "antik":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "yunan":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "sumer":       ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "mezopotamya": ("ancient",     f"{GITHUB_RAW}/onetent-ancient-181070.mp3"),
    "uzay":        ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "yapay zeka":  ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "teknoloji":   ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "bilim":       ("space",       f"{GITHUB_RAW}/the_mountain-space-438391.mp3"),
    "doga":        ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "hayvan":      ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "deniz":       ("nature",      f"{GITHUB_RAW}/sonican-background-music-new-age-nature-465069.mp3"),
    "gizem":       ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "korku":       ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "mitoloji":    ("mystery",     f"{GITHUB_RAW}/studiokolomna-risk-136788.mp3"),
    "motivasyon":  ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
    "basari":      ("inspiring",   f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3"),
}
DEFAULT_MUSIC = ("cinematic", f"{GITHUB_RAW}/atlasaudio-ambient-soundscapes-511893.mp3")

def get_music(topic):
    t = topic.lower()
    # Turkce karakter normalize
    t = t.replace("ş","s").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ü","u").replace("ç","c")
    for k, v in MUSIC_MAP.items():
        if k in t:
            return v
    return DEFAULT_MUSIC

def tg(msg, emoji=""):
    text = f"{emoji} {msg}".strip()
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":"HTML"}, timeout=10)
    except: pass
    print(text)

def tg_photo(path, caption):
    try:
        with open(path,"rb") as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id":TELEGRAM_CHAT_ID,"caption":caption,"parse_mode":"HTML"},
                files={"photo":f}, timeout=30)
    except: pass

def parse_command(cmd):
    parts = [p.strip() for p in cmd.strip().split(",")]
    if len(parts) != 5:
        raise ValueError(f"Format hatali: {cmd}")
    topic, dur, imgs, date_s, time_s = parts
    pub = datetime.strptime(f"{date_s} {time_s}", "%d.%m.%Y %H:%M")
    return {"topic":topic,"duration":int(dur),"img_count":int(imgs),
            "publish_dt":pub,"publish_iso":pub.strftime("%Y-%m-%dT%H:%M:%S+00:00")}

def gemini_call(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = {"contents":[{"parts":[{"text":prompt}]}],
            "generationConfig":{"temperature":0.7,"maxOutputTokens":8192}}
    for attempt in range(4):
        try:
            r = requests.post(url, json=body, timeout=180)
            if r.status_code == 200:
                cands = r.json().get("candidates",[])
                if cands:
                    text = cands[0].get("content",{}).get("parts",[{}])[0].get("text","").strip()
                    if text:
                        return text
                raise Exception("Bos yanit")
            if r.status_code in [429,503]:
                time.sleep(40*(attempt+1))
                continue
            raise Exception(f"HTTP {r.status_code}")
        except requests.Timeout:
            time.sleep(15)
        except Exception as e:
            if "Bos" in str(e):
                time.sleep(20); continue
            raise
    raise Exception("Gemini yanit vermedi")

def parse_json_safe(raw):
    raw = re.sub(r"```json\s*|```\s*","",raw).strip()
    # Direkt parse
    try: return json.loads(raw)
    except: pass
    # { } arasini al
    s = raw.find("{"); e = raw.rfind("}")+1
    if s!=-1 and e>s:
        seg = raw[s:e]
        try: return json.loads(seg)
        except: pass
        # Apostrof duzelt
        try:
            fixed = re.sub(r"(?<!\\)'","",seg)
            return json.loads(fixed)
        except: pass
    # Alan alan cikart
    result = {}
    for key,pat in [
        ("seo_title",       r'"seo_title"\s*:\s*"([^"]{1,100})"'),
        ("seo_description", r'"seo_description"\s*:\s*"([^"]{1,600})"'),
        ("thumbnail_text",  r'"thumbnail_text"\s*:\s*"([^"]{1,50})"'),
        ("thumbnail_prompt",r'"thumbnail_prompt"\s*:\s*"([^"]{1,300})"'),
        ("thumbnail_bg_color",r'"thumbnail_bg_color"\s*:\s*"([^"]{1,20})"'),
    ]:
        m = re.search(pat, raw)
        if m: result[key] = m.group(1)
    # Script - uzun alan
    sm = re.search(r'"script"\s*:\s*"([\s\S]{100,}?)"(?=\s*,\s*"(?:image|thumb|seo_))',raw)
    if sm: result["script"] = sm.group(1)
    # Tags
    tm = re.search(r'"seo_tags"\s*:\s*\[(.*?)\]',raw,re.DOTALL)
    if tm: result["seo_tags"] = re.findall(r'"([^"]+)"',tm.group(1))
    # Image prompts
    im = re.search(r'"image_prompts"\s*:\s*\[(.*?)\]',raw,re.DOTALL)
    if im: result["image_prompts"] = re.findall(r'"([^"]+)"',im.group(1))
    if "seo_title" in result and ("script" in result or "image_prompts" in result):
        return result
    raise Exception(f"JSON parse basarisiz: {raw[:100]}")

def research_and_script(topic, duration, img_count):
    tg(f"'{topic}' arastiriliyor...", "📚")
    words = duration * 160
    prompt = f"""YouTube belgesel senaristiyim. '{topic}' konusunda {duration} dakikalik video hazirla.

KURAL 1: Senaryo SADECE seslendirilecek duz metin. Hicbir gorsel notu, muzik ismi, teknik not olmayacak.
KURAL 2: JSON string degerlerinde apostrof (') kullanma. Yerine baska kelime sec.
KURAL 3: Emojileri SADECE seo_title alaninda kullan.
KURAL 4: image_prompts SADECE Ingilizce sinematik prompt.

JSON formatinda yanit ver:
{{
  "seo_title": "baslik max 60 karakter emoji ile",
  "seo_description": "aciklama 500 karakter hashtag ile",
  "seo_tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "script": "SADECE seslendirilecek Turkce metin {words} kelime. Apostrof kullanma.",
  "image_prompts": ["english cinematic prompt 1 dramatic 8k","english cinematic prompt 2 dramatic 8k"],
  "thumbnail_text": "MAX 4 KELIME",
  "thumbnail_prompt": "epic scene english no text dramatic lighting",
  "thumbnail_bg_color": "#1a1a2e"
}}"""

    for attempt in range(4):
        try:
            raw  = gemini_call(prompt)
            data = parse_json_safe(raw)
            for f in ["seo_title","image_prompts"]:
                if f not in data or not data[f]:
                    raise Exception(f"Eksik: {f}")
            # Script yoksa bos senaryo olustur
            if "script" not in data or not data["script"]:
                tg("Script alani bos, yeniden deneniyor...", "⚠")
                raise Exception("Script bos")
            # Temizle
            sc = data["script"]
            sc = re.sub(r'\[.*?\]','',sc,flags=re.DOTALL)
            sc = re.sub(r'Gorsel\s*\d+\s*:','',sc)
            sc = re.sub(r'Resim\s*\d+\s*:','',sc)
            sc = re.sub(r'\n{3,}','\n\n',sc)
            data["script"] = sc.strip()
            # image_prompts tamamla
            while len(data.get("image_prompts",[])) < img_count:
                data["image_prompts"].append(f"{topic} dramatic cinematic scene {len(data['image_prompts'])+1}")
            data.setdefault("thumbnail_text", topic.upper()[:20])
            data.setdefault("thumbnail_prompt", f"{topic} epic dramatic cinematic")
            data.setdefault("thumbnail_bg_color","#1a1a2e")
            data.setdefault("seo_tags",[topic,"belgesel","tarih"])
            data.setdefault("seo_description",f"{topic} hakkinda belgesel. #belgesel #tarih")
            tg(f"Senaryo hazir!\n<b>{data['seo_title']}</b>\n{len(data['script'].split())} kelime","✅")
            return data
        except Exception as e:
            tg(f"Senaryo hatasi ({attempt+1}/4): {str(e)[:100]}","⚠")
            time.sleep(20)
    raise Exception("Senaryo uretilemedi")

def download_music(topic):
    mtype, murl = get_music(topic)
    tg(f"Muzik indiriliyor: {mtype}","🎵")
    mpath = WORK/"background_music.mp3"
    headers = {"User-Agent":"Mozilla/5.0","Accept":"audio/mpeg,*/*"}
    for attempt in range(4):
        try:
            r = requests.get(murl, headers=headers, timeout=60, stream=True)
            if r.status_code == 200:
                data = b"".join(r.iter_content(8192))
                if len(data) > 5000:
                    mpath.write_bytes(data)
                    tg(f"Muzik indirildi! ({len(data)//1024} KB)","✅")
                    return str(mpath)
            tg(f"Muzik HTTP {r.status_code} ({attempt+1}/4)","⚠")
            time.sleep(8)
        except Exception as e:
            tg(f"Muzik hatasi ({attempt+1}/4): {str(e)[:60]}","⚠")
            time.sleep(8)
    tg("Muzik indirilemedi, muziksiz devam","⚠")
    return ""

def mix_audio(narration, music, duration):
    if not music or not os.path.exists(music):
        return narration
    mixed = WORK/"mixed_audio.mp3"
    tg("Ses ve muzik karistiriliyor...","🎚")
    cmd = ["ffmpeg","-y","-i",narration,"-stream_loop","-1","-i",music,
           "-filter_complex",
           f"[1:a]volume=0.18,atrim=0:{duration+1}[mus];[0:a][mus]amix=inputs=2:duration=first:weights=1 0.18[out]",
           "-map","[out]","-c:a","aac","-b:a","192k","-t",str(duration),str(mixed)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and mixed.exists():
        tg("Ses karisimi hazir! (Anlatici %100 + Muzik %18)","✅")
        return str(mixed)
    tg("Ses karistirma basarisiz, sadece anlatici","⚠")
    return narration

def _dl_image(args):
    global _img_done
    i, prompt, total = args
    enc = quote(f"{prompt}, cinematic 4k ultra detailed")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={i*7+13}&nologo=true&model=flux"
    p   = WORK/f"img_{i+1:02d}.jpg"
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code==200 and len(r.content)>8000:
                p.write_bytes(r.content)
                with _img_lock:
                    _img_done += 1
                    done = _img_done
                tg(f"Gorsel {done}/{total}","🖼")
                return (i,str(p),True)
            time.sleep(5*(attempt+1))
        except: time.sleep(8)
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","color=c=0x1a1a2e:size=1920x1080:rate=1","-vframes","1",str(p)],capture_output=True)
    with _img_lock: _img_done+=1
    tg(f"Gorsel {i+1} yedek","⚠")
    return (i,str(p),False)

def generate_images(prompts):
    global _img_done
    _img_done = 0
    tg(f"{len(prompts)} gorsel uretiliyor... (~{max(5,len(prompts)//5)} dk)","🎨")
    results={}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs={ex.submit(_dl_image,(i,p,len(prompts))):i for i,p in enumerate(prompts)}
        for f in as_completed(futs):
            idx,path,ok=f.result(); results[idx]=path
    return [results[i] for i in range(len(prompts))]

def generate_thumbnail(prompt, text, bg_color, topic):
    tg("Thumbnail uretiliyor...","🖼")
    enc = quote(f"{prompt}, youtube thumbnail, no text, dramatic lighting")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=42&nologo=true&model=flux"
    base=WORK/"thumb_base.jpg"; final=WORK/"thumbnail.jpg"
    for _ in range(4):
        try:
            r=requests.get(url,timeout=120)
            if r.status_code==200 and len(r.content)>5000:
                base.write_bytes(r.content); break
            time.sleep(8)
        except: time.sleep(8)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={bg_color.replace('#','0x')}:size=1280x720:rate=1","-vframes","1",str(base)],capture_output=True)
    st=text.upper().replace("'","\\'").replace(":","\\:")
    sk=topic.upper()[:20].replace("'","\\'").replace(":","\\:")
    fs=88 if len(text)<=12 else 64 if len(text)<=20 else 48
    vf=(f"drawbox=x=0:y=ih*0.60:w=iw:h=ih*0.40:color=black@0.70:t=fill,"
        f"drawtext=text='{st}':fontsize={fs}:fontcolor=black@0.5:x=(w-text_w)/2+3:y=h*0.63+3:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{st}':fontsize={fs}:fontcolor=white:x=(w-text_w)/2:y=h*0.63:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{sk}':fontsize=32:fontcolor=yellow@0.95:x=24:y=24:font=DejaVu Sans:style=Bold")
    r=subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",vf,"-q:v","2",str(final)],capture_output=True,text=True)
    if r.returncode!=0 or not final.exists():
        subprocess.run(["cp",str(base),str(final)])
    if final.exists(): tg_photo(str(final),f"Thumbnail: {text.upper()}")
    tg("Thumbnail hazir!","✅")
    return str(final)

def generate_audio(script):
    tg("Derin belgesel sesi sentezleniyor...","🎙")
    sf=WORK/"script.txt"; rf=WORK/"narration_raw.mp3"; ff=WORK/"narration.mp3"
    sf.write_text(script,encoding="utf-8")
    r=subprocess.run(["edge-tts","--voice","tr-TR-AhmetNeural","--file",str(sf),
        "--write-media",str(rf),"--rate","-8%","--pitch","-10Hz","--volume","+15%"],
        capture_output=True,text=True)
    if r.returncode!=0 or not rf.exists():
        tg("Ses parametreleri hatali, sade sesle deneniyor...","⚠")
        r2=subprocess.run(["edge-tts","--voice","tr-TR-AhmetNeural","--file",str(sf),"--write-media",str(rf)],capture_output=True,text=True)
        if r2.returncode!=0 or not rf.exists():
            raise Exception(f"TTS hatasi: {r2.stderr[-200:]}")
    # EQ - derin belgesel tonu
    eq=subprocess.run(["ffmpeg","-y","-i",str(rf),"-af",
        "equalizer=f=80:width_type=o:width=2:g=5,equalizer=f=180:width_type=o:width=2:g=3,"
        "equalizer=f=3000:width_type=o:width=2:g=-2,equalizer=f=8000:width_type=o:width=2:g=-4,"
        "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,volume=1.3",
        "-c:a","mp3","-b:a","192k",str(ff)],capture_output=True,text=True)
    if eq.returncode!=0 or not ff.exists():
        subprocess.run(["cp",str(rf),str(ff)])
    probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",str(ff)],capture_output=True,text=True)
    dur=float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{dur/60:.1f} dakika</b>","✅")
    return str(ff),dur

def create_video(images, audio, total_duration):
    tg(f"Video montajlaniyor...\n{len(images)} gorsel | Zoom+Fade efektleri\nTahmini: ~{len(images)//2+5} dk","🎬")
    out=WORK/"final_video.mp4"; lst=WORK/"imglist.txt"
    each=total_duration/len(images); fps=25
    tg(f"Toplam: {total_duration/60:.1f} dk | Gorsel basina: {each:.1f}s","⚙")
    processed=[]
    for i,img in enumerate(images):
        proc=WORK/f"seg_{i:02d}.mp4"
        d=i%4
        if d==0:   z,x,y="min(zoom+0.0007,1.08)","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        elif d==1: z,x,y="min(zoom+0.0007,1.08)","iw/2-(iw/zoom/2)+on*0.5","ih/2-(ih/zoom/2)"
        elif d==2: z,x,y="if(lte(on,1),1.08,max(zoom-0.0007,1.0))","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        else:      z,x,y="min(zoom+0.0005,1.06)","iw/2-(iw/zoom/2)-on*0.3","ih/4-(ih/zoom/4)"
        fo=max(0,each-0.7); fr=max(int(each*fps),30)
        cmd=["ffmpeg","-y","-loop","1","-t",str(each+1),"-i",img,
             "-vf",f"scale=3840:-2,zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s=1920x1080:fps={fps},"
                   f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
             "-t",str(each),"-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(proc)]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
        if r.returncode==0 and proc.exists() and proc.stat().st_size>1000:
            processed.append(str(proc))
            tg(f"Segment {i+1}/{len(images)} zoom ok","🎬")
        else:
            cmd2=["ffmpeg","-y","-loop","1","-t",str(each),"-i",img,
                  "-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1",
                  "-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(proc)]
            r2=subprocess.run(cmd2,capture_output=True,text=True,timeout=120)
            if r2.returncode==0: processed.append(str(proc)); tg(f"Segment {i+1} yedek ok","⚠")
    if not processed: raise Exception("Hicbir segment olusturulamadi!")
    with open(lst,"w") as f:
        for p in processed: f.write(f"file '{os.path.abspath(p)}'\n")
    cmd_f=["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-i",audio,
           "-c:v","libx264","-preset","fast","-crf","22",
           "-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(out)]
    r=subprocess.run(cmd_f,capture_output=True,text=True,timeout=900)
    if r.returncode!=0: raise Exception(f"Birlestirme hatasi: {r.stderr[-300:]}")
    mb=os.path.getsize(out)/1024/1024
    tg(f"Video hazir! Boyut: <b>{mb:.0f} MB</b>","✅")
    return str(out)

def yt_token():
    r=requests.post("https://oauth2.googleapis.com/token",
        data={"client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,
              "refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},timeout=30)
    if r.status_code!=200: raise Exception(f"YT token: {r.text}")
    return r.json()["access_token"]

def upload_youtube(video, thumb, title, desc, tags, pub_iso):
    tg("YouTube'a yukleniyor...","📤")
    token=yt_token()
    meta={"snippet":{"title":title[:100],"description":desc[:5000],"tags":tags[:15],"categoryId":"27"},
          "status":{"privacyStatus":"private","publishAt":pub_iso,"selfDeclaredMadeForKids":False}}
    fsize=os.path.getsize(video)
    init=requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json",
                 "X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(fsize)},
        json=meta,timeout=30)
    if init.status_code!=200: raise Exception(f"YT init: {init.text[:200]}")
    upload_url=init.headers["Location"]
    tg(f"Video yukleniyor ({fsize//1024//1024} MB)...","⏳")
    with open(video,"rb") as f:
        up=requests.put(upload_url,headers={"Content-Type":"video/mp4"},data=f,timeout=900)
    if up.status_code not in [200,201]: raise Exception(f"YT yukleme: {up.text[:200]}")
    vid_id=up.json()["id"]; vid_url=f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}","✅")
    try:
        with open(thumb,"rb") as tf:
            tr=requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},data=tf,timeout=60)
        tg("Thumbnail yuklendi!" if tr.status_code in[200,201] else f"Thumbnail atildi({tr.status_code})","✅" if tr.status_code in[200,201] else "⚠")
    except Exception as e: tg(f"Thumbnail hatasi: {e}","⚠")
    return vid_url,vid_id

def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else ""
    if not cmd: sys.exit(1)
    try: p=parse_command(cmd)
    except Exception as e: tg(str(e),"❌"); sys.exit(1)
    mtype,_=get_music(p["topic"])
    tg(f"<b>Video Bot v5 Basladi!</b>\n\nKonu: <b>{p['topic']}</b>\nSure: {p['duration']} dakika\nGorsel: {p['img_count']} adet\nYayin: {p['publish_dt'].strftime('%d.%m.%Y %H:%M')}\nMuzik: {mtype}\nSes: Derin belgesel tonu","🚀")
    try:
        content=research_and_script(p["topic"],p["duration"],p["img_count"])
        (WORK/"metadata.json").write_text(json.dumps(content,ensure_ascii=False,indent=2))
        music=download_music(p["topic"])
        images=generate_images(content["image_prompts"])
        thumb=generate_thumbnail(content["thumbnail_prompt"],content["thumbnail_text"],
                                 content.get("thumbnail_bg_color","#1a1a2e"),p["topic"])
        audio,duration=generate_audio(content["script"])
        mixed=mix_audio(audio,music,duration)
        video=create_video(images,mixed,duration)
        vid_url,vid_id=upload_youtube(video,thumb,content["seo_title"],content["seo_description"],
                                      content["seo_tags"],p["publish_iso"])
        pub_str=p["publish_dt"].strftime("%d.%m.%Y saat %H:%M")
        tg(f"<b>TAMAMLANDI!</b>\n\n<b>{content['seo_title']}</b>\n\n{vid_url}\n\nYayin: <b>{pub_str}</b>\n\nBilgisayarin kapali olsa bile YouTube otomatik yayinlayacak!","🎉")
        (WORK/"result.json").write_text(json.dumps({"status":"success","video_url":vid_url,"title":content["seo_title"],"publish":p["publish_iso"]},ensure_ascii=False))
    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:300]}","❌")
        (WORK/"result.json").write_text(json.dumps({"status":"error","error":str(e)}))
        sys.exit(1)

if __name__=="__main__":
    main()
