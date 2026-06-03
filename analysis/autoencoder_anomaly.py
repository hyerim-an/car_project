import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import RobustScaler
from torch.utils.data import DataLoader, TensorDataset
import pickle


# ---------------------------------------------------------
# 1. 데이터 준비 (Data Preparation)
# ---------------------------------------------------------
print("데이터를 불러오는 중입니다...")
# 스크립트 실행 위치(analysis 폴더)를 고려하여 엑셀 파일 참조 경로 설정
file_path = '../Welding Data Set_01.xlsx' 
if not os.path.exists(file_path):
    file_path = 'Welding Data Set_01.xlsx'
if not os.path.exists(file_path):
    file_path = 'c:/Users/hlahn/car_project/data/Welding Data Set_01.xlsx'

# 'Raw data' 시트에서 4개의 연속형 변수만 추출
# 선택 컬럼: weld force(bar), weld current(kA), weld Voltage(v), weld time(ms)
columns_to_use = ['weld force(bar)', 'weld current(kA)', 'weld Voltage(v)', 'weld time(ms)']
df_raw = pd.read_excel(file_path, sheet_name='Raw data')
data = df_raw[columns_to_use].copy()

# ---------------------------------------------------------
# 2. 데이터 전처리 및 스플릿 (Preprocessing & Split)
# ---------------------------------------------------------
# 0 ~ 8469행은 train_data, 8470행 ~ 끝행은 test_data로 분리
train_df = data.iloc[0:8470]  # 인덱스 0 ~ 8469 (총 8470행)
test_df = data.iloc[8470:]    # 인덱스 8470 ~ 끝

# RobustScaler를 사용하여 스케일링 (Train 데이터 기준으로 Fit 후 변환)
# 이상치에 민감하지 않은 RobustScaler를 사용하여 안정적인 스케일링을 수행합니다.
scaler = RobustScaler()
train_scaled = scaler.fit_transform(train_df)
test_scaled = scaler.transform(test_df)

# PyTorch 학습을 위해 torch.Tensor 형태로 변환 (실수형 데이터)
train_tensor_full = torch.tensor(train_scaled, dtype=torch.float32)
test_tensor = torch.tensor(test_scaled, dtype=torch.float32)

# 배치 학습을 위한 DataLoader 설정
batch_size = 64
train_dataset_full = TensorDataset(train_tensor_full, train_tensor_full)
train_loader_full = DataLoader(train_dataset_full, batch_size=batch_size, shuffle=True)

# ---------------------------------------------------------
# 3. 모델 구축 (Model Construction)
# ---------------------------------------------------------
class AutoEncoder(nn.Module):
    def __init__(self, input_dim):
        super(AutoEncoder, self).__init__()
        # 인코더 (Encoder): 2개 층, 활성화 함수로 RReLU 사용
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8),
            nn.RReLU(),
            nn.Linear(8, 4),
            nn.RReLU()
        )
        # 디코더 (Decoder): 2개 층, 활성화 함수로 RReLU 사용
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

input_dim = train_tensor_full.shape[1]

# ---------------------------------------------------------
# 4. Phase 1: 1차 학습 및 데이터 필터링 (Phase 1 Training & Filtering)
# ---------------------------------------------------------
print("\n[Phase 1] 1차 AutoEncoder 학습을 시작합니다 (30 Epochs)...")
model_phase1 = AutoEncoder(input_dim)
criterion = nn.MSELoss()
optimizer_phase1 = optim.Adam(model_phase1.parameters(), lr=0.01)

epochs_phase1 = 30
for epoch in range(epochs_phase1):
    model_phase1.train()
    epoch_loss = 0.0
    for batch_x, batch_y in train_loader_full:
        optimizer_phase1.zero_grad()
        outputs = model_phase1(batch_x)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer_phase1.step()
        epoch_loss += loss.item() * batch_x.size(0)
    
    avg_loss = epoch_loss / len(train_loader_full.dataset)
    if (epoch + 1) % 10 == 0 or epoch == 0:
        print(f"Phase 1 - Epoch [{epoch+1}/{epochs_phase1}], Loss: {avg_loss:.6f}")

print("\n[Phase 1] 오차가 큰 상위 5% 샘플을 필터링합니다...")
model_phase1.eval()
with torch.no_grad():
    # Train 전체 데이터에 대해 복원 오차(Loss) 계산
    train_outputs_phase1 = model_phase1(train_tensor_full)
    # 각 샘플별 MSE(평균제곱오차) 계산
    individual_losses_phase1 = torch.mean((train_tensor_full - train_outputs_phase1) ** 2, dim=1).numpy()

# 상위 5%에 해당하는 손실값의 기준선(Threshold) 계산
percentile_95 = np.percentile(individual_losses_phase1, 95)
print(f"상위 5% 절사 기준 오차값: {percentile_95:.6f}")

# 상위 5%를 제외한(오차가 95백분위수 이하인) 깨끗한 데이터만 추출 (Clean Train 데이터)
clean_indices = individual_losses_phase1 <= percentile_95
clean_train_tensor = train_tensor_full[clean_indices]
print(f"필터링 전 Train 데이터 개수: {len(train_tensor_full)}")
print(f"필터링 후 Clean Train 데이터 개수: {len(clean_train_tensor)}")

# ---------------------------------------------------------
# 5. Phase 2: 깨끗한 데이터로 2차 재학습 (Phase 2 Retraining)
# ---------------------------------------------------------
print("\n[Phase 2] 새로운 모델로 2차 재학습을 시작합니다 (50 Epochs)...")
# 완전히 초기화된 새로운 모델 객체 생성
model_phase2 = AutoEncoder(input_dim)
optimizer_phase2 = optim.Adam(model_phase2.parameters(), lr=0.01)

# Clean Train 데이터용 DataLoader 생성
clean_train_dataset = TensorDataset(clean_train_tensor, clean_train_tensor)
clean_train_loader = DataLoader(clean_train_dataset, batch_size=batch_size, shuffle=True)

epochs_phase2 = 50
for epoch in range(epochs_phase2):
    model_phase2.train()
    epoch_loss = 0.0
    for batch_x, batch_y in clean_train_loader:
        optimizer_phase2.zero_grad()
        outputs = model_phase2(batch_x)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer_phase2.step()
        epoch_loss += loss.item() * batch_x.size(0)
    
    avg_loss = epoch_loss / len(clean_train_loader.dataset)
    if (epoch + 1) % 10 == 0 or epoch == 0:
        print(f"Phase 2 - Epoch [{epoch+1}/{epochs_phase2}], Loss: {avg_loss:.6f}")

# ---------------------------------------------------------
# 6. 임계값(Threshold) 조정 및 Test 검증 (Threshold & Test)
# ---------------------------------------------------------
print("\n[Threshold] 최종 모델의 임계값을 계산합니다...")
model_phase2.eval()
with torch.no_grad():
    # Clean Train 데이터에 대한 개별 복원 오차 계산
    clean_train_outputs = model_phase2(clean_train_tensor)
    clean_individual_losses = torch.mean((clean_train_tensor - clean_train_outputs) ** 2, dim=1).numpy()

# 새로운 임계값: 평균 + 표준편차 * 3 (보수적인 기준 완화)
mean_loss = np.mean(clean_individual_losses)
std_loss = np.std(clean_individual_losses)
threshold = mean_loss + (std_loss * 3)
print(f"Clean 데이터 평균 오차: {mean_loss:.6f}, 표준편차: {std_loss:.6f}")
print(f"설정된 최종 임계값(Threshold): {threshold:.6f}")

# Test 데이터 예측 및 불량 판별
with torch.no_grad():
    test_outputs = model_phase2(test_tensor)
    test_individual_losses = torch.mean((test_tensor - test_outputs) ** 2, dim=1).numpy()

# 임계값을 초과하는 샘플을 이상치(불량)로 판별
outliers = test_individual_losses > threshold
predicted_outlier_count = int(np.sum(outliers))
print(f"\nTest 데이터 내 예측된 불량(이상치) 개수: {predicted_outlier_count} 개")

# ---------------------------------------------------------
# 6.5 규칙 기반 불량 카테고리 분류 (Rule-based Defect Categorization)
# ---------------------------------------------------------
print("\n[Categorization] 예측된 불량에 대해 규칙 기반 카테고리 분류를 수행합니다...")
# 카테고리: 1=파임불량, 2=용접부족, 3=크랙발생
def categorize_defect(row):
    force = row['weld force(bar)']
    current = row['weld current(kA)']
    voltage = row['weld Voltage(v)']
    time = row['weld time(ms)']
    
    # 정상 평균 (가이드북 기준)
    # 가압력: 2.78 bar, 전류: 14.71 kA, 통전시간: 71.7 ms
    
    # 1. 파임불량: 가압력이 크게 낮거나, 전류/통전시간이 유독 높은 데이터
    if force < 2.5 or current > 14.9 or time > 73.0:
        return 1, '파임불량'
    # 2. 용접부족: 가압력이 유독 높거나, 전류/통전시간이 현저히 낮은 데이터
    elif force > 3.5 or current < 14.5 or time < 70.0:
        return 2, '용접부족'
    # 3. 크랙발생: 복합적 불안정 패턴 (그 외)
    else:
        return 3, '크랙발생'

test_df_outliers = test_df[outliers].copy()
if len(test_df_outliers) > 0:
    categories = test_df_outliers.apply(categorize_defect, axis=1)
    test_df_outliers['defect_type_code'] = categories.apply(lambda x: x[0])
    test_df_outliers['defect_type_name'] = categories.apply(lambda x: x[1])
    
    category_counts = test_df_outliers['defect_type_name'].value_counts()
    print("규칙 기반 불량 카테고리 분류 결과:")
    print(category_counts)
else:
    print("예측된 불량이 없어 카테고리 분류를 생략합니다.")

# ---------------------------------------------------------
# 7. 결과 검증 (Validation)
# ---------------------------------------------------------
print("\n결과 검증을 시작합니다...")
# 'result' 시트에서 일별 실제 불량 개수의 총합 구하기
df_result = pd.read_excel(file_path, sheet_name='result')

# 결측치 등을 방지하고 defect 열(불량 개수)을 안전하게 합산
if 'defect' in df_result.columns:
    actual_defect_count = int(df_result['defect'].sum())
else:
    numeric_cols = df_result.select_dtypes(include=[np.number]).columns
    actual_defect_count = int(df_result[numeric_cols[-1]].sum())

print(f"실제 데이터('result' 시트) 기반 불량 개수 총합: {actual_defect_count} 개")

# 예측 결과와 실제 불량 수 비교 및 출력
error_diff = abs(predicted_outlier_count - actual_defect_count)
print(f"예측과 실제의 차이(오차): {error_diff} 개")

# ---------------------------------------------------------
# 8. Markdown 리포트 자동 생성 (Auto-generate Analysis Report)
# ---------------------------------------------------------
report_path = os.path.join(os.path.dirname(__file__), 'analysis_report.md')

category_summary = ""
if len(test_df_outliers) > 0:
    category_summary = "### 불량 유형 분류 결과 (규칙 기반)\n"
    for cat_name, count in category_counts.items():
        category_summary += f"- **{cat_name}**: {count}개\n"
else:
    category_summary = "### 불량 유형 분류 결과 (규칙 기반)\n- 예측된 불량 없음\n"

report_content = f"""# Two-Stage Iterative Filtering AutoEncoder 이상 탐지 모델 분석 리포트

## 1. 모델 아키텍처 및 전처리 개선 사항
- **스케일링 기법**: 기존 MinMaxScaler에서 `RobustScaler`로 변경하여, 아웃라이어(이상치)의 영향력을 최소화하고 정상 데이터의 스케일을 더 안정적으로 맞춤.
- **학습 전략 (Two-Stage 반복적 정제)**:
  1. **Phase 1 (초기 학습 및 필터링)**: 전체 Train 데이터로 30 에포크 학습 후, 재구성 오차(Loss)가 가장 큰 **상위 5% 샘플을 제거**하여 깨끗한 정상 데이터를 추출함.
  2. **Phase 2 (재학습)**: 필터링된 'Clean Train 데이터'만 사용하여 완전히 초기화된 새 모델을 50 에포크 동안 재학습. 이를 통해 오염된 데이터가 모델에 미치는 영향을 차단하여 과적합을 방지함.
- **임계값 설정 공식**: `mean(Clean_Loss) + std(Clean_Loss) * 3` 
  - (기존 *8에서 현실적으로 완화하여, 보다 정밀한 이상 탐지를 수행함)
- **산출된 임계값**: `{threshold:.6f}`

## 2. Test 예측 결과 및 검증
- **예측된 불량 수 (AutoEncoder)**: `{predicted_outlier_count}` 개
- **실제 불량 수 ('result' 시트 기준)**: `{actual_defect_count}` 개
- **예측 오차**: `{error_diff}` 개

{category_summary}

## 3. 결론 및 인사이트
1. **과적합 방지 효과**: Train 데이터 내에 포함되어 있을 수 있는 잠재적 이상치(노이즈)를 1차로 걸러낸 뒤 순수한 정상 데이터만으로 재학습(Phase 2)함으로써, AutoEncoder 본연의 '정상 데이터 재구성' 능력을 극대화했습니다.
2. **RobustScaler의 안정성**: 1차 필터링 단계에서 통계적으로 의미 있는 상위 5%를 찾을 때 스케일링으로 인한 편향을 방지하는 역할을 했습니다.
3. **Threshold 현실화**: 과거 에포크의 훈련 손실 평균 대신, **최종 재학습된 모델의 개별 샘플 재구성 오차 분포**를 기준으로 임계값을 재산출(Mean + 3*Std)하여 통계적으로 더 타당한 검출 기준을 확립했습니다.
4. **규칙 기반 카테고리화 적용**: 예측된 이상치에 대해 도메인 지식(용접 가압력, 전류, 전압 등)을 반영한 규칙 기반 분류를 도입하여 '파임불량', '용접부족', '크랙발생' 등 구체적인 불량 유형을 제공할 수 있도록 고도화했습니다.
"""

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report_content)
print(f"분석 리포트가 '{report_path}'에 성공적으로 저장되었습니다.")

# ---------------------------------------------------------
# 9. 모델 및 메타데이터 저장 (Save Model & Metadata)
# ---------------------------------------------------------
print("\n[Save] 학습된 모델과 메타데이터를 저장합니다...")
model_path = os.path.join(os.path.dirname(__file__), 'master_model.pth')
meta_path = os.path.join(os.path.dirname(__file__), 'model_meta.pkl')

# 모델 가중치 저장
torch.save(model_phase2.state_dict(), model_path)

# 메타데이터 및 스케일러 저장
meta_data = {
    'input_dim': input_dim,
    'threshold': threshold,
    'scaler': scaler,
    'columns_to_use': columns_to_use
}
with open(meta_path, 'wb') as f:
    pickle.dump(meta_data, f)

print(f"모델 가중치가 '{model_path}'에 저장되었습니다.")
print(f"메타데이터가 '{meta_path}'에 저장되었습니다.")

