"""
PyQt6 Custom Components for Passport Scanner, Form Auto-Fill, and Receipt Calculator
"""

import os
import json
import csv
import datetime
import cv2
import numpy as np
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QDoubleSpinBox, QSpinBox, QFileDialog, QMessageBox,
    QDialog, QFrame, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage
from receipt_generator import InvoiceNumberManager
from ocr_engine import clean_person_name


class DirectNumberInput(QLineEdit):
    """
    QLineEdit optimized for direct numeric keyboard typing without spinbox buttons.
    Provides .value() and .setValue() API compatibility with QDoubleSpinBox.
    """
    valueChanged = pyqtSignal(float)

    def __init__(self, default_val=0.0, text_color="#38bdf8", parent=None):
        super().__init__(parent)
        self.text_color = text_color
        self.setStyleSheet(f"QLineEdit {{ background: #0f172a; color: {self.text_color}; font-weight: bold; border: 1px solid #334155; border-radius: 4px; padding: 4px 6px; font-size: 13px; }}")
        self.setValue(default_val)
        self.textChanged.connect(self._on_text_changed)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()

    def _on_text_changed(self, text):
        clean_text = text.replace("$", "").replace("฿", "").strip()
        try:
            val = float(clean_text) if clean_text else 0.0
        except ValueError:
            val = 0.0
        self.valueChanged.emit(val)

    def value(self) -> float:
        clean_text = self.text().replace("$", "").replace("฿", "").strip()
        try:
            return float(clean_text)
        except ValueError:
            return 0.0

    def setValue(self, val):
        if val is None or val == "" or val == 0 or val == 0.0:
            self.setText("")
        elif isinstance(val, (int, float)):
            if float(val) == int(val):
                self.setText(str(int(val)))
            else:
                self.setText(f"{float(val):.2f}")
        else:
            self.setText(str(val) if val is not None else "")


class ImageDropWidget(QFrame):
    """
    Drag and Drop Image Area & Document Preview Widget supporting single & batch images.
    """
    image_loaded = pyqtSignal(object)  # Emits single PIL Image or File Path
    batch_images_loaded = pyqtSignal(list)  # Emits list of file paths for batch OCR

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("imageDropWidget")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Title Label
        title = QLabel("📷 PASSPORT / ID IMAGE SCANNER")
        title.setProperty("class", "heading-2")
        layout.addWidget(title)

        # Image Display Area (Expanding to fill top space)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setText("📁 Drag & Drop Passport Image(s) Here\n(អាច Drag & Drop រូបភាព Passport 1 ឬច្រើនក្នុងពេលតែមួយ)\n\nឬចុចប៊ូតុងខាងក្រោមដើម្បី Upload / ថតកាមេរ៉ា")
        self.img_label.setStyleSheet("border: 2px dashed #475569; border-radius: 12px; background-color: #0f172a; color: #94a3b8; font-size: 14px; min-height: 280px;")
        self.img_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.img_label, 1)

        # Buttons Panel
        btn_layout = QHBoxLayout()
        self.upload_btn = QPushButton("📁 Select Image File(s)")
        self.webcam_btn = QPushButton("📹 WebCam Snap")

        self.upload_btn.setProperty("class", "primary-btn")

        btn_layout.addWidget(self.upload_btn)
        btn_layout.addWidget(self.webcam_btn)
        layout.addLayout(btn_layout)

        # Connect internal actions
        self.upload_btn.clicked.connect(self._browse_file)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            valid_files = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))]
            if len(valid_files) > 1:
                self.batch_images_loaded.emit(valid_files)
            elif len(valid_files) == 1:
                self.image_loaded.emit(valid_files[0])

    def _browse_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Passport Image(s)", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if file_paths:
            if len(file_paths) > 1:
                self.batch_images_loaded.emit(file_paths)
            else:
                self.image_loaded.emit(file_paths[0])

    def display_pil_image(self, pil_img):
        """
        Display PIL Image inside Qt Label.
        """
        cv_img = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        q_img = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.img_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.img_label.setPixmap(scaled_pixmap)


class CustomerFormWidget(QGroupBox):
    """
    Form fields automatically populated by OCR Document AI scanner.
    """
    save_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("👤 CUSTOMER DATA (ទិន្នន័យស្រង់ស្វ័យប្រវត្តិ)", parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Fields
        self.txt_english_name = QLineEdit()
        self.txt_english_name.setPlaceholderText("វាយបញ្ចូលឈ្មោះអតិថិជន / Full Customer Name (e.g. SOMCHAI SUWANNAKOT)")

        self.txt_travel_date = QLineEdit()
        self.txt_travel_date.setPlaceholderText("ថ្ងៃធ្វើដំណើរ / Travel Date (e.g. 29/07/2026)")

        self.txt_sex = QLineEdit()
        self.txt_sex.setPlaceholderText("Sex / Gender (M / F)")

        self.txt_nationality = QLineEdit()
        self.txt_nationality.setPlaceholderText("Nationality (e.g. THAI / CAMBODIAN)")

        # Form Layout Arrangement
        f1 = QHBoxLayout()
        f1.addWidget(QLabel("👤 ឈ្មោះអតិថិជន (Customer Name):"))
        f1.addWidget(self.txt_english_name)
        layout.addLayout(f1)

        f2 = QHBoxLayout()
        f2.addWidget(QLabel("🗓️ ថ្ងៃធ្វើដំណើរ (Travel Date):"))
        f2.addWidget(self.txt_travel_date)
        layout.addLayout(f2)

        f3 = QHBoxLayout()
        f3.addWidget(QLabel("👤 Sex:"))
        f3.addWidget(self.txt_sex)
        f3.addWidget(QLabel("🌐 Nationality:"))
        f3.addWidget(self.txt_nationality)
        layout.addLayout(f3)

        # Form Action Buttons
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("💾 រក្សាទុកទិន្នន័យ (Save Data)")
        self.btn_save.setProperty("class", "success-btn")

        self.btn_clear = QPushButton("🧹 សម្អាត Form (Clear)")
        self.btn_clear.setProperty("class", "warning-btn")

        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_clear)
        layout.addLayout(btn_box)

        self.btn_save.clicked.connect(self._emit_save)
        self.btn_clear.clicked.connect(self.clear_fields)

    def _emit_save(self):
        data = self.get_customer_data()
        self.save_requested.emit(data)

    def clear_fields(self):
        self.txt_english_name.clear()
        self.txt_travel_date.clear()
        self.txt_sex.clear()
        self.txt_nationality.clear()

    def populate_data(self, data):
        """
        Populates inputs and highlights modified fields.
        """
        name = (
            data.get("full_english_name") or
            data.get("english_name") or
            data.get("khmer_name") or
            data.get("thai_name") or
            ""
        ).strip()
        self.txt_english_name.setText(name)
        self.txt_travel_date.setText(data.get("travel_date") or data.get("dob", ""))
        self.txt_sex.setText(data.get("sex", ""))
        self.txt_nationality.setText(data.get("nationality", ""))

    def get_customer_data(self):
        """
        Return structured dictionary of customer details.
        """
        travel_dt = self.txt_travel_date.text().strip()
        name = self.txt_english_name.text().strip()
        return {
            "thai_name": "",
            "full_english_name": name,
            "english_name": name,
            "khmer_name": "",
            "passport_no": "",
            "travel_date": travel_dt,
            "dob": travel_dt,
            "sex": self.txt_sex.text().strip(),
            "nationality": self.txt_nationality.text().strip(),
            "agency_company": ""
        }





class ReceiptFeeWidget(QGroupBox):
    """
    CMP Golden Mekong Invoice Service Fees & Pricing Calculator.
    """
    download_pdf_requested = pyqtSignal()
    download_png_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("💵 INVOICE FEES & EXCHANGE RATE (គណនាថ្លៃសេវា និងអត្រាប្តូរប្រាក់)", parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Fee Inputs matching CMP Invoice columns (Direct keyboard typing inputs)
        self.spin_visa_fee = DirectNumberInput(0.0, text_color="#38bdf8")
        self.spin_visa_fee.setPlaceholderText("ថ្លៃឡាន ($)...")

        self.spin_evisa_fee = DirectNumberInput(0.0, text_color="#a855f7")
        self.spin_evisa_fee.setPlaceholderText("E-VISA ($)...")

        self.spin_vip_fee = DirectNumberInput(0.0, text_color="#f59e0b")
        self.spin_vip_fee.setPlaceholderText("VIP ($)...")

        self.spin_overstay_fee = DirectNumberInput(0.0, text_color="#ef4444")
        self.spin_overstay_fee.setPlaceholderText("Overstay ($)...")

        self.spin_work_permit = DirectNumberInput(0.0, text_color="#10b981")
        self.spin_work_permit.setPlaceholderText("ក្លៀវផ្លូវ ($)...")

        self.spin_exchange_rate = DirectNumberInput(33.9, text_color="#f8fafc")
        self.spin_exchange_rate.setPlaceholderText("Rate...")

        # Row 1: Car Fee & E-VISA
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("🚗 ថ្លៃឡាន (Car Fee):"))
        r1.addWidget(self.spin_visa_fee)
        r1.addWidget(QLabel("💻 ថ្លៃ E-VISA:"))
        r1.addWidget(self.spin_evisa_fee)
        layout.addLayout(r1)

        # Row 2: VIP & Overstay
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("👑 ថ្លៃ VIP:"))
        r2.addWidget(self.spin_vip_fee)
        r2.addWidget(QLabel("⏳ ថ្លៃ Overstay:"))
        r2.addWidget(self.spin_overstay_fee)
        layout.addLayout(r2)

        # Row 3: Clearance Fee & Exchange Rate
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("🛣️ ថ្លៃក្លៀវផ្លូវ (Clearance Fee):"))
        r3.addWidget(self.spin_work_permit)
        r3.addWidget(QLabel("🔱 អត្រាប្តូរប្រាក់ (Rate):"))
        r3.addWidget(self.spin_exchange_rate)
        layout.addLayout(r3)

        # Summary Display Panel
        summary_panel = QFrame()
        summary_panel.setProperty("class", "highlight-card")
        sp_layout = QVBoxLayout(summary_panel)

        self.lbl_total_usd = QLabel("TOTAL USD: $ 0.00")
        self.lbl_total_usd.setProperty("class", "stat-value")

        self.lbl_currencies = QLabel("PRICE IN BAHT (อัตรา 33.9): ฿ 0")
        sp_layout.addWidget(self.lbl_total_usd)
        sp_layout.addWidget(self.lbl_currencies)
        layout.addWidget(summary_panel)

        # Download Buttons
        btn_box = QHBoxLayout()
        self.btn_download_pdf = QPushButton("📄 ទាញយកវិក័យប័ត្រ (Download PDF)")
        self.btn_download_png = QPushButton("🖼️ ទាញយកវិក័យប័ត្រ (Download PNG)")

        self.btn_download_pdf.setProperty("class", "success-btn")
        self.btn_download_png.setProperty("class", "primary-btn")

        btn_box.addWidget(self.btn_download_pdf)
        btn_box.addWidget(self.btn_download_png)
        layout.addLayout(btn_box)

        # Signals
        self.spin_visa_fee.valueChanged.connect(self._recalculate)
        self.spin_evisa_fee.valueChanged.connect(self._recalculate)
        self.spin_vip_fee.valueChanged.connect(self._recalculate)
        self.spin_overstay_fee.valueChanged.connect(self._recalculate)
        self.spin_work_permit.valueChanged.connect(self._recalculate)
        self.spin_exchange_rate.valueChanged.connect(self._recalculate)

        self.btn_download_pdf.clicked.connect(self.download_pdf_requested.emit)
        self.btn_download_png.clicked.connect(self.download_png_requested.emit)

        self._recalculate()

    def _recalculate(self):
        tot_usd = self.spin_visa_fee.value() + self.spin_evisa_fee.value() + self.spin_vip_fee.value() + self.spin_overstay_fee.value() + self.spin_work_permit.value()
        rate = self.spin_exchange_rate.value()
        tot_baht = tot_usd * rate

        self.lbl_total_usd.setText(f"TOTAL USD: $ {tot_usd:.2f}")
        self.lbl_currencies.setText(f"PRICE IN BAHT (อัตรา {rate:.1f}): ฿ {tot_baht:,.0f}")

    def set_fee_details(self, fee_details):
        if not fee_details:
            return
        if "visa_fee" in fee_details:
            self.spin_visa_fee.setValue(float(fee_details["visa_fee"]))
        if "e_visa" in fee_details:
            self.spin_evisa_fee.setValue(float(fee_details["e_visa"]))
        if "vip_fee" in fee_details:
            self.spin_vip_fee.setValue(float(fee_details["vip_fee"]))
        if "overstay_fee" in fee_details:
            self.spin_overstay_fee.setValue(float(fee_details["overstay_fee"]))
        if "work_permit" in fee_details:
            self.spin_work_permit.setValue(float(fee_details["work_permit"]))
        if "exchange_rate" in fee_details:
            self.spin_exchange_rate.setValue(float(fee_details["exchange_rate"]))
        self._recalculate()

    def get_fee_details(self):
        return {
            "visa_fee": self.spin_visa_fee.value(),
            "e_visa": self.spin_evisa_fee.value(),
            "vip_fee": self.spin_vip_fee.value(),
            "overstay_fee": self.spin_overstay_fee.value(),
            "work_permit": self.spin_work_permit.value(),
            "exchange_rate": self.spin_exchange_rate.value()
        }


class GroupCustomerWidget(QGroupBox):
    """
    Batch Customer Data Form for handling group visitors / tour groups.
    """
    save_group_requested = pyqtSignal(dict)
    member_count_changed = pyqtSignal(int)
    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("👨‍👩‍👧‍👦 BATCH / GROUP CUSTOMERS DATA (ទិន្នន័យភ្ញៀវជាក្រុម)", parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Top Header Section: Customer Name, Travel Date & Top Fees
        top_box = QFrame()
        top_box.setProperty("class", "panel-card")
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(8)

        # Row 1: Sender Name & Travel Date (Compact & Sleek Inputs)
        g1 = QHBoxLayout()
        lbl_sender = QLabel("👤 ឈ្មោះអ្នកបញ្ជូន (Sender Name):")
        lbl_sender.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; color: #818cf8; }")
        
        self.txt_group_name = QLineEdit()
        self.txt_group_name.setPlaceholderText("ឧ. HR(CS)- แอน ឬ ឈ្មោះអ្នកបញ្ជូន...")
        self.txt_group_name.setMinimumHeight(34)
        self.txt_group_name.setMinimumWidth(260)
        self.txt_group_name.setStyleSheet("QLineEdit { background: #0f172a; color: #f8fafc; font-weight: bold; border: 1px solid #475569; border-radius: 6px; padding: 4px 10px; font-size: 12px; }")
        self.txt_group_name.textChanged.connect(self._emit_data_changed)

        lbl_date = QLabel("🗓️ ថ្ងៃធ្វើដំណើរ:")
        lbl_date.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; color: #818cf8; }")

        self.txt_group_travel_date = QLineEdit()
        self.txt_group_travel_date.setPlaceholderText("ឧ. 15-08-2026")
        self.txt_group_travel_date.setText(datetime.date.today().strftime("%d-%m-%Y"))
        self.txt_group_travel_date.setMinimumHeight(34)
        self.txt_group_travel_date.setMinimumWidth(130)
        self.txt_group_travel_date.setStyleSheet("QLineEdit { background: #0f172a; color: #f8fafc; font-weight: bold; border: 1px solid #475569; border-radius: 6px; padding: 4px 10px; font-size: 12px; }")
        self.txt_group_travel_date.textChanged.connect(self._emit_data_changed)

        g1.addWidget(lbl_sender)
        g1.addWidget(self.txt_group_name, stretch=3)
        g1.addWidget(lbl_date)
        g1.addWidget(self.txt_group_travel_date, stretch=1)
        top_layout.addLayout(g1)

        # Row 2: Customer Passport Name (Direct Input) & Pick from Passport Button
        g2 = QHBoxLayout()
        lbl_cust = QLabel("👤 ឈ្មោះអតិថិជន (តាម Passport):")
        lbl_cust.setStyleSheet("QLabel { font-weight: bold; font-size: 11px; color: #38bdf8; }")

        self.txt_passport_customer_name = QLineEdit()
        self.txt_passport_customer_name.setPlaceholderText("វាយបញ្ចូលឈ្មោះអតិថិជន (ឧ. SOMCHAI SUWANNAKOT)...")
        self.txt_passport_customer_name.setMinimumHeight(32)
        self.txt_passport_customer_name.setMinimumWidth(320)
        self.txt_passport_customer_name.setStyleSheet("QLineEdit { background: #0f172a; color: #38bdf8; font-weight: bold; border: 1.5px solid #38bdf8; border-radius: 6px; padding: 3px 8px; font-size: 11px; }")
        self.txt_passport_customer_name.textChanged.connect(self._emit_data_changed)

        self.btn_customer_passport_name = QPushButton("📋 ជ្រើសពី Passport")
        self.btn_customer_passport_name.setProperty("class", "primary-btn")
        self.btn_customer_passport_name.setMinimumHeight(32)
        self.btn_customer_passport_name.setToolTip("ទាញយកឈ្មោះអតិថិជនពីការស្កេន Passport")
        self.btn_customer_passport_name.setStyleSheet("QPushButton { font-size: 11px; font-weight: bold; padding: 3px 12px; border-radius: 6px; }")
        self.btn_customer_passport_name.clicked.connect(self._show_passport_customer_name)

        g2.addWidget(lbl_cust)
        g2.addWidget(self.txt_passport_customer_name, stretch=3)
        g2.addWidget(self.btn_customer_passport_name, stretch=1)
        top_layout.addLayout(g2)

        # Row 2: Car Fee, Invoice No & Exchange Rate
        g_car = QHBoxLayout()

        self.spin_car_1 = DirectNumberInput(0.0, text_color="#38bdf8")
        self.spin_car_1.setToolTip("ថ្លៃឡាន (Car Fee)")

        self.txt_invoice_no = QLineEdit()
        self.txt_invoice_no.setText(InvoiceNumberManager.get_next_invoice_no())
        self.txt_invoice_no.setMinimumHeight(32)
        self.txt_invoice_no.setMinimumWidth(120)
        self.txt_invoice_no.setStyleSheet("QLineEdit { background: #0f172a; color: #fbbf24; font-weight: bold; border: 1.5px solid #fbbf24; border-radius: 6px; padding: 4px 10px; font-size: 12px; }")
        self.txt_invoice_no.textChanged.connect(self._emit_data_changed)

        self.spin_exchange_rate = DirectNumberInput(33.9, text_color="#f8fafc")
        self.spin_exchange_rate.setPlaceholderText("Rate...")
        self.spin_exchange_rate.valueChanged.connect(self._emit_data_changed)

        g_car.addWidget(QLabel("🚗 ថ្លៃឡាន:"))
        g_car.addWidget(self.spin_car_1)
        g_car.addSpacing(10)
        g_car.addWidget(QLabel("🧾 លេខវិក័យប័ត្រ:"))
        g_car.addWidget(self.txt_invoice_no)
        g_car.addSpacing(10)
        g_car.addWidget(QLabel("🔱 អត្រាប្តូរប្រាក់:"))
        g_car.addWidget(self.spin_exchange_rate)
        g_car.addStretch()

        top_layout.addLayout(g_car)

        # Row 3: Top Fee Controls for E-VISA, VIP, and Clearance Fees (អាចវាយបញ្ចូលបាន)
        g_other_fees = QHBoxLayout()

        self.spin_top_evisa = DirectNumberInput(0.0, text_color="#a855f7")
        self.spin_top_evisa.setToolTip("ថ្លៃ E-VISA")

        self.spin_top_vip = DirectNumberInput(0.0, text_color="#f59e0b")
        self.spin_top_vip.setToolTip("ថ្លៃ VIP")

        self.spin_top_clearance = DirectNumberInput(0.0, text_color="#10b981")
        self.spin_top_clearance.setToolTip("ថ្លៃក្លៀវផ្លូវ")

        g_other_fees.addWidget(QLabel("💻 ថ្លៃ E-VISA:"))
        g_other_fees.addWidget(self.spin_top_evisa)
        g_other_fees.addWidget(QLabel("👑 ថ្លៃ VIP:"))
        g_other_fees.addWidget(self.spin_top_vip)
        g_other_fees.addWidget(QLabel("🛣️ ថ្លៃក្លៀផ្លូវ:"))
        g_other_fees.addWidget(self.spin_top_clearance)
        g_other_fees.addStretch()

        top_layout.addLayout(g_other_fees)
        layout.addWidget(top_box)

        # Action Toolbar (Pax Generator & Add Member)
        tool_box = QHBoxLayout()
        self.lbl_member_count = QLabel("👥 ចំនួនសមាជិកក្រុម: 0 នាក់")
        self.lbl_member_count.setProperty("class", "heading-3")

        self.spin_pax_input = QSpinBox()
        self.spin_pax_input.setRange(1, 100)
        self.spin_pax_input.setValue(3)
        self.spin_pax_input.setPrefix("Pax: ")

        self.btn_gen_pax = QPushButton("⚡ បង្កើតជួរ Pax")
        self.btn_gen_pax.setProperty("class", "primary-btn")
        self.btn_gen_pax.clicked.connect(self.generate_pax_rows)

        self.btn_add_member = QPushButton("➕ បន្ថែមសមាជិក 1 នាក់")
        self.btn_add_member.setProperty("class", "secondary-btn")
        self.btn_add_member.clicked.connect(self.add_empty_member)

        self.btn_clear = QPushButton("🧹 សម្អាត Form")
        self.btn_clear.setProperty("class", "warning-btn")
        self.btn_clear.clicked.connect(self.clear_group)

        tool_box.addWidget(self.lbl_member_count)
        tool_box.addStretch()
        tool_box.addWidget(self.spin_pax_input)
        tool_box.addWidget(self.btn_gen_pax)
        tool_box.addWidget(self.btn_add_member)
        tool_box.addWidget(self.btn_clear)
        layout.addLayout(tool_box)

        # Save Group Record Button (Positioned at top right below input controls)
        self.btn_save_group = QPushButton("💾 រក្សាទុកទិន្នន័យក្រុម (Save Group Record)")
        self.btn_save_group.setProperty("class", "success-btn")
        self.btn_save_group.setMinimumHeight(38)
        self.btn_save_group.clicked.connect(self._emit_save_group)
        layout.addWidget(self.btn_save_group)

        # Members Table Widget (Spacious and clear view)
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(7)
        self.members_table.setHorizontalHeaderLabels([
            "ល.រ (#)", "ឈ្មោះតាមប៉ាសព័រ (Passport Name)", "ថ្លៃឡាន ($)", "ថ្លៃ E-VISA ($)", "ថ្លៃ VIP ($)", "ថ្លៃក្លៀវផ្លូវ ($)", "សរុប ($)"
        ])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.members_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.members_table.setColumnWidth(0, 45)
        self.members_table.setMinimumHeight(280)
        layout.addWidget(self.members_table)

        # Signals connection for top fee spinboxes
        self.spin_car_1.valueChanged.connect(self._on_top_car_fees_changed)
        self.spin_top_evisa.valueChanged.connect(self._on_top_other_fees_changed)
        self.spin_top_vip.valueChanged.connect(self._on_top_other_fees_changed)
        self.spin_top_clearance.valueChanged.connect(self._on_top_other_fees_changed)

    def _on_top_car_fees_changed(self, *args):
        if not hasattr(self, 'members_table') or self.members_table is None:
            return
        car_val = self.spin_car_1.value()
        for r in range(self.members_table.rowCount()):
            spin_car = self.members_table.cellWidget(r, 2)
            if spin_car is not None and hasattr(spin_car, 'setValue'):
                spin_car.blockSignals(True)
                spin_car.setValue(car_val)
                spin_car.blockSignals(False)
        self._emit_data_changed()

    def _on_top_other_fees_changed(self, *args):
        if not hasattr(self, 'members_table') or self.members_table is None:
            return
        evisa_val = self.spin_top_evisa.value()
        vip_val = self.spin_top_vip.value()
        clearance_val = self.spin_top_clearance.value()

        for r in range(self.members_table.rowCount()):
            spin_evisa = self.members_table.cellWidget(r, 3)
            if spin_evisa is not None and hasattr(spin_evisa, 'setValue'):
                spin_evisa.blockSignals(True)
                spin_evisa.setValue(evisa_val)
                spin_evisa.blockSignals(False)

            spin_vip = self.members_table.cellWidget(r, 4)
            if spin_vip is not None and hasattr(spin_vip, 'setValue'):
                spin_vip.blockSignals(True)
                spin_vip.setValue(vip_val)
                spin_vip.blockSignals(False)

            spin_clearance = self.members_table.cellWidget(r, 5)
            if spin_clearance is not None and hasattr(spin_clearance, 'setValue'):
                spin_clearance.blockSignals(True)
                spin_clearance.setValue(clearance_val)
                spin_clearance.blockSignals(False)

        self._emit_data_changed()

    def _show_passport_customer_name(self):
        """Displays / auto-fills the customer name(s) extracted from scanned Passport."""
        members = self.get_members_list()
        valid_names = [
            m.get("full_english_name", "").strip()
            for m in members
            if m.get("full_english_name") and not m.get("full_english_name").startswith("CUSTOMER") and not m.get("full_english_name").startswith("PASSENGER")
        ]

        if not valid_names:
            valid_names = [m.get("full_english_name", "").strip() for m in members if m.get("full_english_name")]

        if not valid_names:
            QMessageBox.information(
                self,
                "👤 ឈ្មោះអតិថិជន (ពី Passport)",
                "⚠️ មិនទាន់មានទិន្នន័យឈ្មោះអតិថិជនពី Passport នៅក្នុងតារាងនៅឡើយទេ។\nសូម Drag & Drop រូបភាព Passport ដើម្បីស្កេន ឬវាយបញ្ចូលឈ្មោះក្នុងតារាងខាងក្រោម។"
            )
            return

        names_str = "\n".join([f"  • {idx + 1}. {n}" for idx, n in enumerate(valid_names)])
        msg = f"📋 ឈ្មោះអតិថិជនដែលបានមកពីការស្កេន Passport ({len(valid_names)} នាក់):\n\n{names_str}\n\nតើអ្នកចង់ប្រើឈ្មោះអតិថិជនដំបូង [{valid_names[0]}] មកបំពេញក្នុងប្រអប់ [ឈ្មោះអតិថិជន] ដែរឬទេ?"
        
        reply = QMessageBox.question(
            self,
            "👤 ឈ្មោះអតិថិជន (ពី Passport)",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.txt_passport_customer_name.setText(valid_names[0])

    def generate_pax_rows(self):
        count = self.spin_pax_input.value()
        self.members_table.setRowCount(0)
        car_val = self.spin_car_1.value()
        for i in range(1, count + 1):
            p_val = car_val
            self.add_member_data({
                "full_english_name": f"CUSTOMER {i}",
                "car_fee": p_val,
                "e_visa": self.spin_top_evisa.value(),
                "vip": self.spin_top_vip.value(),
                "clearance_fee": self.spin_top_clearance.value(),
                "qty": "1",
                "nationality": "THAI",
                "sex": "M",
                "passport_no": ""
            })

    def add_customer_1(self):
        self.add_member_data({
            "full_english_name": "CUSTOMER 1",
            "car_fee": 0.0,
            "e_visa": 0.0,
            "vip": 0.0,
            "clearance_fee": 0.0,
            "qty": "1",
            "nationality": "THAI",
            "sex": "M",
            "passport_no": ""
        })

    def add_member_data(self, member_dict):
        """Adds or updates a member dict (from OCR or DB) to table with passport name."""
        given = (member_dict.get('english_given_names') or '').strip()
        sur = (member_dict.get('english_surname') or '').strip()
        given_sur = f"{given} {sur}".strip() if (given and sur) else ""
        given_sur_clean = clean_person_name(given_sur) if given_sur else ""

        name = (
            given_sur_clean or
            clean_person_name(member_dict.get("full_english_name") or '') or
            clean_person_name(member_dict.get("english_name") or '') or
            clean_person_name(member_dict.get("passport_name") or '') or
            clean_person_name(member_dict.get("name") or '') or
            member_dict.get("thai_name") or
            member_dict.get("khmer_name") or
            ""
        ).strip()

        # Check if we should replace an existing placeholder row (e.g. CUSTOMER 1, PASSENGER 1)
        target_row = None
        if name and not name.startswith("CUSTOMER") and not name.startswith("PASSENGER"):
            for r in range(self.members_table.rowCount()):
                w_name = self.members_table.cellWidget(r, 1)
                curr_text = w_name.text().strip() if isinstance(w_name, QLineEdit) else ""
                if curr_text.startswith("CUSTOMER") or curr_text.startswith("PASSENGER"):
                    target_row = r
                    break

        if target_row is not None:
            row = target_row
            # Update existing placeholder row with real scanned passport name
            w_name = self.members_table.cellWidget(row, 1)
            if isinstance(w_name, QLineEdit):
                w_name.setText(name)

            # Update fees if provided
            car_fee = member_dict.get("car_fee")
            if car_fee is not None:
                w_car = self.members_table.cellWidget(row, 2)
                if hasattr(w_car, 'setValue'):
                    w_car.setValue(float(car_fee))

            evisa_fee = member_dict.get("e_visa") or member_dict.get("evisa")
            if evisa_fee is not None:
                w_evisa = self.members_table.cellWidget(row, 3)
                if hasattr(w_evisa, 'setValue'):
                    w_evisa.setValue(float(evisa_fee))

            vip_fee = member_dict.get("vip") or member_dict.get("vip_fee")
            if vip_fee is not None:
                w_vip = self.members_table.cellWidget(row, 4)
                if hasattr(w_vip, 'setValue'):
                    w_vip.setValue(float(vip_fee))

            clearance_fee = member_dict.get("clearance_fee") or member_dict.get("work_permit")
            if clearance_fee is not None:
                w_clearance = self.members_table.cellWidget(row, 5)
                if hasattr(w_clearance, 'setValue'):
                    w_clearance.setValue(float(clearance_fee))

            # Recalculate row total
            w_car = self.members_table.cellWidget(row, 2)
            c_val = w_car.value() if hasattr(w_car, 'value') else 0.0
            w_evisa = self.members_table.cellWidget(row, 3)
            e_val = w_evisa.value() if hasattr(w_evisa, 'value') else 0.0
            w_vip = self.members_table.cellWidget(row, 4)
            v_val = w_vip.value() if hasattr(w_vip, 'value') else 0.0
            w_clearance = self.members_table.cellWidget(row, 5)
            cl_val = w_clearance.value() if hasattr(w_clearance, 'value') else 0.0

            item_tot = self.members_table.item(row, 6)
            if item_tot:
                item_tot.setText(f"${(c_val + e_val + v_val + cl_val):.2f}")

            self._update_count()
            return

        # Otherwise insert a new row
        row = self.members_table.rowCount()
        self.members_table.insertRow(row)

        if not name:
            name = f"PASSENGER {row + 1}"

        # Fees
        car_fee = member_dict.get("car_fee")
        if car_fee is None:
            car_fee = member_dict.get("price") or member_dict.get("visa_fee") or member_dict.get("usd")
        if car_fee is None:
            car_fee = self.spin_car_1.value()
        else:
            try:
                car_fee = float(car_fee)
            except (ValueError, TypeError):
                car_fee = 0.0

        evisa_fee = float(member_dict.get("e_visa") or member_dict.get("evisa") or 0.0)
        vip_fee = float(member_dict.get("vip") or member_dict.get("vip_fee") or 0.0)
        clearance_fee = float(member_dict.get("clearance_fee") or member_dict.get("work_permit") or 0.0)

        # Column 0: Index
        self.members_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

        # Column 1: Editable Passport Customer Name (QLineEdit with bold font & stretch)
        txt_name = QLineEdit()
        txt_name.setText(name)
        txt_name.setPlaceholderText("ឈ្មោះតាម Passport (ឧ. SOMCHAI SUWANNAKOT)...")
        txt_name.setStyleSheet("QLineEdit { background: #0f172a; color: #f8fafc; font-weight: bold; border: 1px solid #475569; border-radius: 5px; padding: 3px 6px; font-size: 11px; min-height: 26px; }")
        txt_name.textChanged.connect(self._emit_data_changed)
        txt_name.returnPressed.connect(lambda: self._focus_next_member_row(txt_name))
        self.members_table.setCellWidget(row, 1, txt_name)

        # Column 2: ថ្លៃឡាន (Car Fee Direct Input)
        spin_car = DirectNumberInput(float(car_fee), text_color="#38bdf8")
        spin_car.setPlaceholderText("ថ្លៃឡាន...")
        spin_car.valueChanged.connect(lambda _: self._emit_data_changed())
        self.members_table.setCellWidget(row, 2, spin_car)

        # Column 3: ថ្លៃ E-VISA (E-Visa Direct Input)
        spin_evisa = DirectNumberInput(float(evisa_fee), text_color="#a855f7")
        spin_evisa.setPlaceholderText("E-VISA...")
        spin_evisa.valueChanged.connect(lambda _: self._emit_data_changed())
        self.members_table.setCellWidget(row, 3, spin_evisa)

        # Column 4: ថ្លៃ VIP (VIP Direct Input)
        spin_vip = DirectNumberInput(float(vip_fee), text_color="#f59e0b")
        spin_vip.setPlaceholderText("VIP...")
        spin_vip.valueChanged.connect(lambda _: self._emit_data_changed())
        self.members_table.setCellWidget(row, 4, spin_vip)

        # Column 5: ថ្លៃក្លៀវផ្លូវ (Clearance Fee Direct Input)
        spin_clearance = DirectNumberInput(float(clearance_fee), text_color="#10b981")
        spin_clearance.setPlaceholderText("ក្លៀវផ្លូវ...")
        spin_clearance.valueChanged.connect(lambda _: self._emit_data_changed())
        self.members_table.setCellWidget(row, 5, spin_clearance)

        # Column 6: Total ($)
        tot_val = car_fee + evisa_fee + vip_fee + clearance_fee
        item_tot = QTableWidgetItem(f"${tot_val:.2f}")
        item_tot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.members_table.setItem(row, 6, item_tot)

        self._update_count()

    def _focus_next_member_row(self, current_txt):
        for r in range(self.members_table.rowCount()):
            if self.members_table.cellWidget(r, 1) == current_txt:
                next_row = r + 1
                if next_row >= self.members_table.rowCount():
                    self.add_empty_member()
                if next_row < self.members_table.rowCount():
                    w_next = self.members_table.cellWidget(next_row, 1)
                    if isinstance(w_next, QLineEdit):
                        w_next.setFocus()
                        w_next.selectAll()
                break

    def add_empty_member(self):
        cnt = self.members_table.rowCount() + 1
        p_val = self.spin_car_1.value()
        self.add_member_data({
            "full_english_name": f"PASSENGER {cnt}",
            "car_fee": p_val,
            "e_visa": 0.0,
            "vip": 0.0,
            "clearance_fee": 0.0,
            "qty": "1",
            "nationality": "THAI",
            "sex": "M",
            "passport_no": ""
        })

    def _delete_row(self, row_idx):
        if 0 <= row_idx < self.members_table.rowCount():
            self.members_table.removeRow(row_idx)
            self._renumber_rows()
            self._update_count()

    def _renumber_rows(self):
        for r in range(self.members_table.rowCount()):
            self.members_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))

    def _update_count(self):
        cnt = self.members_table.rowCount()
        self.lbl_member_count.setText(f"👥 ចំនួនសមាជិកក្រុម: {cnt} នាក់")
        self.member_count_changed.emit(cnt)
        self._emit_data_changed()

    def _emit_data_changed(self):
        self.data_changed.emit()

    def clear_group(self):
        self.txt_group_name.clear()
        self.txt_passport_customer_name.clear()
        self.txt_group_travel_date.clear()
        self.txt_invoice_no.setText(InvoiceNumberManager.get_next_invoice_no())
        self.spin_exchange_rate.setValue(33.9)
        self.spin_car_1.setValue(0.0)
        self.spin_top_evisa.setValue(0.0)
        self.spin_top_vip.setValue(0.0)
        self.spin_top_clearance.setValue(0.0)
        self.members_table.setRowCount(0)
        self._update_count()

    def get_group_info(self):
        return {
            "group_name": self.txt_group_name.text().strip() or "VIP Group",
            "sender_name": self.txt_group_name.text().strip(),
            "customer_name": self.txt_passport_customer_name.text().strip(),
            "agency_company": "",
            "travel_date": self.txt_group_travel_date.text().strip()
        }

    def get_members_list(self):
        members = []
        for r in range(self.members_table.rowCount()):
            w_name = self.members_table.cellWidget(r, 1)
            name = w_name.text().strip() if isinstance(w_name, QLineEdit) else ""

            w_car = self.members_table.cellWidget(r, 2)
            car_fee = w_car.value() if hasattr(w_car, 'value') else 0.0

            w_evisa = self.members_table.cellWidget(r, 3)
            evisa_fee = w_evisa.value() if hasattr(w_evisa, 'value') else 0.0

            w_vip = self.members_table.cellWidget(r, 4)
            vip_fee = w_vip.value() if hasattr(w_vip, 'value') else 0.0

            w_clearance = self.members_table.cellWidget(r, 5)
            clearance_fee = w_clearance.value() if hasattr(w_clearance, 'value') else 0.0

            tot_val = car_fee + evisa_fee + vip_fee + clearance_fee

            item_tot = self.members_table.item(r, 6)
            if item_tot:
                item_tot.setText(f"${tot_val:.2f}")

            members.append({
                "full_english_name": name,
                "english_name": name,
                "car_fee": car_fee,
                "visa_fee": car_fee,
                "price": car_fee,
                "e_visa": evisa_fee,
                "vip": vip_fee,
                "clearance_fee": clearance_fee,
                "work_permit": 0.0,
                "usd": tot_val,
                "qty": "1"
            })
        return members

    def _emit_save_group(self):
        group_info = self.get_group_info()
        sender_name = (group_info.get("group_name") or group_info.get("sender_name") or "").strip()
        if not sender_name or sender_name.upper() in ["VIP GROUP", "GROUP", ""]:
            QMessageBox.warning(self, "Warning", "⚠️ សូមបញ្ចូលឈ្មោះអ្នកផ្ញើ / អ្នកនាំ (Sender Name) ជាមុនសិន ទើបអាចរក្សាទុកបាន!")
            self.txt_group_name.setFocus()
            return
        members = self.get_members_list()
        if not members:
            QMessageBox.warning(self, "Warning", "សូមបញ្ចូលសមាជិកក្រុមយ៉ាងហោចណាស់ ១ នាក់!")
            return
        self.save_group_requested.emit({"group_info": group_info, "members": members})


class GroupReceiptFeeWidget(QGroupBox):
    """
    CMP Golden Mekong Group Invoice Service Fees & Pricing Calculator.
    """
    download_group_pdf_requested = pyqtSignal()
    download_group_png_requested = pyqtSignal()
    share_group_telegram_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("💵 INVOICE FEES & EXCHANGE RATE FOR GROUP (គណនាថ្លៃសេវា និងអត្រាប្តូរប្រាក់ក្រុម)", parent)

        self.member_count = 1
        self.current_members = []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Invoice No & Exchange Rate Control & Payment Status
        self.txt_invoice_no = QLineEdit()
        self.txt_invoice_no.setText(InvoiceNumberManager.get_next_invoice_no())
        self.spin_exchange_rate = DirectNumberInput(33.9, text_color="#f8fafc")

        self.combo_payment_status = QComboBox()
        self.combo_payment_status.addItem("⏳ មិនទាន់បង់ (Unpaid)", "UNPAID")
        self.combo_payment_status.addItem("✅ បង់លុយហើយ (Paid)", "PAID")
        self.combo_payment_status.setMinimumHeight(32)
        self.combo_payment_status.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #f8fafc;
                font-weight: bold;
                border: 1.5px solid #38bdf8;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #f8fafc;
                selection-background-color: #0284c7;
            }
        """)

        r_rate = QHBoxLayout()
        r_rate.addWidget(QLabel("💳 ស្ថានភាព (Payment Status):"))
        r_rate.addWidget(self.combo_payment_status)
        r_rate.addStretch()
        layout.addLayout(r_rate)

        # Summary Display Panel
        summary_panel = QFrame()
        summary_panel.setProperty("class", "highlight-card")
        sp_layout = QVBoxLayout(summary_panel)

        self.lbl_total_usd = QLabel("GROUP TOTAL USD: $ 0.00")
        self.lbl_total_usd.setProperty("class", "stat-value")

        self.lbl_currencies = QLabel("PRICE IN BAHT (อัตรา 33.9): ฿ 0")
        sp_layout.addWidget(self.lbl_total_usd)
        sp_layout.addWidget(self.lbl_currencies)
        layout.addWidget(summary_panel)

        # Download & Universal Share Buttons
        btn_box = QHBoxLayout()
        self.btn_download_pdf = QPushButton("📄 ទាញយកវិក័យប័ត្រ (Download PDF)")
        self.btn_download_png = QPushButton("🖼️ ទាញយកវិក័យប័ត្រ (Download PNG)")
        self.btn_share_telegram = QPushButton("🔗 Share / ផ្ញើចេញ (Universal Share)")

        self.btn_download_pdf.setProperty("class", "success-btn")
        self.btn_download_png.setProperty("class", "primary-btn")
        self.btn_share_telegram.setProperty("class", "warning-btn")
        self.btn_share_telegram.setStyleSheet("QPushButton { background-color: #8b5cf6; color: white; font-weight: bold; } QPushButton:hover { background-color: #7c3aed; }")

        btn_box.addWidget(self.btn_download_pdf)
        btn_box.addWidget(self.btn_download_png)
        btn_box.addWidget(self.btn_share_telegram)
        layout.addLayout(btn_box)

        # Connect signals
        self.spin_exchange_rate.valueChanged.connect(self._recalculate)

        self.btn_download_pdf.clicked.connect(self.download_group_pdf_requested.emit)
        self.btn_download_png.clicked.connect(self.download_group_png_requested.emit)
        self.btn_share_telegram.clicked.connect(self.share_group_telegram_requested.emit)

        self._recalculate()

    def link_form_widget(self, form_widget):
        self.form_widget = form_widget
        self.txt_invoice_no = form_widget.txt_invoice_no
        self.spin_exchange_rate = form_widget.spin_exchange_rate
        self.spin_exchange_rate.valueChanged.connect(self._recalculate)
        self.txt_invoice_no.textChanged.connect(self._recalculate)
        self._recalculate()

    def update_member_count(self, count):
        self.member_count = max(1, count)
        self._recalculate()

    def update_group_members(self, count, members=None):
        self.member_count = max(1, count)
        self.current_members = members or []
        self._recalculate()

    def _recalculate(self):
        mc = max(0, self.member_count)

        if self.current_members:
            tot_usd = sum(float(m.get("usd", 0.0)) for m in self.current_members)
        else:
            tot_usd = 0.0

        rate = self.spin_exchange_rate.value()
        tot_baht = tot_usd * rate

        self.lbl_total_usd.setText(f"GROUP TOTAL ({mc} Pax): $ {tot_usd:.2f}")
        self.lbl_currencies.setText(f"PRICE IN BAHT (อัตรา {rate:.1f}): ฿ {tot_baht:,.0f}")

    def set_fee_details(self, fee_details):
        if not fee_details:
            return
        if "exchange_rate" in fee_details:
            self.spin_exchange_rate.setValue(float(fee_details["exchange_rate"]))
        if "payment_status" in fee_details:
            st = fee_details["payment_status"]
            idx = self.combo_payment_status.findData(st)
            if idx >= 0:
                self.combo_payment_status.setCurrentIndex(idx)
        self._recalculate()

    def get_invoice_no(self) -> str:
        text = self.txt_invoice_no.text().strip()
        if not text:
            text = InvoiceNumberManager.get_next_invoice_no()
            self.txt_invoice_no.setText(text)
        return text

    def advance_invoice_no(self, used_no=None) -> str:
        if not used_no:
            used_no = self.get_invoice_no()
        next_no = InvoiceNumberManager.increment_invoice_no(used_no)
        self.txt_invoice_no.setText(next_no)
        return next_no

    def get_fee_details(self):
        return {
            "visa_fee": 0.0,
            "car_fee": 0.0,
            "e_visa": 0.0,
            "vip_fee": 0.0,
            "overstay_fee": 0.0,
            "work_permit": 0.0,
            "clearance_fee": 0.0,
            "exchange_rate": self.spin_exchange_rate.value(),
            "receipt_no": self.get_invoice_no(),
            "payment_status": self.combo_payment_status.currentData() or "UNPAID"
        }


class SavedCustomersTableWidget(QGroupBox):
    """
    Table displaying saved customer records with JSON persistence, search filter, payment status toggle, and CSV export.
    Supports searching by Tour Guide Name (អ្នកនាំ), Invoice Number (លេខវិក័យប័ត្រ), Travel Date (ថ្ងៃធ្វើដំណើរ), Customer Name (ឈ្មោះអតិថិជន), and Payment Status (បង់ហើយ/មិនទាន់បង់).
    """
    load_record_requested = pyqtSignal(dict)
    download_pdf_record_requested = pyqtSignal(dict)
    download_png_record_requested = pyqtSignal(dict)
    share_telegram_record_requested = pyqtSignal(dict)

    DATA_FILE = "saved_customers.json"

    def __init__(self, parent=None):
        super().__init__("📋 SAVED CUSTOMERS DATABASE (បញ្ជីទិន្នន័យអតិថិជនដែលបានរក្សាទុក)", parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header toolbar
        tool_layout = QHBoxLayout()
        self.lbl_count = QLabel("📊 សរុប: 0 នាក់ (Total Records: 0)")
        self.lbl_count.setProperty("class", "heading-3")

        self.btn_export_csv = QPushButton("📥 Export CSV")
        self.btn_export_csv.setProperty("class", "primary-btn")

        self.btn_clear_all = QPushButton("🗑️ លុបទាំងអស់ (Clear All)")
        self.btn_clear_all.setProperty("class", "danger-btn")

        tool_layout.addWidget(self.lbl_count)
        tool_layout.addStretch()
        tool_layout.addWidget(self.btn_export_csv)
        tool_layout.addWidget(self.btn_clear_all)
        layout.addLayout(tool_layout)

        # Search Toolbar layout
        search_layout = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 ស្វែងរក៖ ឈ្មោះអ្នកនាំ, លេខវិក័យប័ត្រ, ថ្ងៃធ្វើដំណើរ, ឈ្មោះអតិថិជន, ស្ថានភាព (បង់ហើយ/មិនទាន់បង់)...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background: #0f172a;
                color: #f8fafc;
                border: 1.5px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #60a5fa;
            }
        """)

        self.btn_search = QPushButton("🔍 ស៊ើចរក (Search)")
        self.btn_search.setProperty("class", "primary-btn")
        self.btn_search.setStyleSheet("QPushButton { background-color: #2563eb; color: white; font-weight: bold; border-radius: 6px; padding: 6px 14px; } QPushButton:hover { background-color: #1d4ed8; }")

        self.btn_reset_search = QPushButton("❌ សំអាត (Reset)")
        self.btn_reset_search.setProperty("class", "secondary-btn")
        self.btn_reset_search.setStyleSheet("QPushButton { background-color: #475569; color: white; font-weight: bold; border-radius: 6px; padding: 6px 12px; } QPushButton:hover { background-color: #334155; }")

        search_layout.addWidget(self.txt_search, 1)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_reset_search)
        layout.addLayout(search_layout)

        # Table Widget (8 Columns including Payment Status)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ល.រ (#)", "លេខវិក័យប័ត្រ", "ថ្ងៃធ្វើដំណើរ", "អ្នកនាំ / ក្រុម", "ឈ្មោះអតិថិជន (Customer)", "ថ្លៃសេវាសរុប", "ស្ថានភាពទូទាត់", "សកម្មភាព (Actions)"
        ])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 105)
        self.table.setColumnWidth(2, 105)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(5, 95)
        self.table.setColumnWidth(6, 135)
        self.table.setColumnWidth(7, 390)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(280)

        layout.addWidget(self.table)

        # Connect toolbar buttons and search signals
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_clear_all.clicked.connect(self._clear_all)
        self.txt_search.textChanged.connect(self.refresh_table)
        self.btn_search.clicked.connect(self.refresh_table)
        self.btn_reset_search.clicked.connect(self._clear_search)

        self.records = []
        self._load_from_json()

    def _clear_search(self):
        self.txt_search.clear()
        self.refresh_table()

    def add_record(self, record):
        """
        Adds a record dict to memory, persists to JSON, and updates table.
        """
        self.records.insert(0, record)  # Newest first
        self._save_to_json()
        self.refresh_table()

    def _toggle_payment_status(self, rec):
        """
        Toggles payment status between PAID and UNPAID, saves to JSON, and refreshes view.
        """
        current_status = rec.get("payment_status") or rec.get("fees", {}).get("payment_status") or "UNPAID"
        new_status = "UNPAID" if str(current_status).upper() == "PAID" else "PAID"
        rec["payment_status"] = new_status
        if "fees" in rec and isinstance(rec["fees"], dict):
            rec["fees"]["payment_status"] = new_status
        self._save_to_json()
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(0)
        query = self.txt_search.text().strip().lower() if hasattr(self, 'txt_search') else ""

        matched_count = 0
        display_no = 1

        for rec in self.records:
            cust = rec.get("customer", {})
            fees = rec.get("totals", {}) or rec.get("fees", {})
            grp_info = rec.get("group_info", {})
            grp_data = rec.get("group_data", {})
            members = rec.get("members", [])

            inv_no = grp_data.get("receipt_no") or fees.get("receipt_no") or "N/A"
            travel_date = grp_info.get("travel_date") or grp_data.get("date_str") or rec.get("date_saved", "")
            guide_name = grp_info.get("group_name") or grp_info.get("sender_name") or "VIP Group"

            cust_name = (
                grp_info.get("customer_name") or
                cust.get("full_english_name") or
                cust.get("english_name") or
                "N/A"
            ).strip()

            member_names = []
            for m in members:
                m_name = (m.get("full_english_name") or m.get("english_name") or "").strip()
                if m_name and m_name not in member_names:
                    member_names.append(m_name)
            
            members_str = ", ".join(member_names)

            # Payment status determination
            st = rec.get("payment_status") or fees.get("payment_status") or "UNPAID"
            is_paid = (str(st).upper() == "PAID")
            status_label_kh = "✅ បង់ហើយ" if is_paid else "⏳ មិនទាន់បង់"
            status_search_tag = "បង់ហើយ paid" if is_paid else "មិនទាន់បង់ unpaid pending"

            # Match against query
            search_blob = f"{guide_name} {inv_no} {travel_date} {cust_name} {members_str} {rec.get('date_saved', '')} {status_search_tag}".lower()

            if query and query not in search_blob:
                continue

            matched_count += 1
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            if cust_name and cust_name != "N/A":
                display_cust = cust_name
                if len(members) > 1:
                    display_cust += f" (+{len(members)-1} នាក់)"
            elif member_names:
                display_cust = member_names[0]
                if len(members) > 1:
                    display_cust += f" (+{len(members)-1} នាក់)"
            else:
                display_cust = "N/A"

            total_usd = f"${fees.get('usd', 0.0):.2f}"

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(display_no)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(inv_no))
            self.table.setItem(row_idx, 2, QTableWidgetItem(travel_date))
            self.table.setItem(row_idx, 3, QTableWidgetItem(guide_name))
            self.table.setItem(row_idx, 4, QTableWidgetItem(display_cust))
            self.table.setItem(row_idx, 5, QTableWidgetItem(total_usd))

            # Column 6: Interactive Payment Status Toggle Button
            btn_status = QPushButton(status_label_kh)
            if is_paid:
                btn_status.setStyleSheet("""
                    QPushButton {
                        background-color: #16a34a;
                        color: #ffffff;
                        font-weight: bold;
                        border-radius: 5px;
                        padding: 4px 8px;
                        font-size: 11px;
                        min-height: 26px;
                    }
                    QPushButton:hover {
                        background-color: #15803d;
                    }
                """)
                btn_status.setToolTip("បានបង់រួចរាល់ (ចុចដើម្បីប្តូរទៅ មិនទាន់បង់)")
            else:
                btn_status.setStyleSheet("""
                    QPushButton {
                        background-color: #dc2626;
                        color: #ffffff;
                        font-weight: bold;
                        border-radius: 5px;
                        padding: 4px 8px;
                        font-size: 11px;
                        min-height: 26px;
                    }
                    QPushButton:hover {
                        background-color: #b91c1c;
                    }
                """)
                btn_status.setToolTip("មិនទាន់បានបង់ (ចុចដើម្បីប្តូរទៅ បង់ហើយ)")

            btn_status.clicked.connect(lambda _, r=rec: self._toggle_payment_status(r))
            self.table.setCellWidget(row_idx, 6, btn_status)

            display_no += 1

            # Column 7: Action Buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 4, 4, 4)
            action_layout.setSpacing(6)

            btn_pdf = QPushButton("📄 Download PDF")
            btn_pdf.setProperty("class", "btn-table-action success-btn")
            btn_pdf.setToolTip("ទាញយកវិក័យប័ត្រ PDF ដោយផ្ទាល់")
            btn_pdf.clicked.connect(lambda _, r=rec: self.download_pdf_record_requested.emit(r))

            btn_png = QPushButton("🖼️ PNG")
            btn_png.setProperty("class", "btn-table-action primary-btn")
            btn_png.setToolTip("ទាញយកវិក័យប័ត្រ PNG ដោយផ្ទាល់")
            btn_png.clicked.connect(lambda _, r=rec: self.download_png_record_requested.emit(r))

            btn_telegram = QPushButton("🔗 Share")
            btn_telegram.setProperty("class", "btn-table-action warning-btn")
            btn_telegram.setStyleSheet("QPushButton { background-color: #8b5cf6; color: white; font-weight: bold; } QPushButton:hover { background-color: #7c3aed; }")
            btn_telegram.setToolTip("ស៊ែរវិក័យប័ត្រទៅ Telegram, WhatsApp, Messenger, Clipboard, PNG, PDF")
            btn_telegram.clicked.connect(lambda _, r=rec: self.share_telegram_record_requested.emit(r))

            btn_load = QPushButton("📂 Load")
            btn_load.setProperty("class", "btn-table-action secondary-btn")
            btn_load.setToolTip("ទាញយកទិន្នន័យមក Form ខាងលើ")
            btn_load.clicked.connect(lambda _, r=rec: self.load_record_requested.emit(r))

            btn_del = QPushButton("🗑️")
            btn_del.setProperty("class", "btn-table-action danger-btn")
            btn_del.setToolTip("លុបទិន្នន័យនេះ (Delete Record)")
            btn_del.clicked.connect(lambda _, r=rec: self._delete_record_by_obj(r))

            action_layout.addWidget(btn_pdf)
            action_layout.addWidget(btn_png)
            action_layout.addWidget(btn_telegram)
            action_layout.addWidget(btn_load)
            action_layout.addWidget(btn_del)
            self.table.setCellWidget(row_idx, 7, action_widget)

        if query:
            self.lbl_count.setText(f"🔍 ស្វែងរកឃើញ: {matched_count} / {len(self.records)} នាក់")
        else:
            self.lbl_count.setText(f"📊 សរុប: {len(self.records)} នាក់ (Total Records: {len(self.records)})")

    def _clear_all(self):
        if not self.records:
            return
        reply = QMessageBox.question(
            self, "Confirm Clear All",
            "តើអ្នកពិតជាចង់លុបទិន្នន័យអតិថិជនទាំងអស់ចេញពីបញ្ជីមែនទេ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.records = []
            self._save_to_json()
            self.refresh_table()

    def _export_csv(self):
        if not self.records:
            QMessageBox.warning(self, "Warning", "គ្មានទិន្នន័យសម្រាប់ Export ទេ!")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Saved Customers CSV", "saved_customers.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["#", "Invoice No", "Travel Date", "Tour Guide/Group", "Customer/Passenger Name", "Date Saved", "Total Amount ($)"])
                    for idx, rec in enumerate(self.records, 1):
                        grp_info = rec.get("group_info", {})
                        grp_data = rec.get("group_data", {})
                        cust = rec.get("customer", {})
                        fee = rec.get("fees", {}) or rec.get("totals", {})
                        
                        inv_no = grp_data.get("receipt_no") or fee.get("receipt_no") or "N/A"
                        travel_date = grp_info.get("travel_date") or grp_data.get("date_str") or rec.get("date_saved", "")
                        guide_name = grp_info.get("group_name") or grp_info.get("sender_name") or "VIP Group"
                        cust_name = grp_info.get("customer_name") or cust.get("full_english_name") or "N/A"
                        tot_usd = fee.get("usd", 0.0)

                        writer.writerow([
                            idx, inv_no, travel_date, guide_name, cust_name, rec.get("date_saved", ""), tot_usd
                        ])
                QMessageBox.information(self, "Success", f"🎉 បាន Export ទិន្នន័យទៅ CSV រួចរាល់!\nSaved: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"មិនអាច Export CSV បានទេ: {str(e)}")


    def _save_to_json(self):
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving records to JSON: {e}")

    def _load_from_json(self):
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    self.records = json.load(f)
            except Exception as e:
                print(f"Error loading records from JSON: {e}")
                self.records = []
        self.refresh_table()

    def _delete_record_by_obj(self, rec):
        """
        Deletes a saved record after user confirmation.
        """
        if rec not in self.records:
            return

        grp_info = rec.get("group_info", {})
        cust = rec.get("customer", {})
        cust_name = grp_info.get("customer_name") or grp_info.get("group_name") or cust.get("full_english_name") or "អតិថិជននេះ"

        reply = QMessageBox.question(
            self,
            "🗑️ បញ្ជាក់ការលុបទិន្នន័យ (Confirm Delete)",
            f"តើអ្នកពិតជាចង់លុបទិន្នន័យកំណត់ត្រារបស់ [{cust_name}] ចេញពីបញ្ជីមែនទេ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.records.remove(rec)
            self._save_to_json()
            self.refresh_table()
            QMessageBox.information(self, "Success", "🎉 បានលុបទិន្នន័យបានសម្រេច!")



class WebcamDialog(QDialog):
    """
    Live WebCam Feed Dialog for snapping document photos.
    """
    image_captured = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📹 Snap Passport Photo via WebCam")
        self.resize(640, 520)

        layout = QVBoxLayout(self)

        self.video_label = QLabel("Initializing Camera...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 8px;")
        layout.addWidget(self.video_label)

        self.snap_btn = QPushButton("📸 Snap Document Photo")
        self.snap_btn.setProperty("class", "success-btn")
        layout.addWidget(self.snap_btn)

        self.cap = cv2.VideoCapture(0)
        self.snap_btn.clicked.connect(self._snap)

        # Timer for video frames
        from PyQt6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(30)
        self.current_frame = None

    def _update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(q_img)
            self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def _snap(self):
        if self.current_frame is not None:
            pil_img = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
            self.image_captured.emit(pil_img)
            self.accept()

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap.isOpened():
            self.cap.release()
        super().closeEvent(event)
