"""
BB Trend Scalper 파라미터 최적화 (CDP 자동화)
Phase 1: BB Period × BB Std (45조합)
Phase 2: Take Profit × Stop Loss (48조합)
"""

import asyncio
import csv
import itertools
from playwright.async_api import async_playwright

# ===================== 설정 =====================
CDP_URL = "http://localhost:9222"   # TradingView CDP 포트 (확인 후 변경)
START_DATE = "2026-01-01"           # 백테스트 시작일
WAIT_AFTER_APPLY = 3.0              # 차트 업데이트 대기 (초) — 느리면 4~5로 늘릴 것

# Phase 1: BB 핵심 파라미터
BB_PERIODS = list(range(5, 22, 2))   # 5,7,9,11,13,15,17,19,21
BB_STDS    = [0.5, 1.0, 1.5, 2.0, 2.5]

# Phase 2: 리스크 파라미터 (Phase 1 최적값 사용)
TAKE_PROFITS = list(range(20, 141, 20))  # 20,40,60,80,100,120,140
STOP_LOSSES  = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

# 설정창 input 인덱스 (스크린샷 기준 순서)
IDX_START_DATE  = 0
IDX_BB_PERIOD   = 4
IDX_BB_STD      = 5
IDX_NOISE       = 6
IDX_TAKE_PROFIT = 8
IDX_STOP_LOSS   = 10

PHASE1_CSV = "phase1_results.csv"
PHASE2_CSV = "phase2_results.csv"
# ================================================


async def connect(playwright):
    browser = await playwright.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
    page    = context.pages[0]
    print(f"연결: {page.url[:80]}")
    return browser, page


async def open_settings(page):
    """BB Trend Scalper 설정창 열기"""
    legend = page.locator('[data-name="legend-source-item"]').filter(has_text="BB Trend Scalper")
    await legend.hover()
    await asyncio.sleep(0.3)
    await page.locator('[data-name="legend-settings-action"]').first.click()
    await page.wait_for_selector('[data-name="indicator-properties-dialog"]', timeout=10000)
    await asyncio.sleep(0.5)


async def set_input(dialog, index: int, value):
    """설정창 n번째 input에 값 입력"""
    inp = dialog.locator('input').nth(index)
    await inp.triple_click()
    await inp.fill(str(value))
    await inp.press("Tab")
    await asyncio.sleep(0.15)


async def apply_settings(page):
    """OK 클릭 후 차트 업데이트 대기"""
    await page.locator('button[data-name="submit-button"]').click()
    await asyncio.sleep(WAIT_AFTER_APPLY)


async def read_net_profit(page) -> float | None:
    """Strategy Tester 패널에서 순수익률(%) 읽기"""
    value = await page.evaluate("""() => {
        // 'Net Profit' 레이블 옆 값 탐색
        const labels = document.querySelectorAll('[class*="title"], [class*="label"]');
        for (const lbl of labels) {
            if (lbl.innerText && lbl.innerText.trim() === 'Net Profit') {
                const parent  = lbl.closest('[class*="item"], [class*="row"], tr');
                const sibling = parent ? parent.querySelector('[class*="value"], [class*="amount"], td + td') : null;
                if (sibling) {
                    const txt = sibling.innerText.replace(/[^\\-\\d.]/g, '');
                    const num = parseFloat(txt);
                    if (!isNaN(num)) return num;
                }
            }
        }
        // 폴백: % 포함 요소 중 첫 번째 숫자
        const cells = document.querySelectorAll('[class*="profit"], [class*="Profit"]');
        for (const el of cells) {
            const txt = el.innerText || '';
            if (txt.includes('%')) {
                const num = parseFloat(txt.replace(/[^\\-\\d.]/g, ''));
                if (!isNaN(num)) return num;
            }
        }
        return null;
    }""")
    return value


def save_csv(filename: str, rows: list, fieldnames: list):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {filename}")


# ─────────────────────────────────────────────
#  Phase 1: BB Period × BB Std
# ─────────────────────────────────────────────
async def phase1(page) -> dict:
    combos = list(itertools.product(BB_PERIODS, BB_STDS))
    total  = len(combos)
    rows   = []

    print(f"\n=== Phase 1 시작 ({total}조합) ===")

    for i, (bp, bs) in enumerate(combos):
        print(f"  [{i+1:2}/{total}] BB_Period={bp:2}  BB_Std={bs}", end="  ", flush=True)
        try:
            await open_settings(page)
            dlg = page.locator('[data-name="indicator-properties-dialog"]')

            await set_input(dlg, IDX_START_DATE, START_DATE)
            await set_input(dlg, IDX_BB_PERIOD,  bp)
            await set_input(dlg, IDX_BB_STD,     bs)

            await apply_settings(page)
            profit = await read_net_profit(page)
            print(f"→ {profit}%")
        except Exception as e:
            profit = None
            print(f"→ 오류: {e}")

        rows.append({"bb_period": bp, "bb_std": bs, "net_profit_pct": profit})

    save_csv(PHASE1_CSV, rows, ["bb_period", "bb_std", "net_profit_pct"])

    valid = [r for r in rows if r["net_profit_pct"] is not None]
    best  = max(valid, key=lambda r: r["net_profit_pct"]) if valid else None
    print(f"\nPhase 1 최적: {best}")
    return best


# ─────────────────────────────────────────────
#  Phase 2: Take Profit × Stop Loss
# ─────────────────────────────────────────────
async def phase2(page, best_p1: dict):
    combos = list(itertools.product(TAKE_PROFITS, STOP_LOSSES))
    total  = len(combos)
    rows   = []

    print(f"\n=== Phase 2 시작 ({total}조합)  BB_Period={best_p1['bb_period']}  BB_Std={best_p1['bb_std']} ===")

    for i, (tp, sl) in enumerate(combos):
        print(f"  [{i+1:2}/{total}] TP={tp:3}%  SL={sl}", end="  ", flush=True)
        try:
            await open_settings(page)
            dlg = page.locator('[data-name="indicator-properties-dialog"]')

            await set_input(dlg, IDX_START_DATE,  START_DATE)
            await set_input(dlg, IDX_BB_PERIOD,   best_p1["bb_period"])
            await set_input(dlg, IDX_BB_STD,      best_p1["bb_std"])
            await set_input(dlg, IDX_TAKE_PROFIT, tp)
            await set_input(dlg, IDX_STOP_LOSS,   sl)

            await apply_settings(page)
            profit = await read_net_profit(page)
            print(f"→ {profit}%")
        except Exception as e:
            profit = None
            print(f"→ 오류: {e}")

        rows.append({
            "bb_period": best_p1["bb_period"],
            "bb_std":    best_p1["bb_std"],
            "take_profit": tp,
            "stop_loss":   sl,
            "net_profit_pct": profit,
        })

    save_csv(PHASE2_CSV, rows, ["bb_period", "bb_std", "take_profit", "stop_loss", "net_profit_pct"])

    valid = [r for r in rows if r["net_profit_pct"] is not None]
    best  = max(valid, key=lambda r: r["net_profit_pct"]) if valid else None
    print(f"\nPhase 2 최적: {best}")
    return best


# ─────────────────────────────────────────────
#  메인
# ─────────────────────────────────────────────
async def main():
    async with async_playwright() as p:
        browser, page = await connect(p)

        # Strategy Tester 탭이 열려 있는지 확인
        input("TradingView에서 Strategy Tester 탭을 열어두었는지 확인 후 Enter 입력...")

        best_p1 = await phase1(page)

        if best_p1:
            best_p2 = await phase2(page, best_p1)
            print("\n=== 최종 최적 파라미터 ===")
            print(best_p2)
        else:
            print("Phase 1 실패 — CDP 연결/선택자 확인 필요")


if __name__ == "__main__":
    asyncio.run(main())
