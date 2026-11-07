"""Native OOXML writer used because the supplied artifact runtime is unavailable."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
import io, json

A="http://schemas.openxmlformats.org/drawingml/2006/main"
P="http://schemas.openxmlformats.org/presentationml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C="http://schemas.openxmlformats.org/drawingml/2006/chart"
REL="http://schemas.openxmlformats.org/package/2006/relationships"
CT="http://schemas.openxmlformats.org/package/2006/content-types"
X="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
FONT="Arial Unicode MS"
INK,MUTED,ACCENT,GRAY,BROWN,PALE,RULE="24282C","646B70","496577","A9ADB2","A58B70","F1F2F3","D8DCDF"

def emu(n): return str(round(n*9525))
def run(t,size=28,color=INK,bold=False):
 return f'<a:r><a:rPr lang="zh-CN" sz="{round(size*75)}" b="{int(bold)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:rPr><a:t xml:space="preserve">{escape(str(t))}</a:t></a:r>'
def paras(t,size=28,color=INK,bold=False,align="l",spacing=115):
 return "".join(f'<a:p><a:pPr algn="{align}"><a:lnSpc><a:spcPct val="{spacing*1000}"/></a:lnSpc><a:spcAft><a:spcPts val="0"/></a:spcAft></a:pPr>'+run(v,size,color,bold)+f'<a:endParaRPr lang="zh-CN" sz="{round(size*75)}"/></a:p>' for v in str(t).split("\n"))
def group():
 return '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
def rels(entries):
 return XML+f'<Relationships xmlns="{REL}">'+''.join(f'<Relationship Id="{i}" Type="{R}/{k}" Target="{t}"/>' for i,k,t in entries)+'</Relationships>'

class Slide:
 def __init__(self,deck,title="",subtitle="",notes=""):
  self.deck,self.title,self.notes=deck,title,notes
  self.parts,self.relationships,self.objects=[],[],[]
  self.nextid=2
  if title: self.text(title,64,42,1152,66,44,bold=True,name="Title")
  if subtitle: self.text(subtitle,66,116,1148,43,24,MUTED,name="Subtitle")
 def ident(self):
  i=self.nextid;self.nextid+=1;return i
 def text(self,t,x,y,w,h,size=28,color=INK,bold=False,align="l",name="Text"):
  i=self.ident()
  self.parts.append(f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:noAutofit/></a:bodyPr><a:lstStyle/>'+paras(t,size,color,bold,align)+'</p:txBody></p:sp>')
  self.objects.append(dict(type="text",text=str(t),x=x,y=y,w=w,h=h,size=size))
 def table(self,data,widths,heights,x=64,y=180,size=26,numeric_from=None):
  i=self.ident();w,h=sum(widths),sum(heights);body=""
  for ri,row in enumerate(data):
   cells=""
   for ci,t in enumerate(row):
    align="ctr" if numeric_from is not None and ci>=numeric_from else "l"
    fill=PALE if ri==0 else "FFFFFF"
    cells+=('<a:tc><a:txBody><a:bodyPr wrap="square" anchor="ctr"/><a:lstStyle/>'+paras(t,size,INK,ri==0,align,105)+'</a:txBody>'
      +f'<a:tcPr marL="{emu(14)}" marR="{emu(12)}" marT="{emu(2)}" marB="{emu(2)}" anchor="ctr">'
      +'<a:lnL w="0"><a:noFill/></a:lnL><a:lnR w="0"><a:noFill/></a:lnR><a:lnT w="0"><a:noFill/></a:lnT>'
      +f'<a:lnB w="6350"><a:solidFill><a:srgbClr val="{RULE}"/></a:solidFill><a:prstDash val="solid"/></a:lnB><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
   body+=f'<a:tr h="{emu(heights[ri])}">{cells}</a:tr>'
  self.parts.append(f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Table {i}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></p:xfrm><a:graphic><a:graphicData uri="{A}/table"><a:tbl><a:tblPr firstRow="1" bandRow="0"/><a:tblGrid>'+''.join(f'<a:gridCol w="{emu(c)}"/>' for c in widths)+'</a:tblGrid>'+body+'</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
  self.objects.append(dict(type="table",data=data,x=x,y=y,w=w,h=h))
 def chart(self,chart,x=64,y=180,w=790,h=420):
  chart["format"]=chart.get("format","0.000%").replace("%","")
  for series in chart["series"]:
   series["values"]=[v*100 for v in series["values"]]
  idx=len(self.deck.charts)+1;self.deck.charts.append(chart);rid=f"rIdChart{idx}";i=self.ident()
  self.relationships.append((rid,"chart",f"../charts/chart{idx}.xml"))
  self.parts.append(f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Chart {idx}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></p:xfrm><a:graphic><a:graphicData uri="{C}"><c:chart xmlns:c="{C}" r:id="{rid}"/></a:graphicData></a:graphic></p:graphicFrame>')
  self.objects.append(dict(type="chart",chart=chart,x=x,y=y,w=w,h=h))
 def xml(self,n):
  self.text(str(n),1166,678,50,24,18,MUTED,align="r",name="Page")
  return XML+f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld name="{escape(self.title)}"><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree>'+group()+''.join(self.parts)+'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'

def txpr(size=22,color=INK):
 return f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{round(size*75)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:defRPr></a:pPr><a:endParaRPr lang="zh-CN"/></a:p></c:txPr>'
def literal(values,string=False,fmt="0.000%"):
 tag="strCache" if string else "numCache"
 return f'<c:{tag}>'+("" if string else f'<c:formatCode>{fmt}</c:formatCode>')+f'<c:ptCount val="{len(values)}"/>'+''.join(f'<c:pt idx="{i}"><c:v>{escape(str(v))}</c:v></c:pt>' for i,v in enumerate(values))+f'</c:{tag}>'
def chart_xml(chart,idx):
 cats,series=chart["categories"],chart["series"];kind=chart.get("kind","bar");fmt=chart.get("format","0.000%")
 tag="barChart" if kind=="bar" else "lineChart";sx=""
 for j,ser in enumerate(series):
  col=chr(66+j);color=ser.get("color",[ACCENT,GRAY,BROWN][j%3])
  style=f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:ln w="{28575 if kind=="line" else 0}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr>'
  pts=''.join(f'<c:dPt><c:idx val="{i}"/><c:spPr><a:solidFill><a:srgbClr val="{c}"/></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr></c:dPt>' for i,c in enumerate(ser.get("point_colors",[])))
  marker=f'<c:marker><c:symbol val="circle"/><c:size val="7"/>{style}</c:marker>' if kind=="line" else ""
  fhead='Data!$'+col+'$1';fcat='Data!$A$2:$A$'+str(len(cats)+1);fval='Data!$'+col+'$2:$'+col+'$'+str(len(cats)+1)
  sx+=(f'<c:ser><c:idx val="{j}"/><c:order val="{j}"/><c:tx><c:strRef><c:f>{fhead}</c:f>'+literal([ser["name"]],True)+'</c:strRef></c:tx>'+style+marker+pts
       +f'<c:cat><c:strRef><c:f>{fcat}</c:f>'+literal(cats,True)+f'</c:strRef></c:cat><c:val><c:numRef><c:f>{fval}</c:f>'+literal(ser["values"],False,fmt)+'</c:numRef></c:val>'+('<c:smooth val="0"/>' if kind=="line" else "")+'</c:ser>')
 labels=""
 if chart.get("labels",kind=="bar"):
  labels=f'<c:dLbls><c:numFmt formatCode="{fmt}" sourceLinked="0"/>'+txpr(23)+'<c:dLblPos val="outEnd"/><c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>'
 ids=[100000+idx*10,100001+idx*10]
 plot=f'<c:{tag}>'+('<c:barDir val="col"/>' if kind=="bar" else "")+'<c:grouping val="'+('clustered' if kind=="bar" else 'standard')+'"/><c:varyColors val="0"/>'+sx+labels+('<c:gapWidth val="130"/><c:overlap val="0"/>' if kind=="bar" else '<c:marker val="1"/><c:smooth val="0"/>')+f'<c:axId val="{ids[0]}"/><c:axId val="{ids[1]}"/></c:{tag}>'
 line=f'<c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="{GRAY}"/></a:solidFill></a:ln></c:spPr>'
 ax0=f'<c:catAx><c:axId val="{ids[0]}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'+line+txpr(22)+f'<c:crossAx val="{ids[1]}"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="1"/></c:catAx>'
 ax1=f'<c:valAx><c:axId val="{ids[1]}"/><c:scaling><c:orientation val="minMax"/><c:max val="100"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="l"/><c:majorGridlines><c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="{RULE}"/></a:solidFill></a:ln></c:spPr></c:majorGridlines><c:numFmt formatCode="0" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'+line+txpr(21,MUTED)+f'<c:crossAx val="{ids[0]}"/><c:crosses val="autoZero"/><c:crossBetween val="between"/><c:majorUnit val="25"/></c:valAx>'
 legend='<c:legend><c:legendPos val="b"/><c:layout/><c:overlay val="0"/>'+txpr(22)+'</c:legend>' if len(series)>1 else ""
 return XML+f'<c:chartSpace xmlns:c="{C}" xmlns:a="{A}" xmlns:r="{R}"><c:date1904 val="0"/><c:lang val="zh-CN"/><c:roundedCorners val="0"/><c:chart><c:autoTitleDeleted val="1"/><c:plotArea><c:layout/>'+plot+ax0+ax1+'</c:plotArea>'+legend+'<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/><c:showDLblsOverMax val="0"/></c:chart><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'+txpr(22)+'<c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>'

def xlsx(chart):
 b=io.BytesIO();data=[["访问模式"]+[s["name"] for s in chart["series"]]]+[[cat]+[s["values"][i] for s in chart["series"]] for i,cat in enumerate(chart["categories"])]
 sheet=""
 for ri,row in enumerate(data,1):
  cells=""
  for ci,v in enumerate(row):
   ref=f"{chr(65+ci)}{ri}"
   cells+=f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' if isinstance(v,str) else f'<c r="{ref}"><v>{v}</v></c>'
  sheet+=f'<row r="{ri}">{cells}</row>'
 with ZipFile(b,"w",ZIP_DEFLATED) as z:
  z.writestr("[Content_Types].xml",XML+f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
  z.writestr("_rels/.rels",rels([("rId1","officeDocument","xl/workbook.xml")]))
  z.writestr("xl/workbook.xml",XML+f'<workbook xmlns="{X}" xmlns:r="{R}"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
  z.writestr("xl/_rels/workbook.xml.rels",rels([("rId1","worksheet","worksheets/sheet1.xml")]))
  z.writestr("xl/worksheets/sheet1.xml",XML+f'<worksheet xmlns="{X}"><sheetData>{sheet}</sheetData></worksheet>')
 return b.getvalue()
def notes_xml(t):
 return XML+f'<p:notes xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'+group()+'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>'+paras(t,18)+'</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'
def theme():
 vals=[("dk1",INK),("lt1","FFFFFF"),("dk2",MUTED),("lt2",PALE),("accent1",ACCENT),("accent2",GRAY),("accent3",BROWN),("accent4","6B797F"),("accent5","CDC4B7"),("accent6","DDE2E5"),("hlink",ACCENT),("folHlink",ACCENT)]
 clr=''.join(f'<a:{n}><a:srgbClr val="{c}"/></a:{n}>' for n,c in vals)
 fonts=''.join(f'<a:{k}><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:{k}>' for k in ["majorFont","minorFont"])
 solid='<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
 return XML+f'<a:theme xmlns:a="{A}" name="Cache Plain"><a:themeElements><a:clrScheme name="Neutral">{clr}</a:clrScheme><a:fontScheme name="Arial Unicode MS">{fonts}</a:fontScheme><a:fmtScheme name="Plain"><a:fillStyleLst>{solid*3}</a:fillStyleLst><a:lnStyleLst>'+''.join(f'<a:ln w="{w}">{solid}<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>' for w in [6350,12700,19050])+'</a:lnStyleLst><a:effectStyleLst>'+'<a:effectStyle><a:effectLst/></a:effectStyle>'*3+f'</a:effectStyleLst><a:bgFillStyleLst>{solid*3}</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'

class Deck:
 def __init__(self): self.slides,self.charts=[],[]
 def add(self,title="",subtitle="",notes=""):
  s=Slide(self,title,subtitle,notes);self.slides.append(s);return s
 def save(self,path):
  n=len(self.slides);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
  ct=[('presProps.xml','presentationml.presProps'),('viewProps.xml','presentationml.viewProps'),('tableStyles.xml','presentationml.tableStyles'),('presentation.xml','presentationml.presentation.main'),('slideMasters/slideMaster1.xml','presentationml.slideMaster'),('slideLayouts/slideLayout1.xml','presentationml.slideLayout'),('notesMasters/notesMaster1.xml','presentationml.notesMaster')]
  overrides=''.join(f'<Override PartName="/ppt/{p}" ContentType="application/vnd.openxmlformats-officedocument.{t}+xml"/>' for p,t in ct)
  overrides+='<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
  for i in range(1,n+1):
   for prefix,typ in [("slides/slide","slide"),("notesSlides/notesSlide","notesSlide")]:
    overrides+=f'<Override PartName="/ppt/{prefix}{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.{typ}+xml"/>'
  for i in range(1,len(self.charts)+1): overrides+=f'<Override PartName="/ppt/charts/chart{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
  cmap='<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
  with ZipFile(path,"w",ZIP_DEFLATED) as z:
   z.writestr("[Content_Types].xml",XML+f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>{overrides}</Types>')
   rr=rels([("rId1","officeDocument","ppt/presentation.xml"),("rId3","extended-properties","docProps/app.xml")])
   z.writestr("_rels/.rels",rr.replace('</Relationships>',f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'))
   z.writestr("docProps/core.xml",XML+'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Cache 映射方式与替换策略对命中率的影响</dc:title><dc:subject>计算机系统结构小组实验</dc:subject><dc:creator>实验小组</dc:creator></cp:coreProperties>')
   z.writestr("docProps/app.xml",XML+f'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Microsoft PowerPoint</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{n}</Slides><Notes>{n}</Notes></Properties>')
   pr=[("rId1","slideMaster","slideMasters/slideMaster1.xml"),("rId2","notesMaster","notesMasters/notesMaster1.xml"),("rId3","presProps","presProps.xml"),("rId4","viewProps","viewProps.xml"),("rId5","tableStyles","tableStyles.xml")]+[(f"rId{i+5}","slide",f"slides/slide{i}.xml") for i in range(1,n+1)]
   z.writestr("ppt/_rels/presentation.xml.rels",rels(pr))
   z.writestr("ppt/presentation.xml",XML+f'<p:presentation xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst><p:sldIdLst>'+''.join(f'<p:sldId id="{255+i}" r:id="rId{i+5}"/>' for i in range(1,n+1))+f'</p:sldIdLst><p:sldSz cx="{emu(1280)}" cy="{emu(720)}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle/></p:presentation>')
   z.writestr("ppt/presProps.xml",XML+f'<p:presentationPr xmlns:p="{P}"/>')
   z.writestr("ppt/viewProps.xml",XML+f'<p:viewPr xmlns:p="{P}" lastView="slideView"><p:normalViewPr/><p:gridSpacing cx="91440" cy="91440"/></p:viewPr>')
   z.writestr("ppt/tableStyles.xml",XML+f'<a:tblStyleLst xmlns:a="{A}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>')
   z.writestr("ppt/theme/theme1.xml",theme())
   z.writestr("ppt/slideMasters/slideMaster1.xml",XML+f'<p:sldMaster xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'+group()+'</p:spTree></p:cSld>'+cmap+'<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>')
   z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",rels([("rId1","slideLayout","../slideLayouts/slideLayout1.xml"),("rId2","theme","../theme/theme1.xml")]))
   z.writestr("ppt/slideLayouts/slideLayout1.xml",XML+f'<p:sldLayout xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree>'+group()+'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
   z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels",rels([("rId1","slideMaster","../slideMasters/slideMaster1.xml")]))
   z.writestr("ppt/notesMasters/notesMaster1.xml",XML+f'<p:notesMaster xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'+group()+'</p:spTree></p:cSld>'+cmap+'<p:notesStyle/></p:notesMaster>')
   z.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels",rels([("rId1","theme","../theme/theme1.xml")]))
   for i,s in enumerate(self.slides,1):
    z.writestr(f"ppt/slides/slide{i}.xml",s.xml(i))
    z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels",rels([("rIdLayout","slideLayout","../slideLayouts/slideLayout1.xml"),("rIdNotes","notesSlide",f"../notesSlides/notesSlide{i}.xml")]+s.relationships))
    z.writestr(f"ppt/notesSlides/notesSlide{i}.xml",notes_xml(s.notes))
    z.writestr(f"ppt/notesSlides/_rels/notesSlide{i}.xml.rels",rels([("rId1","notesMaster","../notesMasters/notesMaster1.xml"),("rId2","slide",f"../slides/slide{i}.xml")]))
   for i,c in enumerate(self.charts,1):
    z.writestr(f"ppt/charts/chart{i}.xml",chart_xml(c,i))
    z.writestr(f"ppt/charts/_rels/chart{i}.xml.rels",rels([("rId1","package",f"../embeddings/data{i}.xlsx")]))
    z.writestr(f"ppt/embeddings/data{i}.xlsx",xlsx(c))
  (path.parent/"deck_manifest.json").write_text(json.dumps([dict(slide=i,title=s.title,notes=s.notes,objects=s.objects) for i,s in enumerate(self.slides,1)],ensure_ascii=False,indent=2))
  print(json.dumps(dict(path=str(path),slides=n,native_charts=len(self.charts),native_tables=sum(o["type"]=="table" for s in self.slides for o in s.objects)),ensure_ascii=False))
