from model.model import model
from PIL import Image
import cv2
import base64
import pydicom
import numpy as np
import re
import io
import json
import os
import glob
import requests
from collections import defaultdict
from src.configuration.config import json_regex, ABNORMALITY_MAP_MR, ABNORMALITY_MAP_CT, NEGATION_PATTERNS, brain_patterns, chest_patterns,BODY_PART_RE_MAP, ABNORMALITY_MAP_CR



def download_study_zip(pacs_url: str, study_id: str, auth_cred: str, output_zip_path: str):
    """Downloads the study ZIP from Orthanc to the specified local path."""
    download_url = f"{pacs_url}/studies/{study_id}/archive"
    headers = {"Accept": "application/zip"}
    
    if auth_cred:
        headers["Authorization"] = auth_cred

    with requests.get(download_url, headers=headers, stream=True) as r:
        r.raise_for_status()  # Raise error if Orthanc returns 404/401
        with open(output_zip_path, 'wb') as out_file:
            for chunk in r.iter_content(chunk_size=8192):
                out_file.write(chunk)
                
    return output_zip_path


def get_best_image_series(temp_dir: str):
    """Scans a directory for DICOMs, ignores SEG/SR/etc., and returns paths for the largest series."""
    raw_file_paths  = glob.glob(os.path.join(temp_dir, "**", "*.dcm"), recursive=True)
    raw_file_paths += glob.glob(os.path.join(temp_dir, "**", "*.dicom"), recursive=True)

    # Fallback if files don't have extensions
    if not raw_file_paths:
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if not f.endswith(".zip") and not f.endswith(".json"):
                    raw_file_paths.append(os.path.join(root, f))

    if not raw_file_paths:
        return None, "No DICOM files found inside the ZIP."

    series_dict = defaultdict(list)
    # Ignore non-image modalities
    ignored_modalities = ['SEG', 'SR', 'PR', 'KO', 'RTSTRUCT']

    for f in raw_file_paths:
        try:
            # stop_before_pixels=True reads only headers, keeping this loop extremely fast
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            mod = getattr(ds, 'Modality', 'UNKNOWN')
            
            if mod not in ignored_modalities:
                series_uid = getattr(ds, 'SeriesInstanceUID', 'UNKNOWN_SERIES')
                series_dict[series_uid].append(f)
        except Exception:
            continue # Skip files that aren't valid DICOMs

    if not series_dict:
        return None, "No valid image series found (only found SEG/SR)."

    # Select the series with the most slices (isolates the main 3D volume)
    best_series_uid = max(series_dict, key=lambda uid: len(series_dict[uid]))
    best_file_paths = series_dict[best_series_uid]
    
    return best_file_paths, None


def check_modality(dicom_path):
    ds = pydicom.dcmread(dicom_path)
    return ds.Modality 

# call the medgemma  
def run_medgemma_xray(image_path: str, prompt: str):
    image = Image.open(image_path).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    output = model(
        text=messages,
        max_new_tokens=2000,
    )
    response = output[0]["generated_text"][-1]["content"]
    # print("original output:-", response)
    return parse_output(response)

def parse_output(response):
    response_json = re.search(json_regex, response, re.DOTALL)
    
    if response_json:
        json_string = response_json.group(1)
    else:
        print("No JSON found in the prompt.")

    parsed = json.loads(json_string)
    # print("parsed output is:-", parsed)
    finding = parsed.get("finding")
    return parsed


def dicom_to_image(dicom_path,output_path,format="png"):
    try:
        dicom=pydicom.dcmread(dicom_path)
        pixel_array = dicom.pixel_array

        pixel_array=(pixel_array-pixel_array.min())/(pixel_array.max()-pixel_array.min())*255
        pixel_array=pixel_array.astype(np.uint8)

        if dicom.PhotometricInterpretation=="MONOCHROME1":
            pixel_array=255-pixel_array

        if format=="jpg":
            cv2.imwrite(output_path,pixel_array)
        else:
            Image.fromarray(pixel_array).save(output_path)

    except Exception as e:
        raise RuntimeError(f"Failed to convert Dicom to {format}:{str(e)}")



def encode_slice(data):
    with io.BytesIO() as buffer:
        Image.fromarray(data).save(
            buffer,
            format="JPEG"
        )
        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

def select_slices(dicom_slices):
    if len(dicom_slices) > 20:
        selected = []
        middle_slice = len(dicom_slices)//2
        for idx in range(middle_slice-10, middle_slice+10):
            selected.append(dicom_slices[idx])
        dicom_slices = selected
    return dicom_slices

# MRI Utils

def normalize_mri_slices(dicom_slices):
    normalized_mri_slices = []
    
    for ds in dicom_slices:
        img = ds.pixel_array.astype(np.float32)
        if img.max() > img.min():
            img = (img - img.min()) / (img.max() - img.min())
        else:
            img = np.zeros_like(img)
    
        img = (img * 255).astype(np.uint8)
        normalized_mri_slices.append(img)

    return normalized_mri_slices

def preprocess_mri(dicom_files):
    # print(f"Found {len(dicom_files)} DICOM files")
    # print(dicom_files)
    slices = [pydicom.dcmread(f) for f in dicom_files]
    # Sort slices
    if hasattr(slices[0], "ImagePositionPatient"):
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    elif hasattr(slices[0], "InstanceNumber"):
        slices.sort(key=lambda s: int(s.InstanceNumber))

    # print("sorting is done")
    normalized_mri_slices = normalize_mri_slices(slices)
    # print("normalization is done")
    return normalized_mri_slices

def prepare_message_mr(dicom_files, prompt):
    content = []
    content.append({"type": "text", "text": prompt})

    normalized_mri_slices = preprocess_mri(dicom_files)
    normalized_mri_slices = select_slices(normalized_mri_slices)
    
    for slice_idx, slice_img in enumerate(normalized_mri_slices, start=1):
        content.append({"type": "image", "image": encode_slice(slice_img)})
        content.append({"type": "text", "text": f"SLICE {slice_idx}"})
    messages = [
        {
            "role": "user",
            "content": content
        }
    ]
    print("message is prepared")

    return messages
    
def run_medgemma_mr(message):
    output = model(
        text=message,
        max_new_tokens=2000
    )
    response = output[0]["generated_text"][-1]["content"]
    print("model ka output is :-", response)
    return response

 

# CT functions

def norm(ct_vol, min, max):
  """Window and normalize CT imaging Houndsfield values to values 0 - 255."""
  ct_vol = np.clip(ct_vol, min, max)  # Clip the imaging value range
  ct_vol = ct_vol.astype(np.float32)
  ct_vol -= min
  ct_vol /= (max - min) # Norm to values between 0 - 1.0
  ct_vol *= 255.0  # Norm to values been 0 - 255.0
  return ct_vol


def window(ct_vol):
  # Window CT slice imaging with three windows (wide, mediastinum(chest), brain)
  # Imaging will appear color when visualized, RGB channels contain different representations of the data.
  window_clips = [(-1024, 1024), (-135, 215), (0, 80)]
  return np.stack([norm(ct_vol, clip[0], clip[1]) for clip in window_clips], axis=-1)

def normalize_ct_slices(ct_volume_slices):
    normalized_ct_volume_slices = []
    for ct_slice in ct_volume_slices:
        windowed_slice = window(ct_slice)
        # Round slice voxels to nearest integer number.
        windowed_slice = np.round(windowed_slice, 0).astype(np.uint8)
        normalized_ct_volume_slices.append(windowed_slice)
    return normalized_ct_volume_slices

def preprocess_ct(dicom_files):
    slices = [pydicom.dcmread(f) for f in dicom_files]
    # Sort slices
    if hasattr(slices[0], "ImagePositionPatient"):
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    elif hasattr(slices[0], "InstanceNumber"):
        slices.sort(key=lambda s: int(s.InstanceNumber))

    ct_volume_slices  = []

    # row values ---> HU values
    for ds in slices:
        ct_volume_slices.append(pydicom.pixels.apply_rescale(ds.pixel_array, ds))

    normalized_ct_slices = normalize_ct_slices(ct_volume_slices)
    return normalized_ct_slices

def prepare_message_ct(dicom_files, prompt):
    content = []
    content.append({"type": "text", "text": prompt})

    normalized_ct_slices = preprocess_ct(dicom_files)
    normalized_ct_slices = select_slices(normalized_ct_slices)
    
    for slice_idx, slice_img in enumerate(normalized_ct_slices, start=1):
        content.append({"type": "image", "image": encode_slice(slice_img)})
        content.append({"type": "text", "text": f"SLICE {slice_idx}"})
    messages = [
        {
            "role": "user",
            "content": content
        }
    ]
    return messages

def run_medgemma_ct(message):
    output = model(
        text=message,
        max_new_tokens=2000
    )
    response = output[0]["generated_text"][-1]["content"]
    print("model ka output is :-", response)
    return response


# convert to json

 
def is_negated(sentence):
    sentence = sentence.lower()
 
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, sentence):
            return True
 
    return False
 
 
def detect_body_part(text):
 
    text = text.lower()

    if any(re.search(p, text) for p in brain_patterns):
        return "brain"
 
    if any(re.search(p, text) for p in chest_patterns):
        return "chest"
 
    return "unknown"
 
 
def extract_findings(report):
 
    findings_match = re.search(
        r"FINDINGS?:\s*(.*?)(?=\s*IMPRESSIONS?:|$)",
        report,
        flags=re.IGNORECASE | re.DOTALL
    )
 
    if findings_match:
        return findings_match.group(1).strip()
 
    return report.strip()
 
 
def extract_abnormalities(text, abnormalities_map):
 
    abnormalities = []
 
    sentences = re.split(r"[.;\n]+", text)
 
    for sentence in sentences:
 
        sentence = sentence.strip()
 
        if not sentence:
            continue
 
        negated = is_negated(sentence)
 
        for label, pattern in abnormalities_map.items():
 
            if re.search(pattern, sentence, re.IGNORECASE):
 
                if not negated:
                    abnormalities.append(label)
 
    return sorted(list(set(abnormalities)))
 
 
# Extend your existing report_to_json function to dynamically handle CR/XA/DX and fallbacks
def report_to_json(report, modality, known_body_part=None):
    findings = extract_findings(report)
    print("json findings:", findings)

    # Route maps safely
    if modality == 'MR':
        selected_abnormality_map = ABNORMALITY_MAP_MR
    elif modality == 'CT':
        selected_abnormality_map = ABNORMALITY_MAP_CT
    elif modality in ['CR', 'XA', 'DX']:
        selected_abnormality_map = ABNORMALITY_MAP_CR
    else:
        selected_abnormality_map = {}
        
    abnormalities = extract_abnormalities(findings, selected_abnormality_map)
    print("json abnormalities:", abnormalities)
    
    # Resolve the body part token matching cascade
    resolved_body_part = known_body_part or detect_body_part(report)
    if resolved_body_part == "unknown":
        resolved_body_part = extract_body_part_from_text_fallback(report)

    result = {
        "normal": len(abnormalities) == 0,
        "abnormality": abnormalities,
        "body_part": resolved_body_part,
        "finding": findings
    }
    return result



def extract_body_part_from_dicom(first_file_path):
    """
    Attempts to read metadata tags (0018,0015), (0008,0104), and (0008,1030).
    Runs the values through a regex matching layout to return a matched label.
    """
    try:
        ds = pydicom.dcmread(first_file_path, stop_before_pixels=True)
        
        # Pull text components from fallback attributes safely
        candidates = [
            str(getattr(ds, 'BodyPartExamined', '')),
            str(ds.get((0x0008, 0x0104), {}).get('value', '')), # Code Meaning
            str(getattr(ds, 'StudyDescription', ''))
        ]
        
        combined_text = " ".join(candidates).lower()
        if not combined_text.strip():
            return None
            
        # Match using the full anatomical coverage array map
        for label, patterns in BODY_PART_RE_MAP.items():
            for pattern in patterns:
                if re.search(pattern, combined_text):
                    return label
    except Exception:
        pass
    return None


def extract_body_part_from_text_fallback(report_text):
    """Fallback parser to uncover the targeted anatomy from raw prose text."""
    text_lower = report_text.lower()
    for label, patterns in BODY_PART_RE_MAP.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return label
    return "unknown"


