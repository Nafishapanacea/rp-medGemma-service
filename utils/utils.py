from model.model import model
from PIL import Image
import cv2
import base64
import pydicom
import numpy as np
import re
import io
import json

json_regex = r"```json\s*(\{.*?\})\s*```"

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






















import matplotlib.pyplot as plt
import math
import os


def save_debug_mri_slices(slices,
                          save_path="/home/nafisha/medGemma_service/debug_mri_slices.png"):
    print("in plotting function")
    n = len(slices)

    cols = 5
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(
        rows,
        cols,
        figsize=(15, rows * 3)
    )

    axes = np.array(axes).reshape(-1)

    for i, ax in enumerate(axes):

        if i < n:
            ax.imshow(slices[i], cmap="gray")
            ax.set_title(f"Slice {i}")
            ax.axis("off")
        else:
            ax.axis("off")

    plt.tight_layout()

    plt.savefig(save_path, bbox_inches="tight")
    plt.close()

    print(f"Debug MRI saved to: {save_path}")