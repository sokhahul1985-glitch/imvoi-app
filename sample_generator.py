"""
Sample Test Document Generator for Thai Passport, Cambodian Passport, and Name List
Generates realistic PIL Images with Thai, English, and Khmer text for 1-Click testing.
"""

from PIL import Image, ImageDraw, ImageFont
import os


def generate_thai_passport_sample():
    """
    Generates a realistic Thai Passport sample image with Thai and English text + MRZ line.
    """
    w, h = 800, 520
    img = Image.new('RGB', (w, h), color='#1e293b')
    draw = ImageDraw.Draw(img)

    # Header Passport Cover style background
    draw.rectangle([(0, 0), (w, 60)], fill='#0f172a')
    draw.rectangle([(0, h - 70), (w, h)], fill='#0f172a')

    # Passport Header Text
    draw.text((30, 15), "KINGDOM OF THAILAND / ประเทศไทย", fill='#fbbf24')
    draw.text((600, 15), "PASSPORT / หนังสือเดินทาง", fill='#ffffff')

    # Photo Box
    draw.rectangle([(40, 90), (250, 380)], fill='#334155', outline='#6366f1', width=3)
    draw.ellipse([(100, 130), (190, 240)], fill='#64748b')
    draw.rectangle([(80, 240), (210, 360)], fill='#475569')
    draw.text((105, 340), "PASSPORT PHOTO", fill='#cbd5e1')

    # Passport Field Labels & Data (Thai + English)
    fields = [
        ("Type / ประเภท", "P", "Country Code / ประเทศ", "THA"),
        ("Passport No. / หนังสือเดินทางเลขที่", "AA9876543", "Personal No.", "1509901234567"),
        ("Surname / นามสกุล", "SUWANNAKOT", "", ""),
        ("Thai Name / ชื่อ-นามสกุล (ภาษาไทย)", "นาย สมชาย สุวรรณโคตร", "", ""),
        ("Given Names / ชื่อ 지정", "SOMCHAI", "", ""),
        ("Nationality / สัญชาติ", "THAI", "Sex / เพศ", "M"),
        ("Date of birth / วันเกิด", "15 AUG 1988", "Place of birth", "BANGKOK"),
        ("Date of issue / วันออกหนังสือ", "10 JAN 2022", "Date of expiry / วันหมดอายุ", "09 JAN 2032")
    ]

    x_start = 280
    y_start = 85
    y_offset = 0

    for label1, val1, label2, val2 in fields:
        # Field 1
        draw.text((x_start, y_start + y_offset), label1, fill='#94a3b8')
        draw.text((x_start, y_start + y_offset + 16), val1, fill='#ffffff')
        
        # Field 2 (if present)
        if label2:
            draw.text((x_start + 260, y_start + y_offset), label2, fill='#94a3b8')
            draw.text((x_start + 260, y_start + y_offset + 16), val2, fill='#38bdf8')
            
        y_offset += 38

    # Machine Readable Zone (MRZ)
    mrz_line1 = "P<THASUWANNAKOT<<SOMCHAI<<<<<<<<<<<<<<<<<<<<"
    mrz_line2 = "AA98765434THA8808154M32010991509901234567<52"
    draw.text((40, h - 55), mrz_line1, fill='#34d399')
    draw.text((40, h - 30), mrz_line2, fill='#34d399')

    return img


def generate_khmer_passport_sample():
    """
    Generates a Cambodian Passport sample image with Khmer & English text.
    """
    w, h = 800, 520
    img = Image.new('RGB', (w, h), color='#1e293b')
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (w, 60)], fill='#1e1b4b')
    draw.rectangle([(0, h - 70), (w, h)], fill='#1e1b4b')

    draw.text((30, 15), "KINGDOM OF CAMBODIA / ព្រះរាជាណាចក្រកម្ពុជា", fill='#fbbf24')
    draw.text((600, 15), "PASSPORT / លិខិតឆ្លងដែន", fill='#ffffff')

    # Photo Box
    draw.rectangle([(40, 90), (250, 380)], fill='#334155', outline='#10b981', width=3)
    draw.ellipse([(100, 130), (190, 240)], fill='#475569')
    draw.rectangle([(80, 240), (210, 360)], fill='#334155')

    fields = [
        ("Passport No. / លេខលិខិតឆ្លងដែន", "N01234567", "Country Code", "KHM"),
        ("Surname / ត្រកូល", "CHAN", "", ""),
        ("Given Names / ឈ្មោះ", "SOTHEA", "", ""),
        ("Khmer Name / ឈ្មោះជាភាសាខ្មែរ", "ចាន់ សុធា", "", ""),
        ("Nationality / សញ្ជាតិ", "CAMBODIAN", "Sex / ភេទ", "M"),
        ("Date of birth / ថ្ងៃខែឆ្នាំកំណើត", "20 MAY 1995", "Place of birth", "PHNOM PENH"),
        ("Date of expiry / ថ្ងៃផុតកំណត់", "15 MAY 2030", "Authority", "PASSPORT DEPT")
    ]

    x_start = 280
    y_start = 85
    y_offset = 0

    for label1, val1, label2, val2 in fields:
        draw.text((x_start, y_start + y_offset), label1, fill='#94a3b8')
        draw.text((x_start, y_start + y_offset + 16), val1, fill='#ffffff')
        if label2:
            draw.text((x_start + 260, y_start + y_offset), label2, fill='#94a3b8')
            draw.text((x_start + 260, y_start + y_offset + 16), val2, fill='#38bdf8')
        y_offset += 40

    mrz_line1 = "P<KHMCHAN<<SOTHEA<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    mrz_line2 = "N012345674KHM9505204M3005159<<<<<<<<<<<<<<04"
    draw.text((40, h - 55), mrz_line1, fill='#34d399')
    draw.text((40, h - 30), mrz_line2, fill='#34d399')

    return img
