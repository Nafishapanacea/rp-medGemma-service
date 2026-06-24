DICOM_TEMP_PATH= '/home/omen/Documents/rp-medGemma-service/tmp/dicom_uploads'

json_regex = r"```json\s*(\{.*?\})\s*```"


ABNORMALITY_MAP_MR = {
    "Lesion": r"\blesion\b",
    "Mass": r"\bmass\b",
    "Tumor": r"\btumou?r\b",
    "Metastasis": r"\bmetastasis\b",
    "Hemorrhage": r"\bhemorrhage\b",
    "Infarct": r"\binfarct(?:ion)?\b",
    "Edema": r"\bedema\b",
    "Hydrocephalus": r"\bhydrocephalus\b",
    "White Matter Abnormality": r"\bwhite matter abnormalit",
    "Extra-axial Lesion": r"\bextra[- ]axial\b",
    "Vascular Abnormality": r"\bvascular abnormalit",
    "Postoperative Change": r"\bpostoperative change",
    "Atrophy": r"\batrophy\b",
    "Signal Abnormality": r"\bsignal abnormalit",
    "Midline Shift": r"\bmidline shift\b",
    "Mass Effect": r"\bmass effect\b",
    "Cystic Lesion": r"\bcyst(?:ic)? lesion\b|\bcyst\b",
    "Encephalomalacia": r"\bencephalomalacia\b",
    "Demyelinating Disease": r"\bdemyelinating\b",
    "Calcification": r"\bcalcification\b",
    "Skull Fracture": r"\bskull fracture\b"
}

ABNORMALITY_MAP_CT = {
    "Lesion": r"\blesion\b",
    "Mass": r"\bmass\b",
    "Tumor": r"\btumou?r\b",
    "Hemorrhage": r"\bhemorrhage\b",
    "Infarct": r"\binfarct(?:ion)?\b",
    "Edema": r"\bedema\b",
    "Hydrocephalus": r"\bhydrocephalus\b",
    "White Matter Abnormality": r"\bwhite matter abnormalit",
    "Extra-axial Lesion": r"\bextra[- ]axial\b",
    "Vascular Abnormality": r"\bvascular abnormalit",
    "Postoperative Change": r"\bpostoperative change",
    "Atrophy": r"\batrophy\b",
    "Signal Abnormality": r"\bsignal abnormalit",
    "Midline Shift": r"\bmidline shift\b",
    "Mass Effect": r"\bmass effect\b",
    "Cystic Lesion": r"\bcyst(?:ic)? lesion\b|\bcyst\b",
    "Encephalomalacia": r"\bencephalomalacia\b",
    "Demyelinating Disease": r"\bdemyelinating\b",
    "Calcification": r"\bcalcification\b",
    "Skull Fracture": r"\bskull fracture\b"
}
 
 
NEGATION_PATTERNS = [
    r"\bno\b",
    r"\bno evidence of\b",
    r"\bwithout\b",
    r"\babsence of\b",
    r"\bnegative for\b",
    r"\bnot seen\b",
    r"\bfree of\b"
]



brain_patterns = [
        r"\bbrain\b",
        r"\bpons\b",
        r"\bcerebral\b",
        r"\bcerebell",
        r"\bventricles\b",
        r"\bintracranial\b"
    ]
 
chest_patterns = [
        r"\blung",
        r"\bpleural",
        r"\bpneumothorax",
        r"\bmediast",
        r"\bcardiomediast"
    ]
