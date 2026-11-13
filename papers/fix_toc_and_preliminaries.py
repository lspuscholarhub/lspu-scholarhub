"""Fix the Table of Contents and add Preliminaries heading."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from copy import deepcopy

INPUT = r'C:\Users\kirit\Downloads\[09_12_26] LSPU ScholarHub 1-5.docx'
OUTPUT = r'C:\Users\kirit\Downloads\LSPU_ScholarHub_1-5_FIXED.docx'

doc = Document(INPUT)

# ─── Step 1: Add "Preliminaries" heading before LIST OF TABLES ───
# Find the paragraph index for LIST OF TABLES (should be around 132)
lot_index = None
for i, p in enumerate(doc.paragraphs):
    if p.text.strip() == 'LIST OF TABLES' and p.style.name.startswith('Heading'):
        lot_index = i
        break

print(f"Found LIST OF TABLES at paragraph {lot_index}")

if lot_index is not None:
    # Insert a 'Preliminaries' heading paragraph before LIST OF TABLES
    # We need to insert it in the XML element
    lot_para = doc.paragraphs[lot_index]
    lot_elem = lot_para._element
    
    # Create new paragraph element
    from docx.oxml.ns import qn
    from lxml import etree
    
    # Create the new paragraph
    new_p = etree.SubElement(lot_elem.getparent(), qn('w:p'))
    # Move it before the LIST OF TABLES element
    lot_elem.getparent().insert(list(lot_elem.getparent()).index(lot_elem), new_p)
    
    # Add run with text
    new_r = etree.SubElement(new_p, qn('w:r'))
    new_t = etree.SubElement(new_r, qn('w:t'))
    new_t.text = 'Preliminaries'
    new_t.set(qn('xml:space'), 'preserve')
    
    # Set the style to Heading 1
    pPr = etree.SubElement(new_p, qn('w:pPr'))
    pStyle = etree.SubElement(pPr, qn('w:pStyle'))
    pStyle.set(qn('w:val'), 'Heading1')
    
    print("Added 'Preliminaries' heading before LIST OF TABLES")

# ─── Step 2: Fix the Table of Contents ───
# Find the TOC heading and the entries after it
toc_heading_idx = None
for i, p in enumerate(doc.paragraphs):
    if p.text.strip() == 'TABLE OF CONTENTS' and p.style.name.startswith('Heading'):
        toc_heading_idx = i
        break

print(f"Found TABLE OF CONTENTS heading at paragraph {toc_heading_idx}")

if toc_heading_idx is not None:
    # Find where TOC entries end (before the first Heading 1 after TOC, which is CHAPTER I in the TOC)
    toc_end_idx = None
    for i in range(toc_heading_idx + 1, min(toc_heading_idx + 60, len(doc.paragraphs))):
        p = doc.paragraphs[i]
        if p.text.strip().startswith('CHAPTER I') and p.style.name.startswith('Heading'):
            toc_end_idx = i
            break
    
    if toc_end_idx is None:
        # Try to find the end by looking for empty paragraphs or the next section
        for i in range(toc_heading_idx + 1, min(toc_heading_idx + 60, len(doc.paragraphs))):
            p = doc.paragraphs[i]
            if p.style.name.startswith('Heading') and p.text.strip():
                toc_end_idx = i
                break
    
    print(f"TOC entries span from {toc_heading_idx + 1} to {toc_end_idx}")
    
    # Remove old TOC entries
    if toc_end_idx is not None:
        # We need to remove paragraphs from toc_heading_idx + 1 to toc_end_idx - 1
        for i in range(toc_end_idx - 1, toc_heading_idx, -1):
            p = doc.paragraphs[i]
            p._element.getparent().remove(p._element)
    
    # Now insert new TOC entries after the TOC heading
    toc_heading_para = doc.paragraphs[toc_heading_idx]
    toc_elem = toc_heading_para._element
    parent = toc_elem.getparent()
    insert_pos = list(parent).index(toc_elem) + 1
    
    # Define the new TOC content
    toc_entries = [
        ("Preliminaries", "Heading 2", True),
        ("    Title Page", "Normal", False),
        ("    Vision, Mission, and Quality Policy", "Normal", False),
        ("    Approval Sheet", "Normal", False),
        ("    Acknowledgement", "Normal", False),
        ("    Abstract", "Normal", False),
        ("    Table of Contents", "Normal", False),
        ("    List of Tables", "Normal", False),
        ("    List of Figures", "Normal", False),
        ("    List of Appendices", "Normal", False),
        ("    Definition of Terms", "Normal", False),
        ("", "Normal", False),  # blank line
        ("CHAPTER I: INTRODUCTION AND BACKGROUND", "Heading 2", True),
        ("    Project Context", "Normal", False),
        ("    Research Objectives", "Normal", False),
        ("    Project Purpose", "Normal", False),
        ("    Conceptual Framework", "Normal", False),
        ("    Scope and Limitation of the Study", "Normal", False),
        ("", "Normal", False),
        ("CHAPTER II: REVIEW OF RELATED LITERATURE", "Heading 2", True),
        ("    Digital Transformation in Higher Education", "Normal", False),
        ("    Database Management and System Scalability", "Normal", False),
        ("    Artificial Intelligence and Chatbot Technologies", "Normal", False),
        ("    Notification Systems and Digital Communication", "Normal", False),
        ("    Related Systems", "Normal", False),
        ("    Synthesis of the Reviewed Literature and Systems", "Normal", False),
        ("    Technology Gap Analysis", "Normal", False),
        ("", "Normal", False),
        ("CHAPTER III: RESEARCH METHODOLOGY", "Heading 2", True),
        ("    Materials and Methods", "Normal", False),
        ("    Research Design", "Normal", False),
        ("    Population of the Study", "Normal", False),
        ("    Sampling Design", "Normal", False),
        ("    Data Collection Instrument", "Normal", False),
        ("    Project Design", "Normal", False),
        ("    System Testing and Evaluation Procedure", "Normal", False),
        ("    System Testing", "Normal", False),
        ("    System User Evaluation", "Normal", False),
        ("    Ethical Considerations", "Normal", False),
        ("    Statistical Treatment", "Normal", False),
        ("", "Normal", False),
        ("CHAPTER IV: RESULTS AND DISCUSSION", "Heading 2", True),
        ("    General Presentation of Results", "Normal", False),
        ("    Presentation of Objective-Based Results", "Normal", False),
        ("    System Architecture and Development Results", "Normal", False),
        ("    System Testing Results", "Normal", False),
        ("    Discussion of Testing Results", "Normal", False),
        ("    System User Evaluation", "Normal", False),
        ("    Discussion and Interpretation of Findings", "Normal", False),
        ("", "Normal", False),
        ("CHAPTER V: SUMMARY, CONCLUSIONS, AND RECOMMENDATIONS", "Heading 2", True),
        ("    Summary", "Normal", False),
        ("    Conclusions", "Normal", False),
        ("    Recommendations", "Normal", False),
        ("", "Normal", False),
        ("References", "Normal", False),
        ("Appendices", "Normal", False),
    ]
    
    # Insert new paragraphs
    for text, style_name, is_chapter in reversed(toc_entries):
        new_p = etree.SubElement(parent, qn('w:p'))
        parent.insert(insert_pos, new_p)
        
        if text:
            new_r = etree.SubElement(new_p, qn('w:r'))
            
            if is_chapter:
                # Bold for chapter headings
                rPr = etree.SubElement(new_r, qn('w:rPr'))
                b = etree.SubElement(rPr, qn('w:b'))
                
                new_t = etree.SubElement(new_r, qn('w:t'))
                new_t.text = text
                new_t.set(qn('xml:space'), 'preserve')
                
                # Set style
                pPr = etree.SubElement(new_p, qn('w:pPr'))
                pStyle = etree.SubElement(pPr, qn('w:pStyle'))
                pStyle.set(qn('w:val'), style_name)
            else:
                new_t = etree.SubElement(new_r, qn('w:t'))
                new_t.text = text
                new_t.set(qn('xml:space'), 'preserve')
    
    print("Inserted new TOC entries")

# ─── Step 3: Save ───
doc.save(OUTPUT)
print(f"\nSaved to: {OUTPUT}")

# Verify
doc2 = Document(OUTPUT)
print("\n=== VERIFICATION ===")
for i, p in enumerate(doc2.paragraphs):
    if p.style.name.startswith('Heading') and p.text.strip():
        print(f"  [{i}] {p.style.name}: \"{p.text[:120]}\"")
    if i > 200:
        break
