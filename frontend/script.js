document.addEventListener('DOMContentLoaded', () => {
    const fetchBtn = document.getElementById('fetchDataBtn');
    const resultBox = document.getElementById('resultBox');

    // 환경에 따라 동적으로 백엔드 주소를 설정할 수 있도록 변수화
    // 초기 로컬 환경 기준 백엔드 주소 (CORS가 허용됨)
    const API_BASE_URL = '';

    fetchBtn.addEventListener('click', async () => {
        fetchBtn.disabled = true;
        fetchBtn.innerText = '요청 중...';
        resultBox.innerText = '백엔드 서버와 통신하는 중...';
        resultBox.style.backgroundColor = '#ecf0f1';
        resultBox.style.color = '#34495e';

        try {
            const response = await fetch(`${API_BASE_URL}/api/data`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 백엔드가 뱉은 정제된 JSON 데이터
            const data = await response.json();
            
            // 프론트엔드가 JSON을 파싱하여 동적으로 DOM을 업데이트
            resultBox.innerHTML = `
                <strong style="color: #27ae60;">${data.message}</strong>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #7f8c8d;">
                    응답 데이터: [${data.data.items.join(', ')}]
                </div>
            `;
            resultBox.style.backgroundColor = '#e8f8f5';
        } catch (error) {
            console.error('Error fetching data:', error);
            resultBox.innerHTML = `
                <strong style="color: #e74c3c;">연결 실패</strong>
                <div style="margin-top: 5px; font-size: 0.85rem;">서버가 실행 중인지 확인하세요.</div>
            `;
            resultBox.style.backgroundColor = '#fdedec';
        } finally {
            fetchBtn.disabled = false;
            fetchBtn.innerText = '데이터 다시 불러오기';
        }
    });
});
