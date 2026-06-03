---
name: agent
description: 사용자가 @agent 를 호출하면 /.agent/agents 폴더에 새로운 서브에이전트(subagent)를 생성해주는 명령어 스킬입니다.
---

# agent Command

사용자가 프롬프트에서 `@[agent]` (또는 `@agent` 형태의 참조)를 사용하면, 당신은 사용자의 요구사항을 바탕으로 새로운 서브에이전트를 정의하고 관련 파일들을 생성해야 합니다. 

### 작업 프로세스:

1. **요구사항 분석**:
   - 사용자가 원하는 서브에이전트의 역할, 목적, 필요 기능 등을 파악합니다.
   - 에이전트 이름이 명시되지 않았다면 역할에 맞는 적절한 영어 이름(소문자와 언더스코어 조합, 예: `frontend_dev`, `researcher`)을 결정합니다.

2. **파일 생성 위치 파악**:
   - 에이전트 파일들이 위치할 디렉토리는 `c:\Users\hlahn\car_project\.agent\agents\<agent_name>` 입니다.

3. **`agent.json` 작성**:
   - 위 디렉토리에 에이전트의 메타데이터를 담은 `agent.json` 파일을 생성합니다.
   - 기본 형식은 다음과 같습니다:
     ```json
     {
       "name": "<agent_name>",
       "description": "<에이전트의 목적과 역할에 대한 간결한 설명>",
       "system_prompt_file": "system_prompt.md",
       "enable_mcp_tools": false,
       "enable_write_tools": true,
       "enable_subagent_tools": false
     }
     ```
   - 사용자의 요구에 따라 필요하다면 `enable_mcp_tools`나 `enable_subagent_tools`를 `true`로 설정할 수 있습니다.

4. **`system_prompt.md` 작성**:
   - 같은 디렉토리에 해당 에이전트의 성격, 행동 지침, 주력 언어/프레임워크, 제약 사항 등을 명시한 상세한 `system_prompt.md` 파일을 생성합니다.
   - 서브에이전트가 역할을 훌륭히 수행할 수 있도록 충분히 구체적이고 체계적인 마크다운 형식으로 작성합니다.

5. **완료 및 사용자 보고**:
   - 두 파일의 생성이 성공적으로 완료되면, 사용자에게 서브에이전트 생성이 완료되었음을 알립니다.
   - 생성된 에이전트 이름과 주요 설정 내용을 간략히 브리핑하고, 이제부터 해당 에이전트를 호출하여 사용할 수 있음을 안내합니다.
