#!/usr/bin/env python3
"""
Embodied AI Requirements Validator Core
시나리오가 표준 요구사항(SR/ER/CR)을 충족하는지 LLM을 통해 검증합니다.
"""

import argparse
import json
import sys
from pathlib import Path

# 하네스 패키지 경로 설정
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from harness.executor import StepExecutor

def build_validation_prompt(scenario_text, requirements):
    req_list_str = "\n".join([
        f"- [{req['id']}] {req['description']} (Mandatory: {req['mandatory']})"
        for req in requirements
    ])
    
    return f"""당신은 Embodied AI 서비스 표준 검증관입니다. 
아래의 서비스 시나리오가 제공된 표준 요구사항들을 충족하는지 분석하십시오.

### 서비스 시나리오
{scenario_text}

### 표준 요구사항 목록
{req_list_str}

### 지시사항
1. 각 요구사항 ID별로 '충족(Pass)', '미충족(Fail)', '정보부족(Insufficient)' 중 하나로 판별하십시오.
2. 판별 근거(Rationale)를 시나리오의 구체적인 문구를 인용하여 짧게 설명하십시오.
3. 시나리오에 직접 언급되지 않았더라도 상식적으로 추론 가능한 경우 '충족'으로 간주할 수 있으나, 안전 관련 요구사항은 엄격하게 판단하십시오.
4. 결과는 반드시 아래의 JSON 형식으로만 응답하십시오.

```json
{{
  "scenario_summary": "시나리오 요약",
  "results": [
    {{
      "id": "요구사항 ID",
      "status": "Pass | Fail | Insufficient",
      "rationale": "판단 근거"
    }}
  ]
}}
```
"""

def main():
    parser = argparse.ArgumentParser(description="Embodied AI Requirements Validator")
    parser.add_argument("--scenario", required=True, help="Path to scenario file or raw text")
    parser.add_argument("--backend", help="Harness backend name")
    parser.add_argument("--output", help="Path to save the validation report (JSON)")
    args = parser.parse_args()

    # 1. 시나리오 데이터 로드
    scenario_path = Path(args.scenario)
    if scenario_path.exists():
        scenario_text = scenario_path.read_text(encoding="utf-8")
    else:
        scenario_text = args.scenario

    # 2. 요구사항 데이터 로드
    req_file = ROOT / "data" / "requirements.json"
    if not req_file.exists():
        print(f"ERROR: {req_file} not found. Run Phase 2 Step 0 first.")
        sys.exit(1)
    requirements = json.loads(req_file.read_text(encoding="utf-8"))["requirements"]

    # 3. 하네스 엔진 초기화 (백엔드 호출용)
    executor = StepExecutor(root=ROOT, phase_dir_name="2-ai-requirements-validator", backend_name=args.backend)
    backend = executor._backend

    # 4. 프롬프트 생성 및 호출
    prompt = build_validation_prompt(scenario_text, requirements)
    print(f"\n[Validator] Analyzing scenario with backend: {backend.name}...")
    
    result = backend.invoke(prompt, cwd=str(ROOT), timeout=600)

    # 5. 결과 처리 및 출력
    if result.exit_code == 0:
        stdout = result.stdout
        
        try:
            full_json = json.loads(stdout)
            content = full_json.get("response", stdout)
        except json.JSONDecodeError:
            content = stdout

        json_str = ""
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content and "}" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end].strip()
        
        if json_str:
            try:
                report = json.loads(json_str)
                stats = {"Pass": 0, "Fail": 0, "Insufficient": 0}
                for res in report.get("results", []):
                    status = res.get("status")
                    if status in stats:
                        stats[status] += 1
                
                report["statistics"] = stats
                
                print("\n=== Validation Report ===")
                print(f"Summary: {report.get('scenario_summary', 'N/A')}")
                print(f"Stats: Pass={stats['Pass']}, Fail={stats['Fail']}, Insufficient={stats['Insufficient']}")
                print("-" * 30)
                
                for res in report.get("results", []):
                    color = "\033[92m" if res['status'] == "Pass" else "\033[91m" if res['status'] == "Fail" else "\033[93m"
                    reset = "\033[0m"
                    print(f"[{res['id']}] {color}{res['status']}{reset}: {res['rationale']}")

                if args.output:
                    output_path = Path(args.output)
                    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"\n[✓] Report saved to: {args.output}")

            except json.JSONDecodeError:
                print("FAILED TO PARSE JSON. RAW OUTPUT:")
                print(content)
        else:
            print("NO JSON FOUND IN OUTPUT. RAW OUTPUT:")
            print(content)
    else:
        print(f"ERROR: Backend failed with code {result.exit_code}")
        print(result.stderr)

if __name__ == "__main__":
    main()
