"""Reproducible outline icons for the mini-program (Pillow, no external assets)."""
from pathlib import Path
from PIL import Image, ImageDraw

out = Path(__file__).resolve().parents[1] / 'miniprogram/images/ui'
out.mkdir(parents=True, exist_ok=True)
S=4
def icon(name, color, suffix=''):
    image=Image.new('RGBA',(96*S,96*S))
    d=ImageDraw.Draw(image)
    def xy(v): return tuple(int(x*S) for x in v)
    def line(points,w=5): d.line([(int(x*S),int(y*S)) for x,y in points],fill=color,width=w*S,joint='curve')
    def rect(box,r=6): d.rounded_rectangle(xy(box),radius=r*S,outline=color,width=5*S)
    def circle(box): d.ellipse(xy(box),outline=color,width=5*S)
    if name in ('survey','calendar'):
        rect((23,22,73,80));rect((36,15,60,29),4)
        if name=='survey':
            for y in (43,57,69):line([(35,y),(61,y)],4)
        else:
            line([(24,39),(72,39)],4);line([(35,56),(44,65),(62,48)],5)
    elif name=='checkin':
        circle((17,17,79,79));line([(31,47),(44,60),(67,36)],6)
    elif name=='chat':
        rect((16,20,80,68),16);line([(26,66),(24,80),(45,68)],4)
        for x in (34,48,62):d.ellipse(xy((x-3,42,x+3,48)),fill=color)
    elif name=='book':
        line([(48,27),(38,21),(17,21),(17,74),(37,74),(48,80),(59,74),(79,74),(79,21),(58,21),(48,27),(48,80)],5)
        line([(28,36),(37,36)],4);line([(28,48),(37,48)],4);line([(59,36),(68,36)],4);line([(59,48),(68,48)],4)
    elif name=='user':
        circle((34,17,62,45));d.arc(xy((20,50,76,102)),180,360,fill=color,width=5*S);line([(20,76),(76,76)],5)
    elif name=='doctor':
        line([(24,19),(24,41),(28,51),(38,57),(48,51),(52,41),(52,19)],5)
        line([(20,19),(28,19)],5);line([(48,19),(56,19)],5)
        d.arc(xy((37,42,77,83)),0,180,fill=color,width=5*S);line([(38,57),(38,62)],5);line([(77,61),(77,43)],5);circle((68,27,86,45))
    elif name=='leaf':
        d.arc(xy((18,17,79,77)),80,280,fill=color,width=5*S)
        line([(48,18),(77,18),(77,45),(69,63),(48,74),(31,71)],5);line([(24,81),(62,38)],5)
    elif name=='water':
        line([(48,15),(23,51)],5);line([(48,15),(73,51)],5);d.arc(xy((21,31,75,82)),0,180,fill=color,width=5*S);d.arc(xy((32,44,65,72)),10,90,fill=color,width=4*S)
    elif name=='activity':
        line([(11,50),(29,50),(39,26),(55,72),(66,43),(85,43)],5)
    elif name=='group':
        circle((34,17,60,43));d.arc(xy((24,49,72,96)),180,360,fill=color,width=5*S)
        d.arc(xy((13,24,35,46)),80,280,fill=color,width=4*S);d.arc(xy((60,24,82,46)),260,100,fill=color,width=4*S)
        d.arc(xy((6,52,30,88)),180,270,fill=color,width=4*S);d.arc(xy((65,52,90,88)),270,360,fill=color,width=4*S)
    image.resize((96,96),Image.Resampling.LANCZOS).save(out/f'{name}{suffix}.png')

for name in ['survey','checkin','chat','book','user','calendar','doctor','leaf','water','activity','group']:
    icon(name,'#147A61')
for name in ['survey','checkin','chat','book','user']:
    icon(name,'#7E8C86','-muted')
