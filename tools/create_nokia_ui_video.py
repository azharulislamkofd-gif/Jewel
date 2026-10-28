#!/usr/bin/env python3
"""Render the JEWEL-0.5 Nokia explainer from its hero image and three voice tracks.
Dependencies: Pillow and imageio-ffmpeg. Output: media/nokia_jewel_05.mp4.
"""
import math, os, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'media'
WORK = Path(os.environ.get('NOKIA_WORK', '/home/user/.cache/nokia_render'))
WORK.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
W,H=1280,720
F='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
B='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(s,b=False): return ImageFont.truetype(B if b else F,s)
def text(d,xy,s,size=20,fill='#eaf4ff',bold=False): d.text(xy,s,font=font(size,bold),fill=fill)
def rr(d,box,r=18,fill='#101d30',outline='#2b4561',width=1): d.rounded_rectangle(box,r,fill=fill,outline=outline,width=width)
def base(section,number):
    im=Image.new('RGB',(W,H),'#07101e'); p=im.load()
    for y in range(H):
        for x in range(W):
            glow=max(0,1-math.sqrt(((x-1050)/900)**2+((y-180)/600)**2))
            p[x,y]=(int(6+8*glow),int(13+18*glow),int(26+32*glow))
    d=ImageDraw.Draw(im)
    for x in range(0,W,64): d.line((x,0,x,H),fill='#101d2d',width=1)
    for y in range(0,H,64): d.line((0,y,W,y),fill='#101d2d',width=1)
    d.line((65,94,1215,94),fill='#29445b',width=2)
    rr(d,(64,35,224,72),18,'#10283b','#276d8d')
    text(d,(79,44),'JEWEL-0.5',15,'#75e2f4',True)
    text(d,(247,45),'THE STORY OF NOKIA',14,'#a9c1d4',True)
    text(d,(1060,45),f'{number} / 07',14,'#83a1b4',True)
    text(d,(66,657),section.upper(),14,'#7796a9',True)
    d.line((65,693,1215,693),fill='#20364c',width=4)
    d.line((65,693,65+1150*number/7,693),fill='#54dbee',width=4)
    return im,d

def eyebrow(d,s):
    text(d,(67,126),s,15,'#5fd9ed',True)
def left(d,title,sub):
    for i,line in enumerate(title): text(d,(62,180+i*67),line,52,'#f2f7ff',True)
    for i,line in enumerate(sub): text(d,(66,350+i*35),line,21,'#abc1d1')
def panel(d,x1=700,y1=140,x2=1206,y2=615): rr(d,(x1,y1,x2,y2),22,'#0b192b','#2a485f',2)
def badge(d,x,y,s): rr(d,(x,y,x+len(s)*10+30,y+35),17,'#11384b','#25718b'); text(d,(x+15,y+9),s,13,'#71def1',True)

def scene(i):
    im,d=base(['A remarkable journey','The beginnings','The mobile era','The icon','The turning point','A different Nokia','The takeaway'][i],i+1)
    if i==0:
        hero=Image.open(MEDIA/'nokia_ui_hero.png').convert('RGB').resize((790,442))
        im.paste(hero,(488,130)); d=ImageDraw.Draw(im)
        # restore left dark text zone for contrast
        d.rectangle((0,111,610,610),fill='#081321')
        eyebrow(d,'THE RISE. THE FALL. THE REINVENTION.')
        text(d,(62,196),'NOKIA',92,'#f1f8ff',True)
        text(d,(66,310),'A STORY OF',29,'#d0e7f4',True)
        text(d,(66,357),'REINVENTION',36,'#64dff2',True)
        text(d,(67,441),'From a paper mill to a connected world.',19,'#a1b9cb')
        badge(d,67,506,'BANGLA DOCUMENTARY')
    elif i==1:
        eyebrow(d,'01  /  THE BEGINNING'); left(d,['It began with','paper.'],['Finland, 1865. A small wood-pulp mill','becomes the start of something much bigger.'])
        panel(d); text(d,(742,171),'ORIGIN',15,'#7aa7be',True); text(d,(740,209),'1865',86,'#68dff1',True)
        d.line((744,341,1155,341),fill='#28445d',width=2)
        for x,label in [(748,'PULP'),(892,'RUBBER'),(1046,'CABLE')]:
            d.ellipse((x,383,x+47,430),fill='#123e52',outline='#4ac9df',width=2); text(d,(x,450),label,15,'#d9eaf3',True)
        d.line((796,406,891,406),fill='#327088',width=3); d.line((940,406,1045,406),fill='#327088',width=3)
        text(d,(744,535),'FREDRIK IDESTAM  /  FINLAND',14,'#7f9fb1',True)
    elif i==2:
        eyebrow(d,'02  /  THE MOBILE ERA'); left(d,['Connecting','the world.'],['By 1998, Nokia had become the world’s','best-selling mobile phone brand.'])
        panel(d); text(d,(740,176),'MOBILE PHONES',15,'#87a5b7',True)
        text(d,(740,223),'#1',100,'#72e0f0',True); text(d,(744,354),'WORLDWIDE',24,'#d8eef6',True)
        d.line((744,418,1150,418),fill='#2c465c',width=2)
        badge(d,744,460,'1998  /  MARKET LEADER')
    elif i==3:
        eyebrow(d,'03  /  A CULTURAL ICON'); left(d,['An icon in','your pocket.'],['The 3310 became a familiar companion,','remembered for Snake and durability.'])
        hero=Image.open(MEDIA/'nokia_ui_hero.png').convert('RGB').resize((690,385)); im.paste(hero,(600,165)); d=ImageDraw.Draw(im)
        badge(d,745,550,'3310  /  THE CLASSIC')
    elif i==4:
        eyebrow(d,'04  /  THE TURNING POINT'); left(d,['A new era.','A new race.'],['Smartphones changed the rules, and','competition intensified across software','and app ecosystems.'])
        panel(d); text(d,(740,172),'THE SHIFT',15,'#7ea2b7',True)
        rr(d,(741,226,1159,288),12,'#122b40','#284d63'); text(d,(762,246),'iPHONE + ANDROID',20,'#d8edf6',True)
        d.line((949,290,949,347),fill='#4dc5dd',width=3); d.polygon([(939,342),(959,342),(949,355)],fill='#4dc5dd')
        rr(d,(741,369,1159,455),12,'#173447','#32627a'); text(d,(762,386),'2014',25,'#70e2f2',True); text(d,(762,422),'Devices business sold to Microsoft',15,'#c2d9e5')
        text(d,(744,529),'COMPETITION  /  CHANGE',14,'#7f9fb1',True)
    elif i==5:
        eyebrow(d,'05  /  NOKIA TODAY'); left(d,['Not gone.','Reinvented.'],['Today Nokia focuses on the technology','that keeps the world connected.'])
        panel(d); text(d,(740,175),'NOKIA TODAY',15,'#83a8bb',True)
        entries=[('01','MOBILE NETWORKS'),('02','FIBER + CLOUD'),('03','TECHNOLOGY LICENSING')]
        for n,(num,label) in enumerate(entries):
            y=229+n*90; rr(d,(739,y,1160,y+64),12,'#102a3d','#27546a'); text(d,(759,y+20),num,16,'#5ad9ed',True); text(d,(814,y+20),label,16,'#dbeef6',True)
        text(d,(740,538),'Some Nokia-branded phones are made',13,'#7d9eb1')
        text(d,(740,560),'by separate licensees.',13,'#7d9eb1')
    else:
        eyebrow(d,'06  /  THE TAKEAWAY'); left(d,['Change is','the constant.'],['Technology changes. Markets change.','The challenge is to keep evolving.'])
        panel(d); text(d,(742,174),'YOUR TURN',15,'#83a8bb',True)
        text(d,(740,235),'What was your',29,'#e6f5fa',True)
        text(d,(740,278),'first Nokia?',37,'#6fe1f0',True)
        d.line((741,367,1156,367),fill='#2b536a',width=2)
        badge(d,742,415,'TELL US IN THE COMMENTS')
        text(d,(742,541),'JEWEL-0.5  /  THANKS FOR WATCHING',13,'#88a9b9',True)
    im.save(WORK/f'scene{i}.png')

# Approximate chapter boundaries aligned to the three voice clips.
durations=[14.5,14.08,13.5,7.0,12.79,17.0,12.9]
for i in range(7): scene(i)
# Encoding static UI as subtly animated push-ins. A very brief dissolve to black marks each chapter.
for i,sec in enumerate(durations):
    out=WORK/f'scene{i}.mp4'
    vf=(f"zoompan=z='min(zoom+0.000035,1.025)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=24,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={sec-0.3}:d=0.3,format=yuv420p")
    subprocess.run([FF,'-y','-loop','1','-i',str(WORK/f'scene{i}.png'),'-vf',vf,'-t',str(sec),'-an','-c:v','libx264','-preset','veryfast','-crf','21',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(f'chapter {i+1}/7 complete',flush=True)
(WORK/'video.txt').write_text(''.join(f"file '{WORK}/scene{i}.mp4'\n" for i in range(7)))
(WORK/'audio.txt').write_text(''.join(f"file '{MEDIA}/nokia_voice_{i}.mp3'\n" for i in range(1,4)))
subprocess.run([FF,'-y','-f','concat','-safe','0','-i',str(WORK/'video.txt'),'-f','concat','-safe','0','-i',str(WORK/'audio.txt'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart','-shortest',str(MEDIA/'nokia_jewel_05.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('Video ready:',MEDIA/'nokia_jewel_05.mp4',flush=True)
