import hashlib
import tempfile
import unittest
from pathlib import Path
try: import pymupdf as fitz
except ImportError: fitz=None
from resume_pdf import export_pdf


@unittest.skipUnless(fitz,'optional PDF dependency not installed')
class PdfTests(unittest.TestCase):
    def test_single_line_edit_preserves_original_and_other_content(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'original.pdf';target=Path(temp)/'edited.pdf'
            doc=fitz.open();page=doc.new_page()
            page.insert_text((50,70),'Resume: 2027',fontsize=15)
            page.insert_text((50,120),'负责项目文档整理并协助团队沟通。',fontname='china-s',fontsize=11)
            page.insert_text((50,150),'Education: bachelor',fontsize=11)
            doc.save(source);doc.close();before=source.read_bytes()
            export_pdf(source,target,[{'before':'负责项目文档整理并协助团队沟通。','after':'整理项目文档，协助团队沟通。'}])
            with fitz.open(target) as changed:
                self.assertEqual(len(changed),1)
                text=changed[0].get_text()
                self.assertIn('Education: bachelor',text)
                self.assertIn('整理项目文档，协助团队沟通。',text)
                self.assertNotIn('负责项目文档整理并协助团队沟通。',text)
            self.assertEqual(source.read_bytes(),before)
    def test_ambiguous_or_oversized_edits_fail_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'original.pdf';target=Path(temp)/'edited.pdf'
            doc=fitz.open();p=doc.new_page();p.insert_text((50,70),'Short line');doc.save(source);doc.close()
            with self.assertRaises(ValueError): export_pdf(source,target,[{'before':'Short line','after':'This replacement is far too long for the available box'}])
            self.assertFalse(target.exists())
