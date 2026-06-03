/**
 * 백엔드 서버 URL 설정
 * 로컬 테스트: "http://localhost:8000"
 * 운영 배포 후: "https://my-backend-app.onrender.com" 등 Render 주소로 교체
 */
const BACKEND_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
    const sendBtn = document.getElementById("sendBtn");
    const inputText = document.getElementById("inputText");
    const resultBox = document.getElementById("resultBox");

    sendBtn.addEventListener("click", async () => {
        const data = inputText.value.trim();
        if (!data) {
            alert("데이터를 입력해주세요.");
            inputText.focus();
            return;
        }

        resultBox.textContent = "전송 중...";
        sendBtn.disabled = true;

        try {
            const response = await fetch(`${BACKEND_URL}/api/predict`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ data: data })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const json = await response.json();
            resultBox.textContent = `결과: ${json.result}`;
        } catch (error) {
            console.error("Error:", error);
            resultBox.textContent = `오류 발생: ${error.message}`;
        } finally {
            sendBtn.disabled = false;
        }
    });
    
    // 엔터키 입력 지원
    inputText.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            sendBtn.click();
        }
    });
});
