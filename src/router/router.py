import os
from fastapi import APIRouter, UploadFile, File,HTTPException
import tempfile
import threading
import glob
import json
import shutil
from zipfile import ZipFile
import requests
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from utils.prompt import x_ray_prompt, mri_prompt, ct_prompt
from utils.utils import check_modality, dicom_to_image, run_medgemma_xray, prepare_message_mr, run_medgemma_mr, prepare_message_ct, run_medgemma_ct, report_to_json,download_study_zip, get_best_image_series
from src.configuration.config import DICOM_TEMP_PATH

router = APIRouter()

os.makedirs(DICOM_TEMP_PATH, exist_ok=True)

gpu_lock = threading.Lock()
class InferencePayload(BaseModel):
    studyId: str
    pacsUrl: Optional[str] = None
    authCred: Optional[str] = None

@router.post("/predict")
def predict(
    payload: InferencePayload
):
    temp_dir = tempfile.mkdtemp(dir=DICOM_TEMP_PATH)

    try:
        pacs_url = payload.pacsUrl or os.getenv("PACS_URL", "https://dev.radpretation.ai/pacs")
        auth_cred = payload.authCred or os.getenv("AUTH_CRED")

        if not pacs_url:
            return JSONResponse(status_code=400, content={"error": "pacsUrl is required"})

        # ── 1. Download ZIP ───────────────────────────────────────────────
        temp_file = os.path.join(temp_dir, f"{payload.studyId}.zip")
        print(f"Downloading study {payload.studyId} from {pacs_url}...")
        
        download_study_zip(pacs_url, payload.studyId, auth_cred, temp_file)
        print(f"Download complete. Extracting...")

        # ── 2. Extract ZIP ────────────────────────────────────────────────
        with ZipFile(temp_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # ── 3. Find and Filter Best Series (Ignore SEG) ───────────────────
        file_paths, error_msg = get_best_image_series(temp_dir)
        
        if error_msg:
            return JSONResponse(status_code=400, content={"error": error_msg})

        print(f"Selected Best Series with {len(file_paths)} slices for AI processing.")
        

        modality = check_modality(file_paths[0])
        print("Modality is :- ", modality)

        with gpu_lock:
            print(f"Acquired GPU lock. Running AI for {payload.studyId}...")
            
            if (modality =='CR' or modality == 'XA'):
                dicom_path  = file_paths[0]
                output_path = os.path.splitext(dicom_path)[0] + ".png"
                dicom_to_image(dicom_path, output_path, format="png")
                response = run_medgemma_xray(output_path, x_ray_prompt)
                
            elif (modality =='MR'):
                message = prepare_message_mr(file_paths, mri_prompt)
                model_response = run_medgemma_mr(message)
                response = report_to_json(model_response, modality)
                
            elif (modality =='CT'):
                message = prepare_message_ct(file_paths, ct_prompt)
                model_response = run_medgemma_ct(message)
                response = report_to_json(model_response, modality)
                
            else:
                response = {'finding':'Modality not supported'}
            
            print(f"AI finished. Releasing GPU lock for {payload.studyId}.")

        # ── Save and Return ───────────────────────────────────────────────
        temp_dir_return = tempfile.mkdtemp(dir=DICOM_TEMP_PATH)
        json_filepath = os.path.join(temp_dir_return, "predictions.json")

        with open(json_filepath, "w", encoding="utf-8") as json_file:
            json.dump(response, json_file, indent=4)

        return JSONResponse(content={
            "file_id": os.path.basename(temp_dir_return)
        })
    
    except requests.exceptions.HTTPError as e:
        # If Orthanc returns a 404, pass that 404 directly to the frontend
        error_code = e.response.status_code
        return JSONResponse(
            status_code=error_code,
            content={"error": f"PACS Server returned {error_code}: Study not found or unauthorized."}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.get("/json/{file_id}")
async def get_json_object(file_id: str):
    path     = os.path.join(DICOM_TEMP_PATH, file_id, "predictions.json")
    dir_path = os.path.join(DICOM_TEMP_PATH, file_id)

    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return data
        else:
            raise HTTPException(status_code=404, detail="File not found")

    except Exception as e:
        raise e

    finally:
        # Clean up temp dir after reading
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(dir_path) and not os.listdir(dir_path):
            os.rmdir(dir_path)