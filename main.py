"""
Main Entry Point for AI OCR Thai/English Passport Scanner & VIP Receipt App (PyQt6)
Supports Single Customer and Group/Batch Entry Modes.
"""

import sys
import os
import datetime
import urllib.parse
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox, QFileDialog, QSplitter, QStatusBar, QLabel, QScrollArea,
    QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QDesktopServices, QImage

from styles import MAIN_STYLESHEET
from ocr_engine import DocumentAIEngine, clean_person_name
from sample_generator import generate_thai_passport_sample, generate_khmer_passport_sample
from receipt_generator import ReceiptGenerator
from ui_components import (
    ImageDropWidget, WebcamDialog,
    SavedCustomersTableWidget, GroupCustomerWidget, GroupReceiptFeeWidget
)
from telegram_utils import UniversalShareDialog


class OCRWorkerThread(QThread):
    """
    Background Thread for running OCR extraction on a single image.
    """
    finished = pyqtSignal(dict, object)
    error = pyqtSignal(str)

    def __init__(self, engine, image):
        super().__init__()
        self.engine = engine
        self.image = image

    def run(self):
        try:
            extracted_data, annotated_img = self.engine.process_image(self.image)
            self.finished.emit(extracted_data, annotated_img)
        except Exception as e:
            self.error.emit(str(e))


class BatchOCRWorkerThread(QThread):
    """
    Background Thread for running OCR extraction on multiple passport images.
    """
    progress = pyqtSignal(int, int, dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, engine, image_paths):
        super().__init__()
        self.engine = engine
        self.image_paths = image_paths

    def run(self):
        results = []
        try:
            total = len(self.image_paths)
            for idx, path in enumerate(self.image_paths, 1):
                image = Image.open(path)
                data, _ = self.engine.process_image(image)
                results.append(data)
                self.progress.emit(idx, total, data)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class VIPReceiptMainWindow(QMainWindow):
    """
    Main Desktop Window for VIP Border Service & Passport AI OCR System.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI OCR Passport Scanner & VIP Border Service Receipt System (PyQt6)")
        self.resize(1300, 860)
        self.setStyleSheet(MAIN_STYLESHEET)

        # OCR Engine
        self.ocr_engine = DocumentAIEngine()

        # Build UI Layout
        self._init_ui()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🟢 System Ready | ភ្ជាប់ Tesseract OCR, Batch Group OCR & VIP Service Engine")

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Vertical Splitter (Top: Workspace | Bottom: Full-Width Saved Database Table)
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Workspace Horizontal Splitter (Left: Scanner | Right: Group Forms & Fees)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel Widget (Scanner)
        self.scanner_widget = ImageDropWidget()
        top_splitter.addWidget(self.scanner_widget)

        # Right Panel Container (Scrollable Workspace for Form & Fees)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_container = QWidget()
        right_vbox = QVBoxLayout(right_container)
        right_vbox.setContentsMargins(0, 0, 10, 0)
        right_vbox.setSpacing(14)

        # Right Panel Widgets (Group Form & Receipt Calculator)
        self.group_form_widget = GroupCustomerWidget()
        self.group_receipt_widget = GroupReceiptFeeWidget()
        self.group_receipt_widget.link_form_widget(self.group_form_widget)

        right_vbox.addWidget(self.group_form_widget)
        right_vbox.addWidget(self.group_receipt_widget)

        right_scroll.setWidget(right_container)
        top_splitter.addWidget(right_scroll)
        top_splitter.setSizes([440, 860])

        main_splitter.addWidget(top_splitter)

        # Bottom Full-Width Saved Customers Database Table Widget
        self.saved_table_widget = SavedCustomersTableWidget()
        main_splitter.addWidget(self.saved_table_widget)

        main_splitter.setSizes([620, 240])
        main_layout.addWidget(main_splitter)

        # Connect Signals - Scanner
        self.scanner_widget.image_loaded.connect(self._start_single_ocr_process)
        self.scanner_widget.batch_images_loaded.connect(self._start_batch_ocr_process)
        self.scanner_widget.webcam_btn.clicked.connect(self._open_webcam)

        # Connect Signals - Group Customers Mode
        self.group_form_widget.member_count_changed.connect(self._on_group_count_changed)
        self.group_form_widget.data_changed.connect(self._on_group_data_changed)
        self.group_form_widget.save_group_requested.connect(self._save_group_customer_record)
        self.group_receipt_widget.download_group_pdf_requested.connect(self._export_group_pdf_receipt)
        self.group_receipt_widget.download_group_png_requested.connect(self._export_group_png_receipt)
        self.group_receipt_widget.share_group_telegram_requested.connect(self._share_group_telegram)

        # Saved Records Database
        self.saved_table_widget.load_record_requested.connect(self._load_saved_customer_record)
        self.saved_table_widget.download_pdf_record_requested.connect(self._export_saved_record_pdf)
        self.saved_table_widget.download_png_record_requested.connect(self._export_saved_record_png)
        self.saved_table_widget.share_telegram_record_requested.connect(self._share_saved_record_telegram)

    def _export_saved_record_pdf(self, record):
        group_info = record.get("group_info") or {}
        members = record.get("members") or []
        fee_info = record.get("fees") or {}

        rec_inv_no = (record.get("group_data") or {}).get("receipt_no")
        receipt_data = ReceiptGenerator.generate_group_receipt_data(group_info, members, fee_info, receipt_no=rec_inv_no)

        travel_date = (receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Receipt PDF", default_filename, "PDF Files (*.pdf)")

        if file_path:
            out_file = ReceiptGenerator.export_group_pdf(receipt_data, file_path)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PDF រួចរាល់!\n\nSaved to:\n{out_file}")

    def _export_saved_record_png(self, record):
        group_info = record.get("group_info") or {}
        members = record.get("members") or []
        fee_info = record.get("fees") or {}

        rec_inv_no = (record.get("group_data") or {}).get("receipt_no")
        receipt_data = ReceiptGenerator.generate_group_receipt_data(group_info, members, fee_info, receipt_no=rec_inv_no)

        travel_date = (receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.png"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Receipt PNG Image", default_filename, "PNG Images (*.png)")

        if file_path:
            out_file = ReceiptGenerator.export_group_image(receipt_data, file_path)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PNG រួចរាល់!\n\nSaved to:\n{out_file}")

    def _share_group_telegram(self):
        group_info = self.group_form_widget.get_group_info()
        members = self.group_form_widget.get_members_list()
        fee_info = self.group_receipt_widget.get_fee_details()
        inv_no = self.group_receipt_widget.get_invoice_no()

        if not members:
            QMessageBox.warning(self, "Warning", "សូមបញ្ចូលសមាជិកក្រុមយ៉ាងហោចណាស់ ១ នាក់!")
            return

        receipt_data = ReceiptGenerator.generate_group_receipt_data(group_info, members, fee_info, receipt_no=inv_no)
        self._share_invoice_to_telegram(receipt_data, temp_prefix="Group_Receipt")

    def _share_saved_record_telegram(self, record):
        group_info = record.get("group_info") or {}
        members = record.get("members") or []
        fee_info = record.get("fees") or {}

        rec_inv_no = (record.get("group_data") or {}).get("receipt_no")
        receipt_data = ReceiptGenerator.generate_group_receipt_data(group_info, members, fee_info, receipt_no=rec_inv_no)

        self._share_invoice_to_telegram(receipt_data, temp_prefix="Saved_Receipt")

    def _share_invoice_to_telegram(self, receipt_data, temp_prefix="Invoice"):
        """
        Opens Universal Share & Export Center supporting Telegram, WhatsApp, Messenger,
        Clipboard Image, PNG, and PDF exports.
        """
        dialog = UniversalShareDialog(receipt_data, self)
        dialog.exec()

    def _on_group_count_changed(self, count):
        members = self.group_form_widget.get_members_list()
        self.group_receipt_widget.update_group_members(count, members)

    def _on_group_data_changed(self):
        members = self.group_form_widget.get_members_list()
        self.group_receipt_widget.update_group_members(len(members), members)

    def _start_single_ocr_process(self, image_source):
        """Runs OCR Engine for a single image and adds to group table."""
        if isinstance(image_source, str):
            image = Image.open(image_source)
        else:
            image = image_source

        self.status_bar.showMessage("⌛ AI Document AI កំពុងស្កេនរូបភាព (Processing OCR)...")
        self.scanner_widget.display_pil_image(image)

        self.worker = OCRWorkerThread(self.ocr_engine, image)
        self.worker.finished.connect(self._on_single_ocr_finished)
        self.worker.error.connect(self._on_ocr_error)
        self.worker.start()

    def _on_single_ocr_finished(self, extracted_data, annotated_img):
        self.scanner_widget.display_pil_image(annotated_img)
        self.group_form_widget.add_member_data(extracted_data)

        name = (
            extracted_data.get("full_english_name") or
            extracted_data.get("english_name") or
            extracted_data.get("khmer_name") or
            extracted_data.get("thai_name") or
            ""
        ).strip()
        doc_t = extracted_data.get("doc_type", "Passport")
        if name:
            if not self.group_form_widget.txt_passport_customer_name.text().strip():
                self.group_form_widget.txt_passport_customer_name.setText(name)
            self.status_bar.showMessage(f"✅ AI OCR ស្កេនជោគជ័យ! បំពេញឈ្មោះ: {name} ({doc_t}) ក្នុងតារាង")
        else:
            self.status_bar.showMessage("⚠️ AI OCR មិនបានស្រង់ឈ្មោះស្វ័យប្រវត្តទេ - សូមវាយបញ្ចូលឈ្មោះក្នុងតារាងដោយផ្ទាល់")

    def _start_batch_ocr_process(self, image_paths):
        """Runs Batch OCR Engine on multiple images and populates Group Mode."""
        self.status_bar.showMessage(f"⌛ AI កំពុងស្កេនរូបភាព Passport ចំនួន {len(image_paths)} សន្លឹក...")

        self.batch_worker = BatchOCRWorkerThread(self.ocr_engine, image_paths)
        self.batch_worker.progress.connect(self._on_batch_progress)
        self.batch_worker.finished.connect(self._on_batch_finished)
        self.batch_worker.error.connect(self._on_ocr_error)
        self.batch_worker.start()

    def _on_batch_progress(self, current, total, extracted_data):
        self.status_bar.showMessage(f"⌛ Batch OCR: កំពុងស្កេនរូបភាព {current}/{total}...")
        self.group_form_widget.add_member_data(extracted_data)
        if current == 1:
            name = (
                extracted_data.get("full_english_name") or
                extracted_data.get("english_name") or
                extracted_data.get("thai_name") or
                ""
            ).strip()
            if name and not self.group_form_widget.txt_passport_customer_name.text().strip():
                self.group_form_widget.txt_passport_customer_name.setText(name)

    def _on_batch_finished(self, results):
        self.status_bar.showMessage(f"✅ បានស្កេនរូបភាព Passport ជាក្រុមចំនួន {len(results)} សន្លឹកជោគជ័យ!")
        QMessageBox.information(self, "Batch Scan Success", f"🎉 បានស្កេនលិខិតឆ្លងដែនជាក្រុមចំនួន {len(results)} សន្លឹក រួចរាល់!\nទិន្នន័យបានធ្លាក់ចូលតារាងស្វ័យប្រវត្តិ។")

    def _on_ocr_error(self, err_msg):
        QMessageBox.warning(self, "OCR Warning", f"OCR process encountered an issue: {err_msg}")
        self.status_bar.showMessage("⚠️ OCR Process ended with warnings.")

    def _save_group_customer_record(self, group_dict):
        group_info = group_dict["group_info"]
        members = group_dict["members"]
        fee_info = self.group_receipt_widget.get_fee_details()
        inv_no = self.group_receipt_widget.get_invoice_no()

        group_receipt_data = ReceiptGenerator.generate_group_receipt_data(group_info, members, fee_info, receipt_no=inv_no)

        record = {
            "date_saved": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "customer": {
                "full_english_name": f"GROUP: {group_info['group_name']} ({len(members)} Pax)",
                "nationality": "GROUP",
                "sex": f"{len(members)} Pax"
            },
            "payment_status": fee_info.get("payment_status", "UNPAID"),
            "group_info": group_info,
            "members": members,
            "group_data": group_receipt_data,
            "fees": fee_info,
            "totals": group_receipt_data["totals"]
        }

        self.saved_table_widget.add_record(record)
        self.group_receipt_widget.advance_invoice_no(inv_no)
        QMessageBox.information(self, "Success", f"🎉 បានរក្សាទុកទិន្នន័យក្រុម [{group_info['group_name']}] (Invoice: {inv_no}) ចំនួន {len(members)} នាក់ជោគជ័យ!")
        self.status_bar.showMessage(f"✅ បានរក្សាទុកទិន្នន័យក្រុម: {group_info['group_name']} ({inv_no})")

    def _load_saved_customer_record(self, record):
        cust = record.get("customer", {})
        fees = record.get("fees", {})

        grp_info = record.get("group_info") or {}
        members = record.get("members") or []
        if not members and "group_data" in record:
            for item in record["group_data"].get("items", []):
                members.append({"full_english_name": item.get("description", "")})
        if not members and cust:
            members.append(cust)

        grp_name = grp_info.get("group_name") or record.get("group_data", {}).get("customer_name") or cust.get("full_english_name", "Group")
        cust_name = grp_info.get("customer_name") or ""
        travel_dt = grp_info.get("travel_date") or record.get("group_data", {}).get("date_str") or cust.get("travel_date", "")

        self.group_form_widget.txt_group_name.setText(grp_name)
        if cust_name:
            self.group_form_widget.txt_passport_customer_name.setText(cust_name)
        if travel_dt:
            self.group_form_widget.txt_group_travel_date.setText(travel_dt)
        self.group_form_widget.members_table.setRowCount(0)
        for m in members:
            self.group_form_widget.add_member_data(m)

        self.group_receipt_widget.set_fee_details(fees)
        inv_no = record.get("group_data", {}).get("receipt_no")
        if inv_no:
            self.group_receipt_widget.txt_invoice_no.setText(inv_no)

        self.status_bar.showMessage(f"📂 បានទាញយកទិន្នន័យ [{grp_name}] ចំនួន {len(members)} នាក់ រួចរាល់!")

    def _open_webcam(self):
        dialog = WebcamDialog(self)
        dialog.image_captured.connect(self._start_single_ocr_process)
        dialog.exec()

    def _export_group_pdf_receipt(self):
        group_info = self.group_form_widget.get_group_info()
        members = self.group_form_widget.get_members_list()
        fee_info = self.group_receipt_widget.get_fee_details()
        inv_no = self.group_receipt_widget.get_invoice_no()

        if not members:
            QMessageBox.warning(self, "Warning", "សូមបញ្ចូលសមាជិកក្រុមយ៉ាងហោចណាស់ ១ នាក់!")
            return

        travel_date = (receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Group Receipt PDF", default_filename, "PDF Files (*.pdf)")

        if file_path:
            out_file = ReceiptGenerator.export_group_pdf(receipt_data, file_path)
            self.group_receipt_widget.advance_invoice_no(inv_no)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PDF រួចរាល់ (Invoice: {inv_no})!\n\nSaved to:\n{out_file}")

    def _export_group_png_receipt(self):
        group_info = self.group_form_widget.get_group_info()
        members = self.group_form_widget.get_members_list()
        fee_info = self.group_receipt_widget.get_fee_details()
        inv_no = self.group_receipt_widget.get_invoice_no()

        if not members:
            QMessageBox.warning(self, "Warning", "សូមបញ្ចូលសមាជិកក្រុមយ៉ាងហោចណាស់ ១ នាក់!")
            return

        travel_date = (receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.png"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Group Receipt PNG Image", default_filename, "PNG Images (*.png)")

        if file_path:
            out_file = ReceiptGenerator.export_group_image(receipt_data, file_path)
            self.group_receipt_widget.advance_invoice_no(inv_no)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PNG រួចរាល់ (Invoice: {inv_no})!\n\nSaved to:\n{out_file}")


def excepthook(exc_type, exc_value, exc_tb):
    import traceback
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("Uncaught exception:", err_msg)
    try:
        QMessageBox.critical(None, "Application Error", f"មានបញ្ហាកើតឡើង:\n\n{exc_value}")
    except Exception:
        pass

sys.excepthook = excepthook


def main():
    app = QApplication(sys.argv)
    window = VIPReceiptMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
