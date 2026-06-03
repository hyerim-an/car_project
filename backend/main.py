import os
import sys
import tempfile
import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# backend 폴더 위치를 기준으로 상위 폴더(car_project)를 sys.path에 추가하여 analysis 모듈을 import
base_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(base_dir)
sys.path.append(project_dir)

from analysis.predict_anomaly import predict_from_excel

app = FastAPI()

# ngrok 등 외부 유동 도메인 요청을 차단하지 않도록 CORS 허용 오리진을 전면 개방
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    클라이언트에서 업로드한 엑셀 파일을 임시 저장하고,
    기존 predict_anomaly 모듈의 분석 로직을 거쳐
    1초 내로(초경량 JSON 직렬화) 불량 판정 결과를 반환합니다.
    """
    if not file.filename.endswith('.xlsx') and not file.filename.endswith('.xls'):
        raise HTTPException(status_code=400, detail="엑셀 파일만 업로드 가능합니다.")
        
    try:
        # 1. 파일을 임시 위치에 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            
        # 2. 분석 모듈 호출 (기존 에셋 완벽 통합)
        results_df = predict_from_excel(tmp_path)
        
        # 3. 데이터 후처리 (JSON 직렬화 호환성을 위해 NaN을 None으로 치환)
        results_df = results_df.replace({np.nan: None})
        
        # 4. dict 리스트로 직렬화하여 반환 (가벼운 순수 JSON)
        data_records = results_df.to_dict(orient='records')
        
        return {
            "status": "success",
            "message": "데이터 분석이 완료되었습니다.",
            "data": data_records
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 임시 파일 삭제
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/api/data")
def get_data():
    return {
        "status": "success", 
        "message": "백엔드 서버 구동 중. /api/upload 엔드포인트를 통해 데이터를 전송하세요."
    }

# 프론트엔드 정적 파일 서빙 (항상 API 라우트보다 아래에 선언)
from fastapi.staticfiles import StaticFiles
frontend_dir = os.path.join(project_dir, "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
