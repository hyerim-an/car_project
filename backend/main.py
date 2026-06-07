import os
import io
import pickle
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tbsevapmhyzfhaqzmfza.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "Car_project")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# --- 1. 모델 아키텍처 및 룰셋 정의 ---
class AutoEncoder(nn.Module):
    def __init__(self, input_dim):
        super(AutoEncoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8),
            nn.RReLU(),
            nn.Linear(8, 4),
            nn.RReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(4, 8),
            nn.RReLU(),
            nn.Linear(8, input_dim),
            nn.RReLU() 
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

def categorize_defect(row):
    force = row.get('weld force(bar)', 0)
    current = row.get('weld current(kA)', 0)
    time = row.get('weld time(ms)', 0)
    
    if force < 2.5 or current > 14.9 or time > 73.0:
        return 1, '파임불량'
    elif force > 3.5 or current < 14.5 or time < 70.0:
        return 2, '용접부족'
    else:
        return 3, '크랙발생'

# --- 2. 모델 경로 및 전역 변수 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "master_model.pth")
META_PATH = os.path.join(BASE_DIR, "models", "model_meta.pkl")

model = None
meta_data = None
scaler = None
columns_to_use = []
threshold = 0.0

@app.on_event("startup")
def load_ml_models():
    global model, meta_data, scaler, columns_to_use, threshold
    
    if not os.path.exists(META_PATH) or not os.path.exists(MODEL_PATH):
        print(f"Warning: Model files missing. Expected at {MODEL_PATH} and {META_PATH}")
        return
        
    try:
        with open(META_PATH, 'rb') as f:
            meta_data = pickle.load(f)
            
        input_dim = meta_data['input_dim']
        threshold = meta_data['threshold']
        scaler = meta_data['scaler']
        columns_to_use = meta_data['columns_to_use']
        
        model = AutoEncoder(input_dim)
        # map_location='cpu' ensures it works on Render without GPU
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
        model.eval()
        print("ML Models successfully loaded into memory.")
    except Exception as e:
        print(f"Failed to load ML models: {e}")

# --- 3. FastAPI 설정 및 라우터 ---
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 배포 환경이므로 통신을 위해 전체 허용 또는 FRONTEND_URL 제한 가능
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PredictRequest(BaseModel):
    data: str

@app.get("/")
def read_root():
    return {"message": "Hello from Render Backend API"}

@app.post("/api/predict")
def predict(req: PredictRequest):
    return {"result": f"Processed successfully: {req.data}"}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """엑셀 파일을 받아 ML 모델을 통과시키고 결과를 JSON으로 반환하는 엔드포인트"""
    if model is None:
        raise HTTPException(status_code=500, detail="ML Model is not loaded on the server.")
        
    try:
        contents = await file.read()
        try:
            df_raw = pd.read_excel(io.BytesIO(contents), sheet_name='Raw data')
        except Exception:
            df_raw = pd.read_excel(io.BytesIO(contents))
            
        if not all(col in df_raw.columns for col in columns_to_use):
            missing = [col for col in columns_to_use if col not in df_raw.columns]
            raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")
            
        data = df_raw[columns_to_use].copy()
        
        # 스케일링 및 텐서 변환
        scaled_data = scaler.transform(data)
        tensor_data = torch.tensor(scaled_data, dtype=torch.float32)
        
        # 모델 추론
        with torch.no_grad():
            outputs = model(tensor_data)
            individual_losses = torch.mean((tensor_data - outputs) ** 2, dim=1).numpy()
            
        outliers = individual_losses > threshold
        
        # 결과 정리 및 JSON 호환 처리
        results_df = df_raw.copy()
        results_df['is_anomaly'] = outliers.astype(bool)
        results_df['anomaly_loss'] = individual_losses.astype(float)
        
        outlier_indices = results_df[results_df['is_anomaly']].index
        if len(outlier_indices) > 0:
            categories = results_df.loc[outlier_indices].apply(categorize_defect, axis=1)
            results_df.loc[outlier_indices, 'defect_type_code'] = categories.apply(lambda x: int(x[0]))
            results_df.loc[outlier_indices, 'defect_type_name'] = categories.apply(lambda x: str(x[1]))
        else:
            results_df['defect_type_code'] = None
            results_df['defect_type_name'] = None
            
        # NaN 등 JSON으로 바로 반환 불가능한 값들 None으로 치환
        results_df = results_df.replace({np.nan: None})
        
        data_to_return = results_df.to_dict(orient="records")
        
        total_records = len(results_df)
        anomaly_count = int(outliers.sum())
        normal_rate = ((total_records - anomaly_count) / total_records * 100) if total_records > 0 else 0.0
        
        # --- Supabase 저장 로직 시작 ---
        try:
            crack_count = int((results_df['defect_type_name'] == '크랙발생').sum())
            pitting_count = int((results_df['defect_type_name'] == '파임불량').sum())
            lack_count = int((results_df['defect_type_name'] == '용접부족').sum())
            
            # 1. 업로드 요약 정보 저장
            summary_data = {
                "project_name": PROJECT_NAME,
                "filename": file.filename,
                "total_records": total_records,
                "anomaly_count": anomaly_count,
                "normal_rate": float(normal_rate),
                "crack_count": crack_count,
                "pitting_count": pitting_count,
                "lack_count": lack_count,
                "threshold": float(threshold)
            }
            summary_response = supabase.table("upload_summaries").insert(summary_data).execute()
            
            if summary_response.data:
                upload_id = summary_response.data[0]['id']
                
                # 2. 이상치 로그 상세 정보 저장
                if anomaly_count > 0:
                    logs_to_insert = []
                    for idx, row in results_df[results_df['is_anomaly']].iterrows():
                        logs_to_insert.append({
                            "upload_id": upload_id,
                            "project_name": PROJECT_NAME,
                            "row_number": int(idx) + 1,  # 프론트엔드 표시 기준 (1-based index)
                            "anomaly_loss": float(row['anomaly_loss']),
                            "defect_type": str(row['defect_type_name']),
                            "welding_current": float(row['weld current(kA)']) if 'weld current(kA)' in row else None
                        })
                    
                    if logs_to_insert:
                        supabase.table("anomaly_logs").insert(logs_to_insert).execute()
                        
        except Exception as db_err:
            print(f"Supabase 저장 실패: {db_err}")
        # --- Supabase 저장 로직 끝 ---
        
        # --- n8n Webhook 연동 시작 ---
        if N8N_WEBHOOK_URL:
            try:
                webhook_payload = {
                    "filename": file.filename,
                    "normal_rate": float(normal_rate)
                }
                requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=5)
            except Exception as hook_err:
                print(f"n8n Webhook 전송 실패: {hook_err}")
        # --- n8n Webhook 연동 끝 ---
        
        # orient="records" 형태로 반환하여 프론트엔드의 dataRows 배열 기대 포맷과 맞춤
        return {"data": data_to_return}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
