import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import pickle

# ---------------------------------------------------------
# 1. 모델 아키텍처 정의 (Model Architecture)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 2. 규칙 기반 불량 카테고리 분류 (Rule-based Defect Categorization)
# ---------------------------------------------------------
def categorize_defect(row):
    force = row['weld force(bar)']
    current = row['weld current(kA)']
    voltage = row['weld Voltage(v)']
    time = row['weld time(ms)']
    
    if force < 2.5 or current > 14.9 or time > 73.0:
        return 1, '파임불량'
    elif force > 3.5 or current < 14.5 or time < 70.0:
        return 2, '용접부족'
    else:
        return 3, '크랙발생'

# ---------------------------------------------------------
# 3. 새로운 파일 예측 로직 (Prediction Logic)
# ---------------------------------------------------------
def predict_from_excel(file_path):
    print(f"[{file_path}] 파일 예측을 시작합니다...")
    
    # 모델 및 메타데이터 경로 설정
    base_dir = os.path.dirname(__file__)
    model_path = os.path.join(base_dir, 'master_model.pth')
    meta_path = os.path.join(base_dir, 'model_meta.pkl')
    
    if not os.path.exists(meta_path) or not os.path.exists(model_path):
        raise ValueError("에러: 모델 파일(master_model.pth) 또는 메타데이터 파일(model_meta.pkl)이 존재하지 않습니다. 먼저 학습을 진행해주세요.")
        
    # 1. 메타데이터 및 스케일러 불러오기
    with open(meta_path, 'rb') as f:
        meta_data = pickle.load(f)
        
    input_dim = meta_data['input_dim']
    threshold = meta_data['threshold']
    scaler = meta_data['scaler']
    columns_to_use = meta_data['columns_to_use']
    
    # 2. 모델 불러오기
    model = AutoEncoder(input_dim)
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    # 3. 새로운 데이터 불러오기 ('Raw data' 시트 없으면 기본 시트)
    try:
        df_raw = pd.read_excel(file_path, sheet_name='Raw data')
    except Exception:
        try:
            df_raw = pd.read_excel(file_path)
        except Exception as e:
            raise ValueError(f"데이터를 불러오는 데 실패했습니다: {e}")
        
    if not all(col in df_raw.columns for col in columns_to_use):
        missing = [col for col in columns_to_use if col not in df_raw.columns]
        raise ValueError(f"분석에 필요한 열이 파일에 존재하지 않습니다. 누락된 열: {missing}")
        
    data = df_raw[columns_to_use].copy()
    
    # 4. 데이터 전처리 (저장된 scaler 사용)
    scaled_data = scaler.transform(data)
    tensor_data = torch.tensor(scaled_data, dtype=torch.float32)
    
    # 5. 예측 및 검증
    with torch.no_grad():
        outputs = model(tensor_data)
        individual_losses = torch.mean((tensor_data - outputs) ** 2, dim=1).numpy()
        
    outliers = individual_losses > threshold
    predicted_outlier_count = int(np.sum(outliers))
    print(f"총 {len(data)}개의 데이터 중 예측된 불량(이상치) 개수: {predicted_outlier_count} 개")
    
    # 6. 불량 카테고리 분류 및 결과 정리
    results_df = df_raw.copy()
    results_df['is_anomaly'] = outliers
    results_df['anomaly_loss'] = individual_losses
    
    outlier_indices = results_df[results_df['is_anomaly']].index
    if len(outlier_indices) > 0:
        categories = results_df.loc[outlier_indices].apply(categorize_defect, axis=1)
        results_df.loc[outlier_indices, 'defect_type_code'] = categories.apply(lambda x: x[0])
        results_df.loc[outlier_indices, 'defect_type_name'] = categories.apply(lambda x: x[1])
    else:
        results_df['defect_type_code'] = np.nan
        results_df['defect_type_name'] = np.nan
        
    print("예측이 완료되었습니다.")
    return results_df

if __name__ == "__main__":
    # 테스트용 파일 경로 (실제 대시보드에서는 이 부분을 업로드된 파일 경로로 치환하여 사용)
    test_file_path = '../Welding Data Set_01.xlsx' 
    if not os.path.exists(test_file_path):
        test_file_path = 'Welding Data Set_01.xlsx'
    if not os.path.exists(test_file_path):
        test_file_path = 'c:/Users/hlahn/car_project/data/Welding Data Set_01.xlsx'
        
    if os.path.exists(test_file_path):
        results = predict_from_excel(test_file_path)
        
        if results is not None:
            # 예측 결과를 CSV로 저장하는 예시
            output_path = os.path.join(os.path.dirname(__file__), 'prediction_results.csv')
            results.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"예측 결과가 '{output_path}'에 저장되었습니다.")
    else:
        print(f"테스트 파일을 찾을 수 없습니다: {test_file_path}")
