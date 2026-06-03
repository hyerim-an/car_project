import os
import pickle
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# --- 모델 경로 및 로드 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "master_model.pth")
META_PATH = os.path.join(BASE_DIR, "models", "model_meta.pkl")

# 모델 메모리 적재 예시 (PyTorch 등을 사용하는 경우 주석 해제하여 사용)
# @app.on_event("startup")
# def load_ml_models():
#     global model, meta_data
#     if os.path.exists(META_PATH):
#         with open(META_PATH, 'rb') as f:
#             meta_data = pickle.load(f)
#     # if os.path.exists(MODEL_PATH):
#     #     model = torch.load(MODEL_PATH)
#     print(f"Model Path: {MODEL_PATH}")

# Vercel 등 프론트엔드 도메인 환경 변수 (기본값은 로컬 테스트용)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# CORS 설정: 프론트엔드 도메인만 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
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
    # 실제로는 여기서 모델 예측 등을 수행합니다.
    return {"result": f"Processed successfully: {req.data}"}

if __name__ == "__main__":
    import uvicorn
    # Render가 할당하는 PORT 환경 변수를 최우선으로 가져오도록 설정
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
