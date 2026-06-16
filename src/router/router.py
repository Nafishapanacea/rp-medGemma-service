import os
from fastapi import APIRouter, UploadFile, File
import tempfile
import glob
import json
import shutil
from zipfile import ZipFile
from fastapi.responses import JSONResponse

from utils.prompt import x_ray_prompt, mri_prompt, ct_prompt
from utils.utils import check_modality, dicom_to_image, run_medgemma_xray, prepare_message_mr, run_medgemma_mr, prepare_message_ct, run_medgemma_ct, report_to_json
from src.configuration.config import DICOM_TEMP_PATH

router = APIRouter()

os.makedirs(DICOM_TEMP_PATH, exist_ok=True)

@router.post("/predict")
async def predict(
    file : UploadFile = File(...),
):
    temp_dir = tempfile.mkdtemp(dir=DICOM_TEMP_PATH)

    try:
         # ── 1. Save uploaded ZIP ─────────────────────────────────────────
        temp_file = os.path.join(temp_dir, file.filename)
        with open(temp_file, 'wb') as out_file:
            out_file.write(await file.read())

        # ── 2. Extract ZIP ───────────────────────────────────────────────
        with ZipFile(temp_file, "r") as zip_ref:
            root_dir = zip_ref.namelist()[0].split("/")[0]
            zip_ref.extractall(temp_dir)

        root_dir_path = os.path.join(temp_dir, root_dir)

        # ── 3. Find first DICOM file ─────────────────────────────────────
        file_paths  = glob.glob(root_dir_path + "/**/*.dcm", recursive=True)
        file_paths += glob.glob(os.path.join(temp_dir, "**", "*.dicom"), recursive=True)

        # print("files paths:- ", file_paths)

        if not file_paths:
            return JSONResponse(
                status_code=400,
                content={"error": "No .dcm file found inside the ZIP."}
            )

        modality = check_modality(file_paths[0])
        print("Modality is :- ", modality)

        if (modality =='CR' or modality == 'XA'):
            dicom_path  = file_paths[0]
            output_path = os.path.splitext(dicom_path)[0] + ".png"
    
            # ── 4. DICOM → PNG ───────────────────────────────────────────────
            dicom_to_image(dicom_path, output_path, format="png")
    
            # ── 5. call model ───────────────────────────────────────────────
            response = run_medgemma_xray(output_path, x_ray_prompt)
            print(response)
    

        elif (modality =='MR'):
            # print(mri_prompt)
            message = prepare_message_mr(file_paths, mri_prompt)
            print(os.path.exists(file_paths[0]))
            # print(message)
            print("in main and msg is prepared")
            model_response = run_medgemma_mr(message)
            print("MR response",model_response)
            response = report_to_json(model_response, modality)
            # print("final response of MR", response)
            
        elif (modality =='CT'):
            message = prepare_message_ct(file_paths, ct_prompt)
            print(os.path.exists(file_paths[0]))
            # print(message)
            print("in main and msg is prepared")
            model_response = run_medgemma_ct(message)
            # print(model_response)
            response = report_to_json(model_response, modality)
            # print("final response of CT", response)
            
        else:
            response = {'finding':'Modality not supported'}

        # ── 6. Save finding to predictions.json ──────────────────────────
        temp_dir_return = tempfile.mkdtemp(dir=DICOM_TEMP_PATH)
        json_filepath = os.path.join(temp_dir_return, "predictions.json")

        with open(json_filepath, "w", encoding="utf-8") as json_file:
            json.dump(response, json_file, indent=4)

        return JSONResponse(content={
            "file_id": os.path.basename(temp_dir_return)
        })

    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content={"error": str(e)}
        )
        
    finally:
         # ── Clean up upload temp dir ──────────────────────────────────────
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