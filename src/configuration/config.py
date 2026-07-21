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
    # Neuro / General
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
    "Skull Fracture": r"\bskull fracture\b",
    
    # Chest Specific (ADDED)
    "Ground Glass Opacity": r"\bground[- ]glass\b",
    "Consolidation": r"\bconsolidation\b",
    "Pulmonary Fibrosis": r"\bfibrosis\b",
    "Reticulation": r"\breticulation\b",
    "Honeycombing": r"\bhoneycombing\b",
    "Nodule": r"\bnodule\b",
    "Pleural Effusion": r"\bpleural effusion\b|\beffusion\b",
    "Pneumothorax": r"\bpneumothorax\b",
    "Atelectasis": r"\batelectasis\b",
    "Interstitial Thickening": r"\binterstitial thickening\b|\binterstitial disease\b",
    
    # Abdomen Specific (ADDED)
    "Ascites / Free Fluid": r"\bascites\b|\bfree fluid\b",
    "Bowel Obstruction": r"\bobstruction\b",
    "Lymphadenopathy": r"\blymphadenopathy\b|\benlarged nodes\b",
    "Organomegaly": r"\borganomegaly\b|\bhepatomegaly\b|\bsplenomegaly\b",
    "Bowel Wall Thickening": r"\bwall thickening\b"
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



# # Expanded Anatomy Patterns (Head to Toe Coverage)
# abdomen_patterns = [r"\babdomen\b", r"\bkub\b", r"\bliver\b", r"\bspleen\b", r"\bkidneys?\b", r"\brenal\b", r"\bpancreas\b", r"\bperitoneum\b"]
# pelvis_patterns = [r"\bpelvis\b", r"\bhip\b", r"\bbladder\b", r"\bprostate\b", r"\buterus\b", r"\bsacrum\b", r"\biliac\b"]
# spine_patterns = [r"\bspine\b", r"\bcervical\b", r"\bthoracic\b", r"\blumbar\b", r"\bvertebra\b", r"\bsacral\b", r"\bcoccyx\b"]
# extremity_patterns = [r"\barm\b", r"\bleg\b", r"\bhand\b", r"\bfoot\b", r"\bfinger\b", r"\btoe\b", r"\bfemur\b", r"\btibia\b", r"\bfibula\b", r"\bhumerus\b", r"\bradius\b", r"\bulna\b", r"\bpatella\b", r"\bknee\b", r"\bankle\b", r"\bshoulder\b", r"\belbow\b", r"\bwrist\b", r"\bclavicle\b", r"\bscapula\b"]

# # Mapping dictionaries for regex validation loops
# BODY_PART_RE_MAP = {
#     "head": brain_patterns, # matches your existing variable name
#     "chest": chest_patterns,
#     "abdomen": abdomen_patterns,
#     "pelvis": pelvis_patterns,
#     "spine": spine_patterns,
#     "extremity": extremity_patterns
# }



# Expanded Anatomy Patterns (Forgiving/Greedy Matches)

brain_patterns = [
    r"brain", r"pons", r"cerebral", r"cerebell", 
    r"ventricles", r"intracranial", r"head", r"neuro", r"skull"
]
 
chest_patterns = [
    r"chest", r"thorax", r"lung", r"pleural", 
    r"pneumothorax", r"mediast", r"cardiomediast"
]

abdomen_patterns = [
    r"abdomen", r"abdo", r"abd", r"kub", r"liver", 
    r"spleen", r"kidney", r"renal", r"pancreas", r"peritoneum"
]

pelvis_patterns = [
    r"pelvis", r"pelvic", r"hip", r"bladder", 
    r"prostate", r"uterus", r"sacrum", r"iliac"
]

spine_patterns = [
    r"spine", r"c-spine", r"t-spine", r"l-spine", 
    r"cervical", r"thoracic", r"lumbar", r"vertebra", r"sacral", r"coccyx"
]

extremity_patterns = [
    r"arm", r"leg", r"hand", r"foot", r"finger", r"toe", 
    r"femur", r"tibia", r"fibula", r"humerus", r"radius", 
    r"ulna", r"patella", r"knee", r"ankle", r"shoulder", 
    r"elbow", r"wrist", r"clavicle", r"scapula"
]

# Mapping dictionaries for regex validation loops
BODY_PART_RE_MAP = {
    "head": brain_patterns, 
    "chest": chest_patterns,
    "abdomen": abdomen_patterns,
    "pelvis": pelvis_patterns,
    "spine": spine_patterns,
    "extremity": extremity_patterns
}
# Standardized Allowed Vocabulary Mapping for Radiographs (CR/XA/DX)
ABNORMALITY_MAP_CR = {
    "Atelectasis": r"\batelectasis\b",
    "Consolidation": r"\bconsolidation\b",
    "Infiltration": r"\binfiltration\b",
    "Pneumothorax": r"\bpneumothorax\b",
    "Edema": r"\bedema\b",
    "Emphysema": r"\bemphysema\b",
    "Fibrosis": r"\bfibrosis\b",
    "Effusion": r"\beffusion\b|\bpleural effusion\b",
    "Pneumonia": r"\bpneumonia\b",
    "Pleural_Thickening": r"\bpleural thickening\b",
    "Cardiomegaly": r"\bcardiomegaly\b",
    "Nodule": r"\bnodule\b",
    "Mass": r"\bmass\b",
    "Hernia": r"\bhernia\b",
    "Lung Lesion": r"\blung lesion\b",
    "Fracture": r"\bfracture\b",
    "Lung Opacity": r"\blung opacity\b|\bopacity\b",
    "Enlarged Cardiomediastinum": r"\benlarged cardiomediastinum\b",
    "Tuberculosis": r"\btuberculosis\b"
}
