"""
CMP Golden Mekong Commercial Service Official Invoice Generator.
Supports Unicode Thai & Khmer fonts via Pillow and ReportLab.
"""

import os
import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def get_khmer_font_path(bold=False):
    candidates = [
        r"C:\Windows\Fonts\khmeruib.ttf" if bold else r"C:\Windows\Fonts\khmerui.ttf",
        r"C:\Windows\Fonts\KhmerOSmuol.ttf" if bold else r"C:\Windows\Fonts\KhmerOSbattambang.ttf",
        r"C:\Windows\Fonts\KhmerOS.ttf",
        r"C:\Windows\Fonts\daunpenh.ttf",
        r"C:\Windows\Fonts\KhmerOSsiemreap.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_thai_font_path(bold=False):
    candidates = [
        r"C:\Windows\Fonts\tahomabd.ttf" if bold else r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\leelawadb.ttf" if bold else r"C:\Windows\Fonts\leelawad.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_system_font_path():
    return get_khmer_font_path() or get_thai_font_path()


def get_pil_font(size=14, bold=False):
    font_path = get_khmer_font_path(bold=bold) or get_thai_font_path(bold=bold) or get_system_font_path()
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# Register Dual-Font Unicode System for ReportLab PDF (Thai + Khmer)
REPORTLAB_UNICODE_FONT = None
REPORTLAB_THAI_FONT = None
REPORTLAB_KHMER_FONT = None

if REPORTLAB_AVAILABLE:
    _thai_font = get_thai_font_path()
    _khmer_font = get_khmer_font_path()
    _thai_bold = get_thai_font_path(bold=True)
    _khmer_bold = get_khmer_font_path(bold=True)

    if _thai_font:
        try:
            pdfmetrics.registerFont(TTFont('ThaiFont', _thai_font))
            pdfmetrics.registerFont(TTFont('ThaiFontBold', _thai_bold or _thai_font))
            REPORTLAB_THAI_FONT = 'ThaiFont'
        except Exception as e:
            print(f"ReportLab Thai font notice: {e}")

    if _khmer_font:
        try:
            pdfmetrics.registerFont(TTFont('KhmerFont', _khmer_font))
            pdfmetrics.registerFont(TTFont('KhmerFontBold', _khmer_bold or _khmer_font))
            REPORTLAB_KHMER_FONT = 'KhmerFont'
        except Exception as e:
            print(f"ReportLab Khmer font notice: {e}")

    REPORTLAB_UNICODE_FONT = REPORTLAB_KHMER_FONT or REPORTLAB_THAI_FONT or 'Helvetica'


import json
import re


def format_multilingual_html(text, bold=False):
    """
    Formates mixed Thai & Khmer Unicode text into HTML font tags for ReportLab Paragraphs.
    """
    if not text:
        return ""
    str_text = str(text)
    thai_font_name = 'ThaiFontBold' if (bold and REPORTLAB_THAI_FONT) else (REPORTLAB_THAI_FONT or 'Helvetica')
    khmer_font_name = 'KhmerFontBold' if (bold and REPORTLAB_KHMER_FONT) else (REPORTLAB_KHMER_FONT or 'Helvetica')

    parts = re.split(r'([\u0e00-\u0e7f]+|[\u1780-\u17ff]+)', str_text)
    res = []
    for part in parts:
        if not part:
            continue
        if re.search(r'[\u1780-\u17ff]', part):
            res.append(f'<font name="{khmer_font_name}">{part}</font>')
        elif re.search(r'[\u0e00-\u0e7f]', part):
            res.append(f'<font name="{thai_font_name}">{part}</font>')
        else:
            res.append(part)
    return ''.join(res)


def draw_multilingual_text(draw, xy, text, size=13, bold=False, fill='#000000'):
    """
    Renders mixed Thai & Khmer text on Pillow Image Canvas using dynamic script font switching.
    """
    if not text:
        return xy[0]

    khmer_path = get_khmer_font_path(bold=bold) or get_khmer_font_path()
    thai_path = get_thai_font_path(bold=bold) or get_thai_font_path()

    f_khmer = ImageFont.truetype(khmer_path, size) if khmer_path else ImageFont.load_default()
    f_thai = ImageFont.truetype(thai_path, size) if thai_path else ImageFont.load_default()
    f_def = f_khmer or f_thai

    x, y = xy
    parts = re.split(r'([\u0e00-\u0e7f]+|[\u1780-\u17ff]+)', str(text))
    for part in parts:
        if not part:
            continue
        if re.search(r'[\u1780-\u17ff]', part):
            font = f_khmer
        elif re.search(r'[\u0e00-\u0e7f]', part):
            font = f_thai
        else:
            font = f_def

        draw.text((x, y), part, font=font, fill=fill)
        try:
            bbox = font.getbbox(part)
            w_part = bbox[2] - bbox[0]
        except Exception:
            w_part = len(part) * (size * 0.6)
        x += w_part
    return x

class InvoiceNumberManager:
    """
    Manages persistent auto-incrementing invoice numbers (e.g. INV 0173, INV 0174...).
    """
    COUNTER_FILE = r"c:\Users\LEC\Desktop\Imvoi\invoice_counter.json"

    @classmethod
    def get_current_number(cls) -> int:
        if os.path.exists(cls.COUNTER_FILE):
            try:
                with open(cls.COUNTER_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return int(data.get("last_number", 0))
            except Exception:
                pass
        return 0

    @classmethod
    def get_next_invoice_no(cls) -> str:
        curr = cls.get_current_number()
        return f"INV {curr + 1:05d}"

    @classmethod
    def increment_invoice_no(cls, used_no=None) -> str:
        curr = cls.get_current_number()
        next_num = curr + 1
        if used_no and isinstance(used_no, str):
            digits = re.findall(r'\d+', used_no)
            if digits:
                parsed = int(digits[-1])
                if parsed >= next_num:
                    next_num = parsed

        try:
            with open(cls.COUNTER_FILE, 'w', encoding='utf-8') as f:
                json.dump({"last_number": next_num, "prefix": "INV "}, f, indent=2)
        except Exception as e:
            print(f"Error saving invoice counter: {e}")

        return f"INV {next_num:05d}"


class ReceiptGenerator:
    """
    Generates printable Golden Mekong Commercial Service (CMP) Invoices with full Thai & Khmer Unicode support.
    """

    @staticmethod
    def generate_receipt_data(customer_info, fee_details, receipt_no=None):
        """
        Build structured invoice data dictionary for Single Customer.
        """
        cust_name = (
            customer_info.get("full_english_name") or
            customer_info.get("english_name") or
            customer_info.get("khmer_name") or
            customer_info.get("thai_name") or
            "HR(CS)- แอน"
        ).strip()
        travel_dt = customer_info.get("travel_date") or customer_info.get("dob")
        if travel_dt and travel_dt.strip():
            date_str = travel_dt.strip()
        else:
            date_str = datetime.datetime.now().strftime("%d-%m-%Y")

        if receipt_no and str(receipt_no).strip():
            inv_no = str(receipt_no).strip()
        else:
            inv_no = InvoiceNumberManager.get_next_invoice_no()

        e_visa = float(fee_details.get("e_visa", 0.0))
        vip = float(fee_details.get("vip_fee", 0.0))
        overstay = float(fee_details.get("overstay_fee", 0.0))
        car_fee = float(fee_details.get("car_fee") or fee_details.get("visa_fee", 0.0))
        if not car_fee and not (e_visa or vip or overstay):
            car_fee = float(fee_details.get("visa_fee", 60.0))
        clearance_fee = float(fee_details.get("clearance_fee") or fee_details.get("work_permit", 0.0))

        rate = float(fee_details.get("exchange_rate", 33.9))

        items = [{
            "no": 1,
            "description": cust_name,
            "qty": "1",
            "e_visa": f"${e_visa:.0f}" if e_visa else "",
            "vip": f"${vip:.0f}" if vip else "",
            "overstay": f"${overstay:.0f}" if overstay else "",
            "car_fee": f"${car_fee:.0f}" if car_fee else "",
            "visa": f"${car_fee:.0f}" if car_fee else "",
            "clearance_fee": f"${clearance_fee:.0f}" if clearance_fee else "",
            "work_permit": f"${clearance_fee:.0f}" if clearance_fee else "",
            "usd": e_visa + vip + overstay + car_fee + clearance_fee
        }]

        tot_usd = sum(item["usd"] for item in items)
        tot_baht = tot_usd * rate

        return {
            "customer_name": cust_name,
            "agency_company": "",
            "date_str": date_str,
            "receipt_no": inv_no,
            "exchange_rate": rate,
            "items": items,
            "totals": {
                "usd": tot_usd,
                "baht": tot_baht
            }
        }

    @staticmethod
    def generate_group_receipt_data(group_info, members_list, fee_details, receipt_no=None):
        """
        Build structured invoice data dictionary for Group / Batch Customers.
        Extracts clean sender / customer name without generic 'VIP Group | ' prefixes.
        """
        sender = (group_info.get("sender_name") or "").strip()
        customer = (group_info.get("customer_name") or "").strip()
        group_nm = (group_info.get("group_name") or "").strip()

        # Clean up pipe '|' if formatted as "VIP Group | NATTEEYA MALIKUN"
        if "|" in sender:
            sender = sender.split("|")[-1].strip()
        if "|" in customer:
            customer = customer.split("|")[-1].strip()

        # Determine clean sender / customer name directly
        if sender and sender not in ["VIP Group", "Group", "VIP GROUP", ""]:
            display_cust_name = sender
        elif customer and customer not in ["VIP Group", "Group", "VIP GROUP", ""]:
            display_cust_name = customer
        elif members_list and len(members_list) > 0:
            first_m = (members_list[0].get("full_english_name") or members_list[0].get("english_name") or "").strip()
            if "|" in first_m:
                first_m = first_m.split("|")[-1].strip()
            display_cust_name = first_m if (first_m and not first_m.startswith("PASSENGER") and not first_m.startswith("CUSTOMER")) else (group_nm or "HR(CS)- แอน")
        else:
            display_cust_name = group_nm or "HR(CS)- แอน"

        agency = group_info.get("agency_company", "")
        date_str = group_info.get("travel_date") or datetime.datetime.now().strftime("%d-%m-%Y")

        if receipt_no and str(receipt_no).strip():
            inv_no = str(receipt_no).strip()
        elif group_info.get("receipt_no"):
            inv_no = str(group_info.get("receipt_no")).strip()
        else:
            inv_no = InvoiceNumberManager.get_next_invoice_no()

        rate = float(fee_details.get("exchange_rate", 33.9))
        e_visa = float(fee_details.get("e_visa", 0.0))
        vip = float(fee_details.get("vip_fee", 0.0))
        overstay = float(fee_details.get("overstay_fee", 0.0))
        default_car_fee = float(fee_details.get("car_fee") or fee_details.get("visa_fee", 0.0))
        if not default_car_fee and not (e_visa or vip or overstay):
            default_car_fee = float(fee_details.get("visa_fee", 60.0))
        clearance_fee = float(fee_details.get("clearance_fee") or fee_details.get("work_permit", 0.0))

        items = []
        for idx, m in enumerate(members_list, 1):
            name = (
                m.get("full_english_name") or
                m.get("english_name") or
                m.get("khmer_name") or
                m.get("thai_name") or
                f"PASSENGER {idx}"
            ).strip()

            m_car = m.get("car_fee")
            if m_car is None:
                m_car = m.get("price") or m.get("visa_fee") or default_car_fee
            try:
                m_car = float(m_car)
            except (ValueError, TypeError):
                m_car = default_car_fee

            m_evisa = float(m.get("e_visa") if m.get("e_visa") is not None else e_visa)
            m_vip = float(m.get("vip") if m.get("vip") is not None else vip)
            m_clearance = float(m.get("clearance_fee") if m.get("clearance_fee") is not None else clearance_fee)
            m_overstay = float(m.get("overstay") if m.get("overstay") is not None else overstay)

            # Quantity per name should default to 1 for single passenger names
            raw_qty = str(m.get("qty") or "").strip()
            if not raw_qty or raw_qty in ["1", "2", "3"]:
                m_qty = "1"
            else:
                m_qty = raw_qty

            row_usd = m_car + m_evisa + m_vip + m_clearance + m_overstay

            items.append({
                "no": idx,
                "description": name,
                "qty": m_qty,
                "e_visa": f"${m_evisa:.0f}" if m_evisa else "",
                "vip": f"${m_vip:.0f}" if m_vip else "",
                "overstay": f"${m_overstay:.0f}" if m_overstay else "",
                "car_fee": f"${m_car:.0f}" if m_car else "",
                "visa": f"${m_car:.0f}" if m_car else "",
                "clearance_fee": f"${m_clearance:.0f}" if m_clearance else "",
                "work_permit": f"${m_clearance:.0f}" if m_clearance else "",
                "usd": row_usd
            })

        tot_usd = sum(item["usd"] for item in items)
        tot_baht = tot_usd * rate

        return {
            "customer_name": display_cust_name,
            "sender_name": sender,
            "group_customer_name": customer,
            "agency_company": agency,
            "date_str": date_str,
            "receipt_no": inv_no,
            "exchange_rate": rate,
            "items": items,
            "totals": {
                "usd": tot_usd,
                "baht": tot_baht
            }
        }

    @classmethod
    def export_pdf(cls, receipt_data, output_filepath):
        """
        Export CMP Invoice PDF document with dual Thai & Khmer Unicode font rendering guaranteed to fit strictly on 1 A4 page.
        """
        if not REPORTLAB_AVAILABLE:
            png_filepath = output_filepath.replace(".pdf", ".png")
            return cls.export_image(receipt_data, png_filepath)

        pdf_font = REPORTLAB_UNICODE_FONT or 'Helvetica'

        # Page margins optimized to guarantee 1 page
        doc = SimpleDocTemplate(
            output_filepath,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=15,
            bottomMargin=15
        )
        elements = []
        styles = getSampleStyleSheet()

        normal_style = ParagraphStyle('DocNorm', parent=styles['Normal'], fontName=pdf_font, fontSize=8.5, leading=10.5)
        bold_style = ParagraphStyle('DocBld', parent=styles['Normal'], fontName=pdf_font, fontSize=8.5, leading=10.5)
        center_title = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName=pdf_font, fontSize=13, alignment=1, leading=15)

        # 1. Header Title Block with Logo
        logo_path = r"c:\Users\LEC\Desktop\Imvoi\cmp_logo.png"
        logo_element = None
        if os.path.exists(logo_path):
            try:
                from reportlab.platypus import Image as RLImage
                logo_element = RLImage(logo_path, width=65, height=65)
            except Exception:
                logo_element = None

        company_title = format_multilingual_html("บริษัท โกลเด้น เมกง พาณิชย์ เซอร์วิส จำกัด", bold=True)
        header_text = Paragraph(
            f"<b><font color='#0a52be' size=13>{company_title}</font></b><br/>"
            "<font size=7.5 color='#475569'>Chamkar Dong, Dangkao, Phnom Penh, Cambodia<br/>"
            "Tel: 0888022656 / 081662083</font><br/><br/>"
            "<u><b><font size=13 color='#0f172a'>INVOICE</font></b></u>",
            center_title
        )

        if logo_element:
            h_table = Table([[logo_element, header_text]], colWidths=[75, 470])
            h_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (0,0), 'LEFT'),
                ('ALIGN', (1,0), (1,0), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
        else:
            h_table = Table([[header_text]], colWidths=[545])
            h_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))

        elements.append(h_table)
        elements.append(Spacer(1, 6))

        # 2. Customer & Bank Subheader (Plain text without yellow highlight)
        raw_cust_name = receipt_data.get("customer_name", "HR(CS)- แอน")
        formatted_cust = format_multilingual_html(raw_cust_name, bold=True)
        date_str = receipt_data.get("date_str", datetime.datetime.now().strftime("%d-%m-%Y"))
        inv_no = receipt_data.get("receipt_no", InvoiceNumberManager.get_next_invoice_no())

        scb_name = format_multilingual_html("ไทยพาณิชย์", bold=True)
        scb_acc = format_multilingual_html("หมายเลขบัญชี 6924007211", bold=False)
        scb_owner = format_multilingual_html("ชื่อ Mr.KHLORNG ORN", bold=False)

        sub_data = [
            [
                Paragraph(f"<b>Customer Name:</b> <b>{formatted_cust}</b><br/><b>Date:</b> {date_str}<br/><b>Invoice No :</b> <u>{inv_no}</u>", normal_style),
                Paragraph(f"<b>{scb_name}</b><br/><b>{scb_acc}</b><br/><b>{scb_owner}</b>", normal_style)
            ]
        ]
        sub_table = Table(sub_data, colWidths=[345, 200])
        sub_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1)
        ]))
        elements.append(sub_table)
        elements.append(Spacer(1, 6))

        # 3. 30-Row Portrait Table Grid (Guaranteed 1 Single Page)
        hdr_rate = format_multilingual_html("อัตรา\nแลกเงิน", bold=True)
        headers = [
            "No.", "DESCRIPTION", "Quantly\n/Pax", "E\nVISA", "VIP",
            "Over\nStay", "Car\nFee", "Clearance\nFee", hdr_rate, "Price In\nBaht"
        ]
        grid_data = [[Paragraph(f"<b>{h}</b>", bold_style) if isinstance(h, str) and '<font' in h else Paragraph(f"<b>{h}</b>", bold_style) for h in headers]]

        items = receipt_data.get("items", [])
        rate = receipt_data.get("exchange_rate", 33.9)

        # 30-row portrait table grid
        grid_rows_count = max(len(items), 30)

        for r_idx in range(1, grid_rows_count + 1):
            if r_idx <= len(items):
                item = items[r_idx - 1]
                desc_formatted = Paragraph(format_multilingual_html(item.get("description", "")), normal_style)
                row_usd = item.get("usd", 0.0)
                row_baht_str = f"{row_usd * rate:,.0f}" if row_usd > 0 else ""
                raw_qty = str(item.get("qty", "")).strip()
                item_qty = "1" if (raw_qty in ["2", "3"] or not raw_qty) else raw_qty
                grid_data.append([
                    str(r_idx),
                    desc_formatted,
                    item_qty,
                    item.get("e_visa", ""),
                    item.get("vip", ""),
                    item.get("overstay", ""),
                    item.get("car_fee") or item.get("visa", ""),
                    item.get("clearance_fee") or item.get("work_permit", ""),
                    "",
                    row_baht_str
                ])
            else:
                grid_data.append([str(r_idx), "", "", "", "", "", "", "", "", ""])

        tot_usd = receipt_data["totals"]["usd"]
        tot_baht = receipt_data["totals"]["baht"]

        # Summary Row
        grid_data.append([
            "", "Total", "", "", "", "", f"${tot_usd:.0f}", "", f"{rate:.1f}", f"฿ {tot_baht:,.0f}"
        ])

        col_widths = [22, 155, 40, 35, 30, 35, 38, 40, 50, 100]
        grid_table = Table(grid_data, colWidths=col_widths)

        summary_row_idx = grid_rows_count + 1

        table_style = [
            ('FONTNAME', (0,0), (-1,-1), pdf_font),
            ('FONTSIZE', (0,0), (-1,-1), 7.5),
            ('LEADING', (0,0), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#000000')),
            ('SPAN', (8, 1), (8, grid_rows_count)),
            ('BACKGROUND', (8, summary_row_idx), (8, summary_row_idx), colors.HexColor('#bfdbfe')),
            ('BACKGROUND', (9, summary_row_idx), (9, summary_row_idx), colors.HexColor('#e2e8f0')),
            ('ALIGN', (1, -1), (1, -1), 'RIGHT'),
            ('ALIGN', (6, -1), (6, -1), 'CENTER'),
            ('ALIGN', (8, -1), (-1, -1), 'CENTER'),
            ('ALIGN', (9, 1), (9, -1), 'RIGHT'),
            ('RIGHTPADDING', (9, 1), (9, -1), 4)
        ]
        grid_table.setStyle(TableStyle(table_style))
        elements.append(grid_table)
        elements.append(Spacer(1, 6))

        # 4. Footer & Signature
        sig_khmer = format_multilingual_html("ហុល សុខា", bold=True)
        footer_data = [
            [
                Paragraph(f"<b>Prepared by</b><br/><br/><i><u>hol sokha</u></i><br/><b>{sig_khmer}</b>", normal_style),
                Paragraph("<b>Account No. : 000490752</b><br/><b>Account Name: HOL SOKHA</b><br/><b>Bank Name : ABA Bank</b><br/><br/><b>CONTACT ME</b><br/><b>081662083</b>", normal_style)
            ]
        ]
        footer_table = Table(footer_data, colWidths=[270, 275])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1)
        ]))
        elements.append(footer_table)

        doc.build(elements)
        return output_filepath

    @classmethod
    def export_image(cls, receipt_data, output_filepath):
        """
        Generates a high-resolution PNG receipt image matching Golden Mekong CMP Invoice layout 100% with dual Thai & Khmer Unicode fonts.
        """
        items = receipt_data.get("items", [])
        grid_rows_count = max(len(items), 30)

        w, h = 850, 1180
        img = Image.new('RGB', (w, h), color='#ffffff')
        draw = ImageDraw.Draw(img)

        # Standard Fonts
        f_sub = get_pil_font(12)
        f_body = get_pil_font(13)
        f_bold = get_pil_font(13, True)
        f_header = get_pil_font(12, True)

        # 1. CMP Circle Logo (Top Left)
        logo_path = r"c:\Users\LEC\Desktop\Imvoi\cmp_logo.png"
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path).convert("RGBA")
                logo_img = logo_img.resize((105, 105), Image.Resampling.LANCZOS)
                img.paste(logo_img, (35, 15), logo_img)
            except Exception as e:
                print(f"Error pasting CMP logo: {e}")
        else:
            logo_cx, logo_cy, logo_r = 75, 70, 35
            draw.ellipse([(logo_cx - logo_r, logo_cy - logo_r), (logo_cx + logo_r, logo_cy + logo_r)], outline='#0a52be', width=4)
            draw.text((logo_cx - 18, logo_cy - 12), "CMP", font=get_pil_font(16, True), fill='#e11923')

        # 2. Header Text (Center)
        draw_multilingual_text(draw, (220, 18), "บริษัท โกลเด้น เมกง พาณิชย์ เซอร์วิส จำกัด", size=15, bold=True, fill='#0a52be')
        draw.text((230, 48), "Chamkar Dong, Dangkao, Phnom Penh, Cambodia", font=f_sub, fill='#475569')
        draw.text((310, 68), "Tel: 0888022656 / 081662083", font=f_sub, fill='#475569')

        draw.text((360, 98), "INVOICE", font=get_pil_font(15, True), fill='#0f172a')
        draw.line([(360, 122), (445, 122)], fill='#0a52be', width=2)

        # 3. Customer Info (Left) & Bank Info (Right) - Plain Text Without Yellow Box
        cust_name = receipt_data.get("customer_name", "HR(CS)- แอน")
        date_str = receipt_data.get("date_str", datetime.datetime.now().strftime("%d-%m-%Y"))
        inv_no = receipt_data.get("receipt_no", InvoiceNumberManager.get_next_invoice_no())

        draw.text((50, 150), "Customer Name :", font=f_body, fill='#000000')
        draw_multilingual_text(draw, (200, 150), cust_name, size=13, bold=True, fill='#000000')

        draw.text((50, 182), f"Date: {date_str}", font=f_body, fill='#000000')
        draw.text((50, 202), f"Invoice No      : {inv_no}", font=f_body, fill='#000000')

        # Right bank SCB
        draw_multilingual_text(draw, (640, 135), "ไทยพาณิชย์", size=13, bold=True, fill='#000000')
        draw_multilingual_text(draw, (590, 158), "หมายเลขบัญชี 6924007211", size=13, bold=False, fill='#000000')
        draw_multilingual_text(draw, (615, 180), "ชื่อ Mr.KHLORNG ORN", size=13, bold=False, fill='#000000')

        # 4. Table Grid Setup
        col_x = [35, 70, 335, 380, 425, 465, 515, 565, 625, 685, 815]
        y_top = 230
        row_h = 24

        # Draw Table Header
        draw.rectangle([(col_x[0], y_top), (col_x[-1], y_top + 34)], fill='#f1f5f9', outline='#000000', width=1)

        draw.text((42, y_top + 8), "No.", font=f_header, fill='#000000')
        draw.text((150, y_top + 8), "DESCRIPTION", font=f_header, fill='#000000')
        draw.text((340, y_top + 2), "Quantly\n/Pax", font=f_header, fill='#000000')
        draw.text((390, y_top + 2), "E\nVISA", font=f_header, fill='#000000')
        draw.text((432, y_top + 8), "VIP", font=f_header, fill='#000000')
        draw.text((472, y_top + 2), "Over\nStay", font=f_header, fill='#000000')
        draw.text((522, y_top + 2), "Car\nFee", font=f_header, fill='#000000')
        draw.text((570, y_top + 2), "Clearance\nFee", font=f_header, fill='#000000')
        draw_multilingual_text(draw, (635, y_top + 2), "อัตรา", size=12, bold=True, fill='#000000')
        draw_multilingual_text(draw, (635, y_top + 16), "แลกเงิน", size=12, bold=True, fill='#000000')
        draw.text((715, y_top + 2), "Price In\nBaht", font=f_header, fill='#000000')

        for cx in col_x:
            draw.line([(cx, y_top), (cx, y_top + 34)], fill='#000000', width=1)

        # Draw Dynamic Rows
        curr_y = y_top + 34
        grid_bottom_y = y_top + 34 + (grid_rows_count * row_h)
        rate = receipt_data.get("exchange_rate", 33.9)

        # Outer border rectangle for full table grid
        draw.rectangle([(col_x[0], curr_y), (col_x[-1], grid_bottom_y)], outline='#000000', width=1)

        # Draw vertical grid column lines
        for cx in col_x:
            draw.line([(cx, curr_y), (cx, grid_bottom_y)], fill='#000000', width=1)

        for r_idx in range(1, grid_rows_count + 1):
            if r_idx < grid_rows_count:
                line_y = curr_y + row_h
                # Left segment (cols 0..8)
                draw.line([(col_x[0], line_y), (col_x[8], line_y)], fill='#000000', width=1)
                # Right segment (cols 9..10)
                draw.line([(col_x[9], line_y), (col_x[10], line_y)], fill='#000000', width=1)

            draw.text((col_x[0] + 8, curr_y + 4), str(r_idx), font=f_body, fill='#000000')

            if r_idx <= len(items):
                item = items[r_idx - 1]
                draw_multilingual_text(draw, (col_x[1] + 8, curr_y + 4), item.get("description", "")[:40], size=13, bold=False, fill='#000000')
                raw_qty = str(item.get("qty", "")).strip()
                item_qty = "1" if (raw_qty in ["2", "3"] or not raw_qty) else raw_qty
                if item_qty:
                    draw.text((col_x[2] + 8, curr_y + 4), item_qty, font=f_body, fill='#000000')
                if item.get("e_visa"):
                    draw.text((col_x[3] + 4, curr_y + 4), item.get("e_visa"), font=f_body, fill='#000000')
                if item.get("vip"):
                    draw.text((col_x[4] + 4, curr_y + 4), item.get("vip"), font=f_body, fill='#000000')
                if item.get("overstay"):
                    draw.text((col_x[5] + 4, curr_y + 4), item.get("overstay"), font=f_body, fill='#000000')
                car_val = item.get("car_fee") or item.get("visa")
                if car_val:
                    draw.text((col_x[6] + 4, curr_y + 4), car_val, font=f_body, fill='#000000')
                clearance_val = item.get("clearance_fee") or item.get("work_permit")
                if clearance_val:
                    draw.text((col_x[7] + 4, curr_y + 4), clearance_val, font=f_body, fill='#000000')

                row_usd = item.get("usd", 0.0)
                if row_usd > 0:
                    row_baht_val = row_usd * rate
                    draw.text((col_x[9] + 15, curr_y + 4), f"{row_baht_val:,.0f}", font=f_body, fill='#000000')

            curr_y += row_h

        # Exchange rate column value centered in single merged cell
        rate_y_center = y_top + 34 + (grid_rows_count * row_h) // 2 - 8
        draw.text((col_x[8] + 12, rate_y_center), f"{rate:.1f}", font=f_bold, fill='#000000')

        # 5. Summary Row
        tot_usd = receipt_data["totals"]["usd"]
        tot_baht = receipt_data["totals"]["baht"]

        draw.rectangle([(col_x[0], curr_y), (col_x[-1], curr_y + 28)], outline='#000000', width=1)
        for cx in col_x:
            draw.line([(cx, curr_y), (cx, curr_y + 28)], fill='#000000', width=1)

        draw.text((col_x[1] + 100, curr_y + 6), "Total", font=f_bold, fill='#000000')
        draw.text((col_x[6] + 2, curr_y + 6), f"${tot_usd:.0f}", font=f_bold, fill='#000000')

        draw.rectangle([(col_x[8] + 1, curr_y + 1), (col_x[9] - 1, curr_y + 27)], fill='#dbeafe')
        draw.text((col_x[8] + 10, curr_y + 6), f"{rate:.1f}", font=f_bold, fill='#000000')

        draw.rectangle([(col_x[9] + 1, curr_y + 1), (col_x[10] - 1, curr_y + 27)], fill='#e2e8f0')
        draw_multilingual_text(draw, (col_x[9] + 15, curr_y + 6), f"฿  {tot_baht:,.0f}", size=13, bold=True, fill='#000000')

        # 6. Footer Payment & Signature Section
        fy = curr_y + 35
        draw.text((50, fy), "Prepared by", font=f_body, fill='#000000')
        draw.line([(50, fy + 40), (130, fy + 40)], fill='#000000', width=1)
        draw_multilingual_text(draw, (50, fy + 45), "ហុល សុខា", size=13, bold=True, fill='#000000')

        # ABA Bank Right Footer
        draw.text((580, fy), "Account No. :  000490752", font=f_bold, fill='#000000')
        draw.text((605, fy + 22), "Account Name:  HOL SOKHA", font=f_bold, fill='#000000')
        draw.text((615, fy + 44), "Bank Name :  ABA Bank", font=f_bold, fill='#000000')
        draw.text((620, fy + 72), "CONTACT ME", font=f_bold, fill='#000000')
        draw.text((630, fy + 94), "081662083", font=f_bold, fill='#000000')

        img.save(output_filepath)
        return output_filepath

    @classmethod
    def export_group_pdf(cls, group_receipt_data, output_filepath):
        return cls.export_pdf(group_receipt_data, output_filepath)

    @classmethod
    def export_group_image(cls, group_receipt_data, output_filepath):
        return cls.export_image(group_receipt_data, output_filepath)

