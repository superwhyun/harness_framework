# Module Persona Framework

이 문서는 하네스 프레임워크의 모듈-페르소나 레이어 규약이다.
`HARNESS.md`가 phase/step 프로세스를 정의하듯, 이 문서는 모듈 구조와 페르소나를 정의한다.

## 개념

### 계층 구조

프로젝트는 피라미드 형태의 모듈 계층으로 구성된다.
각 모듈은 담당 페르소나를 가지며, 페르소나는 모듈 내부를 자율적으로 관리한다.
모듈 간 경계는 컨트랙트(Contract)로 정의된다.

```
Root
├── auth          [Auth Expert]
│   ├── token     [Token Manager]
│   └── session   [Session Manager]
└── data          [Data Expert]
    └── cache     [Cache Manager]
```

### 아티팩트 종류

| 아티팩트 | 위치 | 수명 | 역할 |
|---|---|---|---|
| `registry.json` | `docs/modules/` | 프로젝트 전체 | 전역 모듈 상태 대시보드 |
| `MODULE.md` | `docs/modules/{id}/` | 프로젝트 전체 | 모듈 페르소나 + 컨트랙트 |
| `ARCHITECTURE.md` | `docs/` | 프로젝트 전체 | 전체 기능/흐름 뷰 |
| `module-map.json` | `phases/{task}/` | phase 한정 | step 소유권 (thin, ref만) |
| `phases/steps` | `phases/{task}/` | phase 한정 | 작업 지시서 |

`docs/` 하위 파일은 항상 실제 코드와 동기화되어야 한다.
동기화는 step AC(Acceptance Criteria)의 일부로 강제된다.

---

## MODULE.md 형식

```markdown
---
id: auth/token
version: 1.0.0
parent: auth
persona: Token Manager
status: planned
contract_version: 1.0.0
---

# Token Manager

## Contract

### Inputs
- `create(userId: string, scope: string[]) → JWT`
- `verify(token: JWT) → {userId: string, scope: string[]} | TokenError`

### Errors
- `TokenError: EXPIRED | INVALID | MALFORMED`

### Dependencies
- upstream: auth
- downstream: 없음

## Autonomy
- 내부 구현: 자유
- Contract 변경: parent(auth) + downstream 페르소나와 협의, Manager 최종 승인
- 타 모듈 MODULE.md: 읽기만, 수정 금지
```

### status 값

| 값 | 의미 |
|---|---|
| `planned` | 설계됨, 구현 전 |
| `healthy` | 정상 동작 중 |
| `negotiating` | contract 변경 협의 중 |
| `broken` | 오류 상태, 수정 필요 |
| `deprecated` | 제거 예정, downstream 마이그레이션 중 |

---

## registry.json 형식

```json
{
  "schema_version": 1,
  "project": "my-app",
  "updated_at": "2026-01-01T00:00:00Z",
  "modules": {
    "auth": {
      "persona": "Auth Expert",
      "version": "1.0.0",
      "status": "healthy",
      "children": ["auth/token", "auth/session"],
      "module_doc": "docs/modules/auth/MODULE.md"
    },
    "auth/token": {
      "persona": "Token Manager",
      "version": "1.0.0",
      "status": "healthy",
      "children": [],
      "module_doc": "docs/modules/auth/token/MODULE.md"
    }
  }
}
```

---

## 프로세스

### Bootstrap (최초 1회, phase1/step0)

프로젝트 최초 phase의 step0에서 아래를 수행한다.

1. Manager가 모듈 경계를 정의한다
2. `scripts/scaffold_module.py`로 `docs/modules/` 구조를 생성한다
3. 각 MODULE.md의 Contract 초안을 작성한다
4. Manager가 검토 및 승인한다
5. `docs/ARCHITECTURE.md` 초안을 작성한다
6. 이후 step1부터 구현을 시작한다

```bash
python3 scripts/scaffold_module.py auth/token \
  --project my-app \
  --persona "Token Manager" \
  --parent auth
```

### 기능 추가/변경 (신규 phase)

```
step0: contract 협의 (변경 있을 때만)
  - 변경 모듈 MODULE.md contract 초안 수정
  - registry에 status: negotiating 표시
  - downstream 페르소나 영향 확인
  - Manager 승인 → version bump → status: healthy

step1+: 모듈별 구현
  - 해당 모듈 페르소나로 작동
  - owned_paths 안에서만 구현
  - 완료 시 MODULE.md version bump + registry 업데이트

마지막 step: 통합 검증
  - registry 전체 healthy 확인
  - docs/ARCHITECTURE.md 업데이트 (흐름 변경 시)
```

### Contract 협의 프로토콜

**Non-breaking 변경** (필드 추가 등):
- 오너 페르소나가 MODULE.md 수정
- downstream에 고지 (MODULE.md 읽기)
- Manager 승인

**Breaking 변경** (기존 제거/변경):
- registry에 `negotiating` 표시
- 오너 페르소나가 변경 초안 + 마이그레이션 계획 작성
- 모든 downstream 페르소나가 자기 MODULE.md에 대응 계획 기록
- Manager 최종 승인
- 모든 모듈 version bump 후 `healthy` 복귀

**규칙:**
- 자기 MODULE.md만 수정한다. 타 모듈 MODULE.md는 건드리지 않는다
- contract 변경은 step0에서 먼저 확정한 뒤 구현 step을 진행한다

### 모듈 Deprecation (2단계)

**stage 1 - 선언 (step0):**
- registry에 `deprecated` 표시
- MODULE.md에 `## Deprecation` 섹션 추가
  - replaced by, downstream 마이그레이션 대상 목록
- downstream 모듈마다 마이그레이션 step 생성

**stage 2 - 제거 (마지막 step):**
- downstream 전부 마이그레이션 완료 확인
- registry에서 항목 제거
- MODULE.md 파일 삭제
- ARCHITECTURE.md 업데이트

---

## 읽기 순서

세션 시작 시 아래 순서로 읽는다. 세션당 1회만 읽는다.

```
1. AGENTS.md
2. docs/HARNESS.md
3. docs/ARCHITECTURE.md
4. docs/modules/registry.json        ← 현재 모듈 상태 파악
5. docs/ADR.md
6. phases/project-manifest.json
7. phases/{task}/index.json
8. phases/{task}/module-map.json
9. docs/modules/{해당 모듈}/MODULE.md ← module-map 확인 후 해당 모듈만
10. phases/{task}/stepN.md
```

MODULE.md는 module-map에서 작업 대상 모듈을 확인한 뒤 해당 모듈만 읽는다.
관계없는 모듈의 MODULE.md는 읽지 않는다.

---

## docs/ 동기화 규칙

모든 step의 AC에 아래가 포함되어야 한다.

```
- [ ] docs/modules/{id}/MODULE.md contract가 구현과 일치한다
- [ ] docs/modules/registry.json version과 status가 최신이다
- [ ] docs/ARCHITECTURE.md 관련 섹션이 변경 사항을 반영한다 (흐름 변경 시)
```

docs가 코드보다 늦거나 틀리면 다음 세션의 AI가 잘못된 정보로 시작한다.
docs 업데이트는 구현의 일부이지 선택사항이 아니다.
