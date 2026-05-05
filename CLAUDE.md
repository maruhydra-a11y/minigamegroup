# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

5가지 브라우저 미니게임 모음 사이트. 빌드 도구, 패키지 매니저, 외부 라이브러리 없이 순수 HTML/CSS/JavaScript로만 구성된 정적 사이트.

**배포:** GitHub Pages — https://maruhydra-a11y.github.io/minigamegroup/
**저장소:** https://github.com/maruhydra-a11y/minigamegroup

## 실행 방법

빌드 불필요. 파일을 브라우저로 직접 열거나 GitHub Pages URL로 접속.

```powershell
# 로컬 확인
Start-Process "C:\Users\HOME\OneDrive\문서\CLAUDE\index.html"

# 배포 사이트 확인
Start-Process "https://maruhydra-a11y.github.io/minigamegroup/"
```

변경 사항은 `git push` 후 약 1~2분 내에 GitHub Pages에 자동 반영됨.

## 파일 구조

```
index.html        # 게임 허브 홈페이지 (게임 선택 카드 UI)
minesweeper.html  # 지뢰찾기
2048.html         # 2048 슬라이딩 퍼즐
snake.html        # 뱀 게임 (Canvas)
memory.html       # 기억력 카드 (CSS 3D flip)
breakout.html     # 벽돌 깨기 (Canvas)
```

## 아키텍처

각 게임은 완전히 독립된 단일 HTML 파일. HTML/CSS/JS가 한 파일 안에 인라인으로 포함되며 파일 간 공유 코드 없음.

**공통 패턴 (모든 게임 파일에 반복 적용):**
- 상단 고정 `.game-nav` — `← 홈으로` 링크(index.html)와 게임 제목
- `body`에 `padding-top: 48px` — 고정 nav 높이 보정
- 다크 테마 베이스 색상: 배경 `#0d0f1a`, 서피스 `#111827`, 카드 `#161f30`
- Canvas 기반 게임(snake, breakout)은 `requestAnimationFrame` 또는 `setInterval` 게임 루프 사용
- 최고 점수 등 영속 데이터는 `localStorage` 저장

**index.html 카드 색상 체계:**

| 게임 | CSS 클래스 | 색상 |
|------|-----------|------|
| 지뢰찾기 | `.blue` | `#4a9eff` |
| 2048 | `.orange` | `#f6a623` |
| 뱀 게임 | `.green` | `#4caf50` |
| 기억력 카드 | `.purple` | `#a855f7` |
| 벽돌 깨기 | `.red` | `#ef4444` |

## Git / 배포

Stop 훅(`.claude/settings.local.json`)이 설정되어 있어 Claude 응답 종료 시 변경 파일을 자동 커밋·push함. 수동 커밋이 필요한 경우:

```powershell
cd "C:\Users\HOME\OneDrive\문서\CLAUDE"
git add <파일>
git commit -m "설명"
git push
```
