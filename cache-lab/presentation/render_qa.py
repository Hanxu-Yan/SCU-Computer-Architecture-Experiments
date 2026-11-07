"""File-based slide QA: native Quick Look charts with OOXML text/table geometry."""
from pathlib import Path
from zipfile import ZipFile
import re, json, subprocess
import xml.etree.ElementTree as E
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
BUILD=HERE/"build"
PREVIEW=BUILD/"quicklook/candidate.pptx.qlpreview"
OUT=BUILD/"renders"
OUT.mkdir(exist_ok=True)
N={"a":"http://schemas.openxmlformats.org/drawingml/2006/main","p":"http://schemas.openxmlformats.org/presentationml/2006/main","c":"http://schemas.openxmlformats.org/drawingml/2006/chart"}
FONT="/Library/Fonts/Arial Unicode.ttf"
fonts={}
def font(size):
 size=round(size)
 if size not in fonts: fonts[size]=ImageFont.truetype(FONT,size)
 return fonts[size]
def box(node,kind="a"):
 f=node.find(".//"+kind+":xfrm",N)
 off=f.find("a:off",N);ext=f.find("a:ext",N)
 return [int(off.get("x"))/9525,int(off.get("y"))/9525,int(ext.get("cx"))/9525,int(ext.get("cy"))/9525]
def wrap(text,f,width):
 lines=[]
 for source in text.split("\n"):
  line=""
  for c in source:
   if line and f.getlength(line+c)>width:
    lines.append(line);line=""
   line+=c
  lines.append(line)
 return lines
warnings=[]
def text(draw,body,x,y,w,h,slide,table=False):
 entries=[]
 for para in body.findall("a:p",N):
  t="".join(v.text or "" for v in para.findall(".//a:t",N))
  if not t: continue
  pr=para.find("a:r/a:rPr",N)
  size=int(pr.get("sz","2400"))/75
  bold=pr.get("b")=="1"
  fill=pr.find("a:solidFill/a:srgbClr",N)
  color="#"+(fill.get("val") if fill is not None else "24282C")
  ppr=para.find("a:pPr",N);align=ppr.get("algn","l") if ppr is not None else "l"
  for line in wrap(t,font(size),w):
   entries.append((line,size,bold,color,align))
 total=sum(size*(1.26 if table else 1.38) for _,size,_,_,_ in entries)
 if total>h+4: warnings.append(dict(slide=slide,text=" / ".join(e[0] for e in entries),height=total,frame=h))
 yy=y+(max(0,h-total)/2 if table else 0)
 for t,size,bold,color,align in entries:
  f=font(size);tw=f.getlength(t)
  xx=x+(w-tw)/2 if align=="ctr" else x+w-tw if align=="r" else x
  draw.text((xx,yy),t,font=f,fill=color,anchor="lt",stroke_width=0 if not bold else 0)
  if bold: draw.text((xx+.5,yy),t,font=f,fill=color,anchor="lt")
  yy+=size*(1.26 if table else 1.38)

pdfs=re.findall(r'<img src="(Attachment\d+\.pdf)"', (PREVIEW/"Preview.html").read_text())
assert len(pdfs)==8
for pdf in pdfs:
 p=PREVIEW/pdf
 subprocess.run(["pdftoppm","-scale-to","1600","-png","-singlefile",str(p),str(p.with_suffix(""))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
chart=0
with ZipFile(BUILD/"candidate.pptx") as z:
 for i in range(1,17):
  root=E.fromstring(z.read(f"ppt/slides/slide{i}.xml"))
  im=Image.new("RGB",(1280,720),"white");draw=ImageDraw.Draw(im)
  for obj in root.find("p:cSld/p:spTree",N):
   if obj.tag.endswith("}sp"):
    x,y,w,h=box(obj)
    text(draw,obj.find("p:txBody",N),x,y,w,h,i)
   elif obj.tag.endswith("}graphicFrame"):
    x,y,w,h=box(obj,"p")
    tbl=obj.find(".//a:tbl",N)
    if tbl is None:
     p=PREVIEW/Path(pdfs[chart]).with_suffix(".png")
     image=Image.open(p).convert("RGB").resize((round(w),round(h)),Image.Resampling.LANCZOS)
     im.paste(image,(round(x),round(y)));chart+=1
    else:
     widths=[int(c.get("w"))/9525 for c in tbl.findall("a:tblGrid/a:gridCol",N)]
     yy=y
     for row in tbl.findall("a:tr",N):
      hh=int(row.get("h"))/9525;xx=x
      for width,cell in zip(widths,row.findall("a:tc",N)):
       props=cell.find("a:tcPr",N)
       color=props.find("a:solidFill/a:srgbClr",N).get("val")
       draw.rectangle((xx,yy,xx+width,yy+hh),fill="#"+color)
       draw.line((xx,yy+hh,xx+width,yy+hh),fill="#D8DCDF",width=1)
       text(draw,cell.find("a:txBody",N),xx+14,yy+2,width-26,hh-4,i,True)
       xx+=width
      yy+=hh
  im.save(OUT/f"slide-{i:02}.png")
assert chart==8
(BUILD/"render_checks.json").write_text(json.dumps({"text_fit_warnings":warnings,"charts":"macOS Quick Look native chart renders","text_tables":"OOXML geometry rendered with installed Arial Unicode MS"},ensure_ascii=False,indent=2))
print(json.dumps(warnings,ensure_ascii=False,indent=2))
