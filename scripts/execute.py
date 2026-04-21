#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.
(Refactored version using harness package)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # harness 패키지를 찾기 위해 최상위 경로 추가

from harness.executor import StepExecutor

def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--backend", help="Backend name from harness.json or built-in defaults")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    args = parser.parse_args()

    # StepExecutor는 이제 harness.executor 모듈에서 가져와 사용합니다.
    executor = StepExecutor(
        root=ROOT,
        phase_dir_name=args.phase_dir,
        backend_name=args.backend,
        auto_push=args.push
    )
    executor.run()

if __name__ == "__main__":
    main()
