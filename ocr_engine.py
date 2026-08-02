"""
OCR and Document AI Processing Engine supporting Thai, English, and Khmer Passport/ID Cards
"""

import re
import os
import cv2
import numpy as np
from PIL import Image

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
except Exception:
    RAPIDOCR_AVAILABLE = False


FORBIDDEN_NAME_WORDS = {
    # Countries & Sovereignties
    'KINGDOM', 'OF', 'THAILAND', 'CAMBODIA', 'VIETNAM', 'LAOS', 'MYANMAR', 'CHINA',
    'REPUBLIC', 'FEDERATION', 'UNITED', 'STATES', 'AMERICA', 'JAPAN', 'KOREA',
    'KINGDOMOFTHAILAND', 'KINGDOMOFCAMBODIA', 'REPUBLICOFKOREA', 'PEOPLESREPUBLIC',
    'THAILANDKINGDOM', 'CAMBODIAKINGDOM', 'VIETNAMREPUBLIC', 'SOCIALIST',

    # Country Codes & Common Misreads
    'THA', 'KHM', 'VNM', 'USA', 'LAO', 'MMR', 'CHN', 'GBR', 'FRA', 'DEU', 'AUS',
    'IND', 'JPN', 'KOR', 'RUS', 'SGP', 'MYS', 'TWN', 'PHL', 'IDN', 'CAN', 'NZL',
    'ESP', 'ITA', 'NLD', 'BEL', 'SWE', 'NOR', 'CHE', 'AUT', 'POL', 'TUR', 'ISR',
    'UISIN', 'VSTIN', 'USINN', 'UISN', 'VSTN', 'USIN', 'VNMNG', 'USIC', 'USAC',
    'TH', 'TE', 'TO', 'NO', 'DO', 'DU', 'DE', 'LA', 'ST',

    # Country Labels & Field Header Words (and OCR misreads)
    'COUNTRY', 'COUNTRYCODE', 'COUNTIYCODE', 'COUNTYCODE', 'COUNTRICODE', 'COUNTRYCODES',
    'COUNTIY', 'COUNTY', 'COUNTR', 'COUTRY', 'COUTRYCODE', 'CODEDUPAYS',
    'CODE', 'CODES', 'PAYS', 'DU', 'EMISSION', 'EMETTEUR', 'ISSUING', 'AUTHORITY',
    'NATIONALITY', 'NATIONAL', 'NATION', 'STATE', 'GOVERNMENT',
    'IDENTIFICATION', 'INDIVIDUAL', 'SIGNATURE', 'BEARER', 'HOLDER', 'HOLDERS',

    # Common OCR Label Misreads from Passport headers / Passport No / Signature
    'PAISPOFTNO', 'PASTPONTNO', 'PASSPORTNO', 'PASPOFTNO', 'PAISPORTNO', 'PASSPOR', 'PASPO',
    'WILOCHUNSNS', 'WUOLLENKUNUNV', 'DONGALNE', 'INTIWINDA', 'ININNINDE', 'INNWUINDA',
    'NAMEIN', 'THAL', 'NAMEINTHAL', 'IDENT', 'IDENTIF', 'SIGN', 'SIGNA',

    # Thai Provinces & Cities (commonly misread from Place of Birth)
    'BANGKOK', 'NONTHABURI', 'PATHUM', 'THANI', 'CHIANG', 'MAI', 'RAI', 'CHONBURI',
    'PHUKET', 'SAMUT', 'PRAKAN', 'SAKHON', 'SONGKHLA', 'RAYONG', 'KANCHANABURI',
    'TAK', 'SAKAEW', 'SAKAEO', 'SURIN', 'BURIRAM', 'SISAKET', 'UBON', 'RATCHATHANI',
    'PRACHIN', 'BURI', 'PRACHINBURI', 'YALA', 'NARATHIWAT', 'KRABI', 'SURAT',
    'UDON', 'KHON', 'KAEN', 'NAKHON', 'RATCHASIMA', 'PATHOM', 'SAWAN', 'SI',
    'THAMMARAT', 'PATTANI', 'PHETCHABURI', 'PHETCHABUN', 'PHITSANULOK', 'RATCHABURI',
    'SARABURI', 'TRAT', 'CHACHOENGSAO', 'LAMPANG', 'LAMPHUN', 'LOEI', 'PHRAE',
    'PHATTHALUNG', 'PHAYAO', 'PICHIT', 'RANONG', 'SATUN', 'SINGBURI', 'SUKHOTHAI',
    'SUPHAN', 'TRANG', 'NAN', 'MUKDAHAN', 'YASOTHON', 'AMNAT', 'CHAROEN',

    # Cambodian Provinces & Cities
    'PHNOM', 'PENH', 'PHNOMPENH', 'SIEM', 'REAP', 'BATTAMBANG', 'TAKEO', 'KAMPOT',
    'KAMPONG', 'CHHNANG', 'CHAM', 'THOM', 'SPEU', 'SIHANOUKVILLE', 'PREAH', 'SIHANOUK',
    'KANDAL', 'SVAY', 'RIENG', 'PREY', 'VENG', 'KOH', 'KONG', 'MONDULKIRI',
    'RATANAKIRI', 'STUNG', 'TRENG', 'PURSAT', 'ODDAR', 'MEANCHEY', 'PAILIN', 'TBOUNG',

    # Document Header Terms & Labels
    'PASSPORT', 'DOCUMENT', 'AUTHORITY', 'MINISTRY', 'FOREIGN', 'AFFAIRS',
    'NATIONALITY', 'PERSONAL', 'NO', 'TYPE', 'CODE', 'DATE', 'BIRTH', 'EXPIRY',
    'ISSUE', 'EXPIRE', 'SEX', 'GENDER', 'SIGNATURE', 'HOLDER', 'BEARER', 'DEPARTMENT',
    'STATE', 'TRAVEL', 'ROYAL', 'GOVERNMENT', 'PHOTO', 'AREA', 'SCAN', 'DETAILS',
    'GIVEN', 'NAMES', 'SURNAME', 'NAME', 'LAST', 'FIRST', 'FAMILY', 'MIDDLE', 'TITLE',
    'MR', 'MRS', 'MISS', 'MS', 'DR', 'PROF', 'REV', 'MASTER', 'MADAM', 'SIR', 'NAI', 'NANG', 'NANGSAO',
    'THAI', 'KHMER', 'OFFICIAL', 'INVOICE', 'VIP', 'SERVICE', 'BORDER', 'CHECKPOINT',
    'NOM', 'NOMS', 'PRENOMS', 'PRENOM', 'PRÉNOMS', 'PRÉNOM', 'FORENAMES', 'FORENAME', 'APELLIDOS', 'NOMBRES', 'TITULAR', 'FIRMA', 'AUTORIDAD', 'CAN', 'IMMIGRATION',
    'REGISTERED', 'CIVIL', 'REGISTRATION', 'OFFICE', 'ISSUING', 'PLACE', 'BIRTHPLACE',
    'ADDRESS', 'PERMANENT', 'RESIDENCE', 'IDENTITY', 'CARD', 'HEIGHT', 'INCHES',
    'CUSTOMER', 'PASSPORT CUSTOMER',
    'UNUNNE', 'UNUN', 'UNNAME', 'NONAME', 'UNKNOWN', 'UNDEFINED', 'NULL', 'NIL', 'NONE', 'NOTSTATED', 'UNSPECIFIED',
    'ORT', 'PORT', 'PAGE', 'ZONE', 'SIGN', 'SIGNATURE', 'STAMP', 'SEAL', 'MRZ'
}


def clean_person_name(name_str):
    """
    Sanitizes candidate name strings by stripping non-alpha characters and filtering
    out forbidden document header words, country codes, province names, and OCR garbage.
    """
    if not name_str:
        return ""

    import unicodedata
    nfkd = unicodedata.normalize('NFKD', name_str)
    ascii_str = "".join([c for c in nfkd if not unicodedata.combining(c)])
    upper_line = ascii_str.upper()

    # Reject line if it contains structural document headers or country code labels
    forbidden_line_headers = [
        'PASSPORT', 'NATIONALITY', 'DATE OF BIRTH', 'DATE OF ISSUE', 'DATE OF EXPIRY',
        'EXPIRY', 'IDENTIFICATION', 'MINISTRY OF', 'FOREIGN AFFAIRS', 'KINGDOM OF',
        'COUNTRY CODE', 'COUNTRYCODE', 'COUNTIYCODE', 'COUNTYCODE', 'CODE DU PAYS',
        'PAYS EMETTEUR', 'PAYS D\'EMISSION', 'TYPE / TYPE', 'DOCUMENT NO', 'PASSPORT NO',
        'PLACE OF BIRTH', 'AUTHORITY', 'REPUBLIC OF', 'STATE OF', 'ISSUING AUTHORITY',
        'SIGNATURE OF', 'BEARER OF'
    ]
    if any(h in upper_line for h in forbidden_line_headers):
        return ""

    clean = re.sub(r'[^A-Z\s]', ' ', upper_line).strip()
    words = clean.split()

    forbidden_substrings = [
        'KINGDOM', 'THAILAND', 'CAMBODIA', 'PASSPORT', 'REPUBLIC', 'MINISTRY',
        'BIRTHPLACE', 'NATIONALITY', 'AUTHORITY', 'COUNTRY', 'COUNTI', 'COUNTY',
        'COUNTR', 'CODE', 'PAYS', 'DOCUMENT', 'CARD', 'OFFICE', 'RESIDEN',
        'ADDRESS', 'GIVEN', 'SURNAME', 'SIGNATURE', 'HOLDER', 'BEARER', 'IDENTIF'
    ]

    valid_words = []
    for w in words:
        if len(w) >= 2 and w not in FORBIDDEN_NAME_WORDS:
            # Check substring matches
            if any(fw in w for fw in forbidden_substrings):
                continue
            # Regex check for misreads of PASSPORT NO / IDENTIFICATION / SIGNATURE
            if re.search(r'P[A-Z]*P[O0]R', w) or re.search(r'P[A-Z]*N[O0]$', w):
                continue
            if re.search(r'I[NTV1i]{2,}', w) and len(w) > 6:
                continue
            # Reject words with 3 consecutive identical letters (OCR garbage like NNN, UUU, LLL)
            if re.search(r'([A-Z])\1\1', w):
                continue
            # Require at least one vowel in words >= 3 chars (unless THAI/KHMER common name fragment)
            if len(w) >= 3 and not re.search(r'[AEIOUY]', w):
                continue
            valid_words.append(w)

    if not valid_words:
        return ""

    # If only 1-2 short words like 'TH', 'TE' remain, reject
    if len(valid_words) == 1 and len(valid_words[0]) <= 3:
        return ""
    if len(valid_words) == 2 and all(len(w) <= 2 for w in valid_words):
        return ""

    return " ".join(valid_words)


class DocumentAIEngine:
    """
    Intelligent Passport & ID Card OCR Extraction Engine.
    Handles Thai, English, and Khmer text detection and structured field parsing.
    """

    def __init__(self):
        self.tesseract_available = PYTESSERACT_AVAILABLE
        self.rapid_ocr = None
        
        if RAPIDOCR_AVAILABLE:
            try:
                self.rapid_ocr = RapidOCR()
            except Exception as e:
                print(f"RapidOCR init notice: {e}")

        # Check if tesseract binary is accessible on Windows
        if self.tesseract_available:
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
            ]
            for p in common_paths:
                expanded = os.path.expandvars(p)
                if os.path.exists(expanded):
                    pytesseract.pytesseract.tesseract_cmd = expanded
                    break

    def process_image(self, image_path_or_pil):
        """
        Process document image and return extracted structured data + processed image with overlay boxes.
        """
        if isinstance(image_path_or_pil, str):
            image = Image.open(image_path_or_pil)
        else:
            image = image_path_or_pil

        # Downscale large high-res camera photos to max 1600px for 5x faster OCR
        w, h = image.size
        if max(w, h) > 1600:
            ratio = 1600.0 / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to OpenCV BGR format
        cv_img = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
        raw_text = ""

        # 1. Primary OCR: RapidOCR (No Tesseract binary required on Windows)
        if self.rapid_ocr is not None:
            try:
                res, _ = self.rapid_ocr(cv_img)
                if res:
                    ocr_lines = [item[1] for item in res if item and len(item) > 1 and item[1]]
                    raw_text = "\n".join(ocr_lines)
            except Exception as e:
                print(f"RapidOCR process notice: {e}")

        # 2. Secondary OCR: Pytesseract fallback
        if not raw_text and self.tesseract_available:
            try:
                raw_text = pytesseract.image_to_string(cv_img, lang='tha+eng+khm')
            except Exception:
                try:
                    raw_text = pytesseract.image_to_string(cv_img, lang='eng')
                except Exception:
                    raw_text = ""

        # Structured data extraction result dictionary
        extracted_data = {
            "doc_type": "Unknown Document",
            "passport_no": "",
            "thai_name": "",
            "english_surname": "",
            "english_given_names": "",
            "full_english_name": "",
            "khmer_name": "",
            "dob": "",
            "sex": "",
            "nationality": "",
            "expiry_date": "",
            "issue_date": "",
            "raw_text": raw_text
        }

        # Run smart pattern analysis & rule parser
        extracted_data = self._parse_structured_fields(raw_text, extracted_data, cv_img)

        # Draw visual bounding box overlays for recognized text blocks
        annotated_cv = self._annotate_image(cv_img, extracted_data)
        annotated_pil = Image.fromarray(cv2.cvtColor(annotated_cv, cv2.COLOR_BGR2RGB))

        return extracted_data, annotated_pil

    def _parse_structured_fields(self, text, data, cv_img):
        """
        Apply Regex & Rule-based extraction logic for Passport MRZ, Thai Passports, and ID cards.
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 1. MRZ (Machine Readable Zone) Detection for International Passports
        for line in lines:
            clean_l = re.sub(r'<\s*<', '<<', line.upper().replace(' ', ''))
            is_mrz1 = ('<<' in clean_l) or (len(clean_l) >= 25 and '<' in clean_l and bool(re.match(r'^P<[A-Z]{3}', clean_l)))
            if is_mrz1:
                if '<<' in clean_l:
                    parts = clean_l.split('<<', 1)
                    raw_sur = parts[0]
                    raw_given = parts[1] if len(parts) > 1 else ""
                else:
                    tokens = [t for t in clean_l.split('<') if t]
                    if len(tokens) >= 2:
                        raw_sur = tokens[0]
                        raw_given = '<'.join(tokens[1:])
                    else:
                        raw_sur = clean_l
                        raw_given = ""

                # Remove leading P< or P and 3-letter Country Code (e.g., P<THA, PTHAI, P<KHM, P<USA)
                prefix_match = re.match(r'^(?:P[<A-Z0-9]?)[A-Z]{3}', raw_sur)
                if prefix_match:
                    sur_clean = raw_sur[prefix_match.end():]
                else:
                    sur_clean = re.sub(r'^P[<A-Z0-9]?', '', raw_sur)
                sur_clean = sur_clean.replace('<', ' ').strip()

                # Extract all given & middle names separated by < before MRZ padding
                raw_given_clean = re.split(r'<{2,}', raw_given)[0] if '<' in raw_given else raw_given
                given_clean = raw_given_clean.replace('<', ' ').strip()

                sur = clean_person_name(sur_clean)
                given = clean_person_name(given_clean)

                if sur or given:
                    if sur:
                        data["english_surname"] = sur
                    if given:
                        data["english_given_names"] = given
                    if sur and given:
                        data["full_english_name"] = f"{sur} {given}".strip()
                    elif sur:
                        data["full_english_name"] = sur
                    elif given:
                        data["full_english_name"] = given
                    data["doc_type"] = "Passport (MRZ Detected)"
                    break

        # 1b. MRZ Line 2 Detection (Passport No, Nat, DOB, Sex)
        for line in lines:
            clean_l = line.upper().replace(' ', '')
            mrz2_match = re.search(r'([A-Z0-9]{7,9})\d([A-Z]{3})(\d{6})\d([MF])(\d{6})', clean_l)
            if mrz2_match:
                if not data["passport_no"]:
                    data["passport_no"] = mrz2_match.group(1)
                if not data["nationality"]:
                    data["nationality"] = mrz2_match.group(2)
                raw_dob = mrz2_match.group(3)
                raw_sex = mrz2_match.group(4)
                if not data["dob"] and len(raw_dob) == 6:
                    yy, mm, dd = raw_dob[:2], raw_dob[2:4], raw_dob[4:6]
                    year = f"19{yy}" if int(yy) > 30 else f"20{yy}"
                    data["dob"] = f"{dd}/{mm}/{year}"
                if not data["sex"]:
                    data["sex"] = "M (Male / ชาย)" if raw_sex == 'M' else "F (Female / หญิง)"
                break

        # 2. Thai Language Name Pattern Matching (นาย / นาง / นางสาว / เด็กชาย / เด็กหญิง)
        thai_name_match = re.search(r'(นาย|นาง|นางสาว|เด็กชาย|เด็กหญิง)\s*([\u0e00-\u0e7f\s]+)', text)
        if thai_name_match:
            data["thai_name"] = thai_name_match.group(0).strip()
            if data["doc_type"] == "Unknown Document":
                data["doc_type"] = "Thai Passport / Document"

        # 3. Search Passport Number fallback patterns
        if not data["passport_no"]:
            pno_match = re.search(r'(?:PASSPORT NO|PASSPORT|NO\.|เลขที่หนังสือเดินทาง)\s*[:\.]?\s*([A-Z0-9]{7,9})', text, re.IGNORECASE)
            if pno_match:
                data["passport_no"] = pno_match.group(1)
            else:
                generic_pno = re.search(r'\b[A-Z]{1,2}[0-9]{7,8}\b', text)
                if generic_pno:
                    data["passport_no"] = generic_pno.group(0)

        # 4. Search English Name via Labels (Same line & Multi-line lookahead up to 3 lines)
        if not data.get("english_surname") or not data.get("english_given_names"):
            for i, line in enumerate(lines):
                import unicodedata
                nfkd = unicodedata.normalize('NFKD', line)
                ascii_line = "".join([c for c in nfkd if not unicodedata.combining(c)])
                upper_raw = re.sub(r'[^A-Z\s/:]', ' ', ascii_line.upper())

                if not data.get("english_surname") and re.search(r'\b(SURNAME|LAST NAME|FAMILY NAME|NOM|NOMS|APELLIDOS)\b', upper_raw):
                    after_label = re.sub(r'.*?\b(SURNAME|LAST NAME|FAMILY NAME|NOM|NOMS|APELLIDOS|นามสกุล|ត្រកូល)\b[/\s:]*', '', upper_raw).strip()
                    val = clean_person_name(after_label)
                    if val:
                        data["english_surname"] = val
                    else:
                        for offset in range(1, 4):
                            if i + offset < len(lines):
                                next_val = clean_person_name(lines[i+offset])
                                if next_val and next_val != data.get("english_given_names"):
                                    data["english_surname"] = next_val
                                    break

                if not data.get("english_given_names") and re.search(r'\b(GIVEN NAMES|GIVEN NAME|FIRST NAME|TITLE / NAME|TITLE NAME|PRENOMS|PRENOM|FORENAMES|FORENAME|NOMBRES)\b', upper_raw):
                    after_label = re.sub(r'.*?\b(GIVEN NAMES|GIVEN NAME|FIRST NAME|TITLE / NAME|TITLE NAME|PRENOMS|PRENOM|FORENAMES|FORENAME|NOMBRES|ชื่อ|ឈ្មោះ)\b[/\s:]*', '', upper_raw).strip()
                    val = clean_person_name(after_label)
                    if val:
                        data["english_given_names"] = val
                    else:
                        for offset in range(1, 4):
                            if i + offset < len(lines):
                                next_val = clean_person_name(lines[i+offset])
                                if next_val and next_val != data.get("english_surname"):
                                    data["english_given_names"] = next_val
                                    break

        # Re-evaluate full_english_name after Label search
        sur = data.get("english_surname", "")
        given = data.get("english_given_names", "")
        if sur and given:
            data["full_english_name"] = f"{sur} {given}".strip()

        # 5. Fallback Uppercase English Name Scanner across multi-lines if still missing components
        if not data.get("full_english_name") or not data.get("english_surname") or not data.get("english_given_names"):
            valid_candidates = []
            for line in lines:
                cleaned_line = clean_person_name(line)
                if cleaned_line:
                    tokens = cleaned_line.split()
                    if len(tokens) >= 2 and not data.get("full_english_name"):
                        data["full_english_name"] = cleaned_line
                        data["english_surname"] = tokens[0]
                        data["english_given_names"] = " ".join(tokens[1:])
                        break
                    else:
                        for tok in tokens:
                            if tok not in valid_candidates:
                                valid_candidates.append(tok)

            if (not data.get("full_english_name") or not data.get("english_surname") or not data.get("english_given_names")) and len(valid_candidates) >= 2:
                if not data.get("english_surname") and not data.get("english_given_names"):
                    data["english_surname"] = valid_candidates[0]
                    data["english_given_names"] = " ".join(valid_candidates[1:])
                    data["full_english_name"] = f"{data['english_surname']} {data['english_given_names']}".strip()
                elif not data.get("english_given_names") and data.get("english_surname"):
                    cand_given = [w for w in valid_candidates if w != data["english_surname"]]
                    if cand_given:
                        data["english_given_names"] = " ".join(cand_given[:2])
                        data["full_english_name"] = f"{data['english_surname']} {data['english_given_names']}".strip()
                elif not data.get("english_surname") and data.get("english_given_names"):
                    cand_sur = [w for w in valid_candidates if w not in data["english_given_names"].split()]
                    if cand_sur:
                        data["english_surname"] = cand_sur[0]
                        data["full_english_name"] = f"{data['english_surname']} {data['english_given_names']}".strip()

        # Final safety check for full_english_name
        sur = data.get("english_surname", "")
        given = data.get("english_given_names", "")
        if sur and given:
            data["full_english_name"] = f"{sur} {given}".strip()
        elif given and not data.get("full_english_name"):
            data["full_english_name"] = given
        elif sur and not data.get("full_english_name"):
            data["full_english_name"] = sur

        # 6. Search Khmer Name Patterns
        khmer_match = re.search(r'([\u1780-\u17ff\s]{3,40})', text)
        if khmer_match and len(khmer_match.group(0).strip()) >= 3:
            data["khmer_name"] = khmer_match.group(0).strip()

        # 7. DOB (Date of Birth) Pattern
        dob_match = re.search(r'(?:DATE OF BIRTH|DOB|เกิดวันที่|ថ្ងៃខែឆ្នាំកំណើត)\s*[:\.]?\s*(\d{1,2}[\/\-\s][A-Za-z0-9]+[\/\-\s]\d{2,4})', text, re.IGNORECASE)
        if dob_match:
            data["dob"] = dob_match.group(1)
        else:
            generic_date = re.search(r'\b(\d{2}[\s\/\-][0-9A-Z]{3,8}[\s\/\-]\d{4})\b', text)
            if generic_date:
                data["dob"] = generic_date.group(0)

        # 8. Sex / Gender
        sex_match = re.search(r'(?:SEX|GENDER|เพศ|ភេទ)\s*[:\.]?\s*([MF|ชาย|หญิง|ประុស|ស្រី])', text, re.IGNORECASE)
        if sex_match:
            val = sex_match.group(1).upper()
            if val in ['M', 'ชาย', 'ประុស']:
                data["sex"] = "M (Male / ชาย)"
            elif val in ['F', 'หญิง', 'ស្រី']:
                data["sex"] = "F (Female / หญิง)"

        # 9. Nationality
        nat_match = re.search(r'(?:NATIONALITY|សញ្ជាតិ|สัญชาติ)\s*[:\.]?\s*([A-Z]{3}|THAI|CAMBODIAN)', text, re.IGNORECASE)
        if nat_match:
            data["nationality"] = nat_match.group(1).upper()

        if data["full_english_name"]:
            data["full_english_name"] = clean_person_name(data["full_english_name"])

        if data["full_english_name"] and data["doc_type"] == "Unknown Document":
            data["doc_type"] = "Passport / Document"

        return data

    def _annotate_image(self, cv_img, data):
        """
        Draw visual bounding box overlays and status banner on the processed OpenCV image.
        """
        annotated = cv_img.copy()
        h, w, _ = annotated.shape

        cv2.rectangle(annotated, (0, 0), (w, 50), (30, 41, 59), -1)
        doc_type_text = f"AI OCR STATUS: {data['doc_type']} Detected"
        cv2.putText(annotated, doc_type_text, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (52, 211, 153), 2)

        face_x1, face_y1 = int(w * 0.08), int(h * 0.25)
        face_x2, face_y2 = int(w * 0.38), int(h * 0.85)
        cv2.rectangle(annotated, (face_x1, face_y1), (face_x2, face_y2), (99, 102, 241), 2)

        text_x1, text_y1 = int(w * 0.42), int(h * 0.15)
        text_x2, text_y2 = int(w * 0.95), int(h * 0.88)
        cv2.rectangle(annotated, (text_x1, text_y1), (text_x2, text_y2), (16, 185, 129), 2)

        return annotated
