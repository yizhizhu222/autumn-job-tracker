"""Conservative single-line replacements; reject edits that cannot preserve layout."""
from collections import Counter
from pathlib import Path
import os
import re


def compact(value): return re.sub(r'\s+','',value)


def export_pdf(source, target, edits):
    try: import pymupdf as fitz
    except ImportError: raise ValueError('导出PDF需要安装 requirements-ai.txt 中的 PyMuPDF')
    doc=fitz.open(source)
    try:
        original=''.join(p.get_text() for p in doc)
        plans=[]
        for edit in edits:
            if '\n' in edit['before'] or '\n' in edit['after']:
                raise ValueError('PDF只支持单行微调，跨行修改请先保存正文')
            hits=[(p.number,r) for p in doc for r in p.search_for(edit['before'])]
            if len(hits)!=1: raise ValueError('PDF中无法唯一定位到一行，保留原版式并停止导出')
            pn,rect=hits[0];page=doc[pn]
            spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans'] if fitz.Rect(s['bbox']).intersects(rect)]
            if not spans: raise ValueError('无法读取该行排版信息')
            span=spans[0];base=float(span['size']);font='china-s' if any(ord(c)>255 for c in edit['after']) else 'helv'
            natural=fitz.get_text_length(edit['after'],fontname=font,fontsize=base)
            size=min(base,base*(rect.width/max(natural,1)))
            if size<base*0.85: raise ValueError('新文字放不下原位置，请缩短措辞后重试')
            if any(p[0]==pn and p[1].intersects(rect) for p in plans): raise ValueError('修改区域重叠')
            color=span.get('color',0)
            rgb=tuple(((color>>shift)&255)/255 for shift in (16,8,0))
            plans.append((pn,rect,edit,size,font,float(span['origin'][1]),rgb))
        for pn,rect,*_ in plans: doc[pn].add_redact_annot(rect,fill=False,cross_out=False)
        for pn in {p[0] for p in plans}: doc[pn].apply_redactions(images=0,graphics=0)
        for pn,rect,edit,size,font,baseline,rgb in plans:
            doc[pn].insert_text((rect.x0,baseline),edit['after'],fontsize=size,fontname=font,color=rgb)
        expected=Counter(compact(original))
        for e in edits:
            expected.subtract(Counter(compact(e['before'])));expected.update(Counter(compact(e['after'])))
        actual=Counter(compact(''.join(p.get_text() for p in doc)))
        if +expected != actual: raise ValueError('文字完整性校验未通过，停止导出，原件未改动')
        target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_suffix('.tmp')
        try: doc.save(tmp,garbage=4,deflate=True);os.replace(tmp,target)
        finally:
            if tmp.exists(): tmp.unlink()
    finally: doc.close()
