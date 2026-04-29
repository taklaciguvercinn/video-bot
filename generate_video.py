#!/usr/bin/env python3
"""Video Bot v7 - Tum problemler kalici olarak cozuldu"""

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

def tg(mesaj, emoji=""):
    text = f"{emoji} {mesaj}".strip()
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":"HTML"},timeout=10)
    except: pass
    print(text)

def tg_foto(dosya, aciklama):
    try:
        with open(dosya,"rb") as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id":TELEGRAM_CHAT_ID,"caption":aciklama,"parse_mode":"HTML"},
                files={"photo":f},timeout=30)
    except: pass

def komut_isle(cmd):
    p = [x.strip() for x in cmd.strip().split(",")]
    if len(p)!=5: raise ValueError("Format: Konu,Dakika,Resim,GG.AA.YYYY,SS:DD")
    konu,sure,resim,tarih,saat = p
    yayin = datetime.strptime(f"{tarih} {saat}","%d.%m.%Y %H:%M")
    return {"konu":konu,"sure":int(sure),"resim":int(resim),
            "yayin_dt":yayin,"yayin_iso":yayin.strftime("%Y-%m-%dT%H:%M:%S+00:00")}

def muzik_uret(konu, sure_saniye):
    tg("Muzik uretiliyor (konuya ozel)...","🎵")
    yol = WORK/"muzik.mp3"
    k = konu.lower()
    for c,r in [("ş","s"),("ğ","g"),("ı","i"),("ö","o"),("ü","u"),("ç","c")]:
        k = k.replace(c,r)
    if any(x in k for x in ["viking","savas","osmanli","roma","selcuklu","tarih"]):
        filtre = "aevalsrc=0.3*sin(55*2*PI*t)+0.2*sin(110*2*PI*t)+0.15*sin(82*2*PI*t)+0.1*sin(41*2*PI*t):s=44100"
    elif any(x in k for x in ["misir","antik","yunan","sumer","mezopotamya"]):
        filtre = "aevalsrc=0.25*sin(174*2*PI*t)+0.2*sin(261*2*PI*t)+0.15*sin(348*2*PI*t)+0.1*sin(130*2*PI*t):s=44100"
    elif any(x in k for x in ["uzay","yapay","teknoloji","bilim","robot"]):
        filtre = "aevalsrc=0.2*sin(220*2*PI*t*(1+0.005*sin(0.1*2*PI*t)))+0.15*sin(330*2*PI*t)+0.1*sin(440*2*PI*t):s=44100"
    elif any(x in k for x in ["doga","hayvan","deniz","orman"]):
        filtre = "aevalsrc=0.15*sin(196*2*PI*t)+0.12*sin(261*2*PI*t)+0.1*sin(329*2*PI*t)+0.08*sin(392*2*PI*t):s=44100"
    elif any(x in k for x in ["gizem","korku","paranormal","komplo"]):
        filtre = "aevalsrc=0.2*sin(73*2*PI*t)+0.15*sin(110*2*PI*t)+0.1*sin(155*2*PI*t)+0.08*sin(207*2*PI*t):s=44100"
    else:
        filtre = "aevalsrc=0.2*sin(130*2*PI*t)+0.18*sin(164*2*PI*t)+0.15*sin(196*2*PI*t)+0.12*sin(261*2*PI*t):s=44100"
    cmd = ["ffmpeg","-y","-f","lavfi","-i",filtre,"-af",
           f"aecho=0.8:0.9:100:0.3,afade=t=in:st=0:d=3,afade=t=out:st={max(0,sure_saniye-5)}:d=5,volume=0.7",
           "-t",str(sure_saniye+15),"-c:a","mp3","-b:a","128k",str(yol)]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if r.returncode==0 and yol.exists():
        tg("Muzik hazir! (Konuya ozel)","✅")
        return str(yol)
    tg("Muzik basarisiz","⚠")
    return ""

def gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type":"application/json","x-goog-api-key":GEMINI_API_KEY}
    body = {"contents":[{"parts":[{"text":prompt}]}],
            "generationConfig":{"temperature":0.7,"maxOutputTokens":8192,"thinkingConfig":{"thinkingBudget":0}}}
    for deneme in range(5):
        try:
            r = requests.post(url,headers=headers,json=body,timeout=180)
            if r.status_code==200:
                cands = r.json().get("candidates",[])
                if cands:
                    metin = cands[0].get("content",{}).get("parts",[{}])[0].get("text","").strip()
                    if metin: return metin
                tg(f"Gemini bos yanit ({deneme+1}/5)","⏳")
                time.sleep(20)
            elif r.status_code in [429,503]:
                tg(f"Gemini mesgul, {40*(deneme+1)}s...","⏳")
                time.sleep(15*(deneme+1))
            else:
                raise Exception(f"HTTP {r.status_code}: {r.json().get('error',{}).get('message',r.text[:80])}")
        except requests.Timeout:
            tg(f"Gemini timeout ({deneme+1}/5)","⏳")
            time.sleep(15)
    raise Exception("Gemini 5 denemede yanit vermedi")

def json_cikart(ham):
    ham = re.sub(r"```json\s*|```\s*","",ham).strip()
    try: return json.loads(ham)
    except: pass
    s=ham.find("{"); e=ham.rfind("}")+1
    if s!=-1 and e>s:
        seg=ham[s:e]
        try: return json.loads(seg)
        except: pass
        try:
            temiz=re.sub(r"(?<=[^\s{,:\[])'(?=[^\s},:!\]])", "",seg)
            return json.loads(temiz)
        except: pass
    veri={}
    for alan,pat in [("baslik",r'"baslik"\s*:\s*"([^"]{1,100})"'),("aciklama",r'"aciklama"\s*:\s*"([^"]{1,800})"'),
                     ("thumbnail_metin",r'"thumbnail_metin"\s*:\s*"([^"]{1,50})"'),
                     ("thumbnail_prompt",r'"thumbnail_prompt"\s*:\s*"([^"]{1,300})"'),("renk",r'"renk"\s*:\s*"(#[0-9a-fA-F]{6})"')]:
        m=re.search(pat,ham)
        if m: veri[alan]=m.group(1)
    for pat in [r'"senaryo"\s*:\s*"([\s\S]{200,}?)"(?=\s*,\s*"(?:gorsel|thumb|etiket|renk))',r'"senaryo"\s*:\s*"([\s\S]{200,})"']:
        m=re.search(pat,ham)
        if m: veri["senaryo"]=m.group(1); break
    tm=re.search(r'"etiketler"\s*:\s*\[(.*?)\]',ham,re.DOTALL)
    if tm: veri["etiketler"]=re.findall(r'"([^"]+)"',tm.group(1))
    im=re.search(r'"gorseller"\s*:\s*\[(.*?)\]',ham,re.DOTALL)
    if im: veri["gorseller"]=re.findall(r'"([^"]+)"',im.group(1))
    if "baslik" in veri and ("senaryo" in veri or "gorseller" in veri): return veri
    raise Exception(f"JSON okunamadi: {ham[:80]}")

def senaryo_uret(konu, sure, resim_sayisi):
    tg(f"'{konu}' icin icerik uretiliyor...","📚")
    kelime_hedef = sure * 160

    tg("Adim 1: Baslik ve gorsel promptlari...","📋")
    prompt1 = f"""YouTube belgesel. Konu: {konu}. Sure: {sure} dk.
Apostrof kullanma. Emojileri sadece baslik alaninda kullan.
JSON: {{"baslik":"baslik 55 karakter emoji","aciklama":"aciklama 400 karakter hashtag","etiketler":["e1","e2","e3","e4","e5","e6","e7","e8"],"gorseller":[{"".join([f'"ingilizce sinematik prompt {i+1} dramatic 8k",' for i in range(resim_sayisi)]).rstrip(",")}],"thumbnail_metin":"MAX 3 KELIME","thumbnail_prompt":"epic dramatic cinematic no text","renk":"#1a1a2e"}}"""

    meta = None
    for _ in range(4):
        try:
            meta = json_cikart(gemini(prompt1))
            if "baslik" in meta: break
        except Exception as e:
            tg(f"Meta hatasi: {str(e)[:60]}","⚠")
            time.sleep(15)

    if not meta:
        meta={"baslik":f"{konu} Belgeseli","aciklama":f"{konu} belgeseli. #belgesel #tarih",
              "etiketler":[konu,"belgesel","tarih","youtube"],
              "gorseller":[f"{konu} dramatic cinematic scene {i+1} 8k" for i in range(resim_sayisi)],
              "thumbnail_metin":konu.upper()[:15],"thumbnail_prompt":f"{konu} epic dramatic","renk":"#1a1a2e"}

    while len(meta.get("gorseller",[]))<resim_sayisi:
        meta["gorseller"].append(f"{konu} historical dramatic cinematic {len(meta['gorseller'])+1} 8k")
    tg(f"Meta hazir: <b>{meta['baslik']}</b>","✅")

    tg(f"Adim 2: {kelime_hedef} kelimelik senaryo yaziliyor...","📝")
    prompt2 = f"""Profesyonel YouTube belgesel senaristiyim.
'{konu}' konusunda {sure} dakikalik Turkce belgesel metni yaz.
ZORUNLU: Tam {kelime_hedef} kelime olmali!
KURAL: Sadece seslendirilecek duz Turkce metin.
KURAL: Hicbir gorsel notu, muzik ismi, teknik not, kose parantezi, yildiz, emoji YOK.
KURAL: Apostrof (') kullanma. Turkce karakterleri kullan.
KURAL: National Geographic tarzinda akici, merak uyandiran, bilgilendirici.
Sadece metni yaz:"""

    senaryo = ""
    for _ in range(4):
        try:
            ham = gemini(prompt2)
            ham = re.sub(r'\[.*?\]','',ham,flags=re.DOTALL)
            ham = re.sub(r'^\*+\s*','',ham,flags=re.MULTILINE)
            ham = re.sub(r'^#+\s.*$','',ham,flags=re.MULTILINE)
            ham = re.sub(r'\n{3,}','\n\n',ham).strip()
            kelime = len(ham.split())
            if kelime >= kelime_hedef*0.7:
                senaryo = ham
                tg(f"Senaryo hazir: {kelime} kelime","✅")
                break
            else:
                tg(f"Kisa ({kelime}/{kelime_hedef}), uzatiliyor...","⚠")
                prompt_uzat = f"Bu metni devam ettir ve genislet. Toplam {kelime_hedef} kelime hedefi. Konu: {konu}. Apostrof yok, emoji yok. Devam:\n\n{ham[-300:]}"
                ham2 = gemini(prompt_uzat)
                ham2 = re.sub(r'\[.*?\]','',ham2,flags=re.DOTALL).strip()
                senaryo = (ham + "\n\n" + ham2).strip()
                tg(f"Uzatildi: {len(senaryo.split())} kelime","✅")
                break
        except Exception as e:
            tg(f"Senaryo hatasi: {str(e)[:60]}","⚠")
            time.sleep(15)

    if not senaryo:
        senaryo = f"{konu} tarihin en ilginc konularindan biridir. Bu belgeselde bu konuyu derinlemesine inceliyoruz."
    meta["senaryo"] = senaryo
    tg(f"Toplam: {len(senaryo.split())} kelime | {resim_sayisi} gorsel","📊")
    return meta

def gorsel_indir_tek(i, prompt, toplam):
    yol = WORK/f"img_{i+1:02d}.jpg"
    for seed in [i*7+42, i*13+17, i*3+99, i*11+5, i*17+33]:
        enc = quote(f"{prompt}, ultra detailed 4k cinematic photography professional")
        url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={seed}&nologo=true&model=flux&enhance=true"
        try:
            r = requests.get(url,timeout=180)
            if r.status_code==200 and len(r.content)>20000 and r.content[:2]==b'\xff\xd8':
                yol.write_bytes(r.content)
                tg(f"Gorsel {i+1}/{toplam} hazir","🖼")
                time.sleep(10)
                return str(yol)
            elif r.status_code==429:
                tg("Rate limit, 45s bekleniyor...","⏳")
                time.sleep(45)
            else:
                time.sleep(12)
        except: time.sleep(12)
    # Turbo
    enc = quote(f"{prompt}, cinematic 4k")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1920&height=1080&seed={i+300}&nologo=true&model=turbo"
    try:
        r = requests.get(url,timeout=120)
        if r.status_code==200 and len(r.content)>5000 and r.content[:2]==b'\xff\xd8':
            yol.write_bytes(r.content)
            tg(f"Gorsel {i+1}/{toplam} turbo ile hazir","🖼")
            time.sleep(10)
            return str(yol)
    except: pass
    renkler=[("0x1a1a2e","0x16213e"),("0x2d1b00","0x4a2f00"),("0x0d1b0d","0x1a3a1a"),("0x1a0000","0x3a1a1a"),("0x1a0d1a","0x2d1b2d")]
    r1,r2=renkler[i%len(renkler)]
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={r1}:size=1920x1080:rate=1","-vframes","1","-q:v","2",str(yol)],capture_output=True)
    tg(f"Gorsel {i+1} yedek renk","⚠")
    return str(yol)

def gorseller_uret(promptlar):
    tg(f"{len(promptlar)} gorsel indiriliyor (sirali, rate limit yok)\n⏳ ~{len(promptlar)*2:.0f} dk","🎨")
    return [gorsel_indir_tek(i,p,len(promptlar)) for i,p in enumerate(promptlar)]

def thumbnail_uret(prompt, metin, renk, konu):
    tg("Thumbnail uretiliyor...","🖼")
    enc = quote(f"{prompt}, youtube thumbnail dramatic vibrant no text")
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1280&height=720&seed=777&nologo=true&model=flux&enhance=true"
    base=WORK/"thumb_base.jpg"; final=WORK/"thumbnail.jpg"
    for _ in range(4):
        try:
            r=requests.get(url,timeout=180)
            if r.status_code==200 and len(r.content)>5000 and r.content[:2]==b'\xff\xd8':
                base.write_bytes(r.content); break
            time.sleep(15)
        except: time.sleep(15)
    else:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={renk.replace('#','0x')}:size=1280x720:rate=1","-vframes","1",str(base)],capture_output=True)
    m=metin.upper()[:25].replace("'","").replace(":","\\:").replace('"',"")
    k=konu.upper()[:20].replace("'","").replace(":","\\:").replace('"',"")
    fs=80 if len(m)<=10 else 60 if len(m)<=18 else 44
    vf=(f"drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.42:color=black@0.72:t=fill,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=black@0.4:x=(w-text_w)/2+2:y=h*0.62+2:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{m}':fontsize={fs}:fontcolor=white:x=(w-text_w)/2:y=h*0.62:font=DejaVu Sans:style=Bold,"
        f"drawtext=text='{k}':fontsize=30:fontcolor=yellow:x=20:y=20:font=DejaVu Sans:style=Bold")
    r=subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",vf,"-q:v","2",str(final)],capture_output=True,text=True)
    if r.returncode!=0 or not final.exists(): subprocess.run(["cp",str(base),str(final)])
    if final.exists(): tg_foto(str(final),f"Thumbnail: {m}")
    tg("Thumbnail hazir!","✅")
    return str(final)

def ses_uret(senaryo):
    tg("Derin belgesel sesi sentezleniyor...","🎙")
    sf=WORK/"senaryo.txt"; rf=WORK/"ses_ham.mp3"; ff=WORK/"ses.mp3"
    sf.write_text(senaryo,encoding="utf-8")
    r=subprocess.run(["edge-tts","--voice","tr-TR-AhmetNeural","--file",str(sf),
        "--write-media",str(rf),"--rate=-8%","--pitch=-10Hz","--volume=+15%"],capture_output=True,text=True)
    if r.returncode!=0 or not rf.exists():
        tg("Parametreli ses basarisiz...","⚠")
        r2=subprocess.run(["edge-tts","--voice","tr-TR-AhmetNeural","--file",str(sf),"--write-media",str(rf)],capture_output=True,text=True)
        if r2.returncode!=0 or not rf.exists(): raise Exception(f"TTS basarisiz: {r2.stderr[-100:]}")
    subprocess.run(["ffmpeg","-y","-i",str(rf),"-af",
        "equalizer=f=80:width_type=o:width=2:g=5,equalizer=f=200:width_type=o:width=2:g=3,"
        "equalizer=f=3000:width_type=o:width=2:g=-3,equalizer=f=8000:width_type=o:width=2:g=-5,"
        "acompressor=threshold=-16dB:ratio=3:attack=5:release=60,volume=1.3",
        "-c:a","mp3","-b:a","192k",str(ff)],capture_output=True)
    kullan=str(ff) if ff.exists() else str(rf)
    probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",kullan],capture_output=True,text=True)
    sure=float(json.loads(probe.stdout)["format"]["duration"])
    tg(f"Ses hazir! Sure: <b>{sure/60:.1f} dakika</b>","✅")
    return kullan,sure

def ses_miksle(anlati, muzik, sure):
    if not muzik or not os.path.exists(muzik): return anlati
    tg("Ses + Muzik karistiriliyor...","🎚")
    miksl=WORK/"miksl.mp3"
    cmd=["ffmpeg","-y","-i",anlati,"-stream_loop","-1","-i",muzik,
         "-filter_complex",f"[1:a]volume=0.15,atrim=0:{sure+2}[muz];[0:a][muz]amix=inputs=2:duration=first:weights=1 0.15[out]",
         "-map","[out]","-c:a","aac","-b:a","192k","-t",str(sure),str(miksl)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode==0 and miksl.exists():
        tg("Ses karisimi hazir!","✅"); return str(miksl)
    return anlati

def video_montaj(gorseller, ses, toplam_sure):
    tg(f"Video montajlaniyor...\n{len(gorseller)} gorsel | Zoom+Pan+Fade\n⏳ ~{len(gorseller)//2+5} dk","🎬")
    cikis=WORK/"video.mp4"; liste=WORK/"liste.txt"
    her_biri=toplam_sure/len(gorseller); fps=25
    tg(f"Toplam: {toplam_sure/60:.1f} dk | Her gorsel: {her_biri:.1f}s","⚙")
    segmentler=[]
    for i,gorsel in enumerate(gorseller):
        seg=WORK/f"seg_{i:02d}.mp4"
        fo=max(0,her_biri-0.7); fr=max(int(her_biri*fps),25); d=i%4
        if d==0:   z,x,y="min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        elif d==1: z,x,y="min(zoom+0.0008,1.1)","iw/2-(iw/zoom/2)+on*0.5","ih/2-(ih/zoom/2)"
        elif d==2: z,x,y="if(lte(on,1),1.1,max(zoom-0.0008,1.0))","iw/2-(iw/zoom/2)","ih/2-(ih/zoom/2)"
        else:      z,x,y="min(zoom+0.0006,1.08)","iw/2-(iw/zoom/2)-on*0.4","ih/2-(ih/zoom/2)"
        cmd=["ffmpeg","-y","-loop","1","-t",str(her_biri+1),"-i",gorsel,
             "-vf",f"scale=iw*2:ih*2,zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s=1920x1080:fps={fps},"
                   f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
             "-t",str(her_biri),"-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
        if r.returncode==0 and seg.exists() and seg.stat().st_size>500:
            segmentler.append(str(seg)); tg(f"Segment {i+1}/{len(gorseller)} zoom ok","🎬")
        else:
            pan=str(min(i*3,80)) if i%2==0 else str(max(-80,-i*3))
            cmd2=["ffmpeg","-y","-loop","1","-t",str(her_biri),"-i",gorsel,
                  "-vf",f"scale=2000:1125,crop=1920:1080:{pan}:22,fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
                  "-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
            r2=subprocess.run(cmd2,capture_output=True,text=True,timeout=120)
            if r2.returncode==0 and seg.exists():
                segmentler.append(str(seg)); tg(f"Segment {i+1} pan ok","⚠")
            else:
                cmd3=["ffmpeg","-y","-loop","1","-t",str(her_biri),"-i",gorsel,
                      "-vf",f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,"
                            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fo:.2f}:d=0.5",
                      "-c:v","libx264","-preset","ultrafast","-crf","28","-an","-pix_fmt","yuv420p",str(seg)]
                r3=subprocess.run(cmd3,capture_output=True,text=True,timeout=120)
                if r3.returncode==0: segmentler.append(str(seg)); tg(f"Segment {i+1} fade ok","⚠")
    if not segmentler: raise Exception("Hicbir segment olusturulamadi!")
    with open(liste,"w") as f:
        for s in segmentler: f.write(f"file '{os.path.abspath(s)}'\n")
    cmd_son=["ffmpeg","-y","-f","concat","-safe","0","-i",str(liste),"-i",ses,
             "-c:v","libx264","-preset","fast","-crf","22","-c:a","aac","-b:a","192k",
             "-shortest","-movflags","+faststart",str(cikis)]
    r=subprocess.run(cmd_son,capture_output=True,text=True,timeout=900)
    if r.returncode!=0: raise Exception(f"Birlestirme: {r.stderr[-200:]}")
    mb=os.path.getsize(cikis)/1024/1024
    tg(f"Video hazir! <b>{mb:.0f} MB</b>","✅")
    return str(cikis)

def yt_token():
    r=requests.post("https://oauth2.googleapis.com/token",
        data={"client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,
              "refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},timeout=30)
    if r.status_code!=200: raise Exception(f"YT token: {r.text[:100]}")
    return r.json()["access_token"]

def youtube_yukle(video,thumb,baslik,aciklama,etiketler,yayin_iso):
    tg("YouTube'a yukleniyor...","📤")
    token=yt_token()
    meta={"snippet":{"title":baslik[:100],"description":aciklama[:5000],"tags":etiketler[:15],"categoryId":"27"},
          "status":{"privacyStatus":"private","publishAt":yayin_iso,"selfDeclaredMadeForKids":False}}
    boyut=os.path.getsize(video)
    init=requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json",
                 "X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(boyut)},json=meta,timeout=30)
    if init.status_code!=200: raise Exception(f"YT init: {init.text[:100]}")
    tg(f"Video yukleniyor ({boyut//1024//1024} MB)...","⏳")
    with open(video,"rb") as f:
        r=requests.put(init.headers["Location"],headers={"Content-Type":"video/mp4"},data=f,timeout=900)
    if r.status_code not in [200,201]: raise Exception(f"YT yukleme: {r.text[:100]}")
    vid_id=r.json()["id"]; vid_url=f"https://youtu.be/{vid_id}"
    tg(f"Video yuklendi!\n{vid_url}","✅")
    try:
        with open(thumb,"rb") as tf:
            tr=requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}",
                headers={"Authorization":f"Bearer {token}","Content-Type":"image/jpeg"},data=tf,timeout=60)
        tg("Thumbnail yuklendi!" if tr.status_code in[200,201] else f"Thumbnail atildi({tr.status_code})","✅" if tr.status_code in[200,201] else "⚠")
    except Exception as e: tg(f"Thumbnail: {str(e)[:50]}","⚠")
    return vid_url,vid_id

def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else ""
    if not cmd: sys.exit(1)
    try: p=komut_isle(cmd)
    except Exception as e: tg(str(e),"❌"); sys.exit(1)
    tg(f"<b>Video Bot v7 Basladi!</b>\nKonu: <b>{p['konu']}</b>\nSure: {p['sure']} dk\nGorsel: {p['resim']} adet\nYayin: {p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}","🚀")
    try:
        icerik=senaryo_uret(p["konu"],p["sure"],p["resim"])
        (WORK/"metadata.json").write_text(json.dumps(icerik,ensure_ascii=False,indent=2))
        muzik=muzik_uret(p["konu"],p["sure"]*60+120)
        gorseller=gorseller_uret(icerik["gorseller"])
        thumb=thumbnail_uret(icerik["thumbnail_prompt"],icerik["thumbnail_metin"],icerik.get("renk","#1a1a2e"),p["konu"])
        ses,sure=ses_uret(icerik["senaryo"])
        miksli=ses_miksle(ses,muzik,sure)
        video=video_montaj(gorseller,miksli,sure)
        vid_url,_=youtube_yukle(video,thumb,icerik["baslik"],icerik["aciklama"],icerik["etiketler"],p["yayin_iso"])
        tg(f"<b>TAMAMLANDI!</b>\n\n<b>{icerik['baslik']}</b>\n\n{vid_url}\n\nYayin: <b>{p['yayin_dt'].strftime('%d.%m.%Y %H:%M')}</b>","🎉")
        (WORK/"result.json").write_text(json.dumps({"status":"success","video_url":vid_url,"title":icerik["baslik"]},ensure_ascii=False))
    except Exception as e:
        tg(f"<b>Hata:</b>\n{str(e)[:300]}","❌")
        (WORK/"result.json").write_text(json.dumps({"status":"error","error":str(e)}))
        sys.exit(1)

if __name__=="__main__":
    main()
