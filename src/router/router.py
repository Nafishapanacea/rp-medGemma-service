import os
from fastapi import APIRouter, UploadFile, File
import tempfile
import glob
import json
import shutil
from zipfile import ZipFile
from fastapi.responses import JSONResponse

from src.configuration.prompt import x_ray_prompt
from utils.utils import dicom_to_image, run_medgemma

router = APIRouter()

DICOM_TEMP_PATH= '/home/nafisha/medGemma_service/tmp/dicom_uploads'
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

        if not file_paths:
            return JSONResponse(
                status_code=400,
                content={"error": "No .dcm file found inside the ZIP."}
            )

        dicom_path  = file_paths[0]
        print("DICOM FILE:", dicom_path)
        output_path = os.path.splitext(dicom_path)[0] + ".png"

        # ── 4. DICOM → PNG ───────────────────────────────────────────────
        dicom_to_image(dicom_path, output_path, format="png")

        # ── 5. call model ───────────────────────────────────────────────
        response = run_medgemma(output_path, x_ray_prompt)
        print(response)

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