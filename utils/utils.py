from model.model import model
from PIL import Image
import cv2
import pydicom
import numpy as np
import re
import json

json_regex = r"```json\s*(\{.*?\})\s*```"

# call the medgemma  
def run_medgemma(image_path: str, prompt: str):
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