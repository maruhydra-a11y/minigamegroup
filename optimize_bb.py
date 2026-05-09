"""
BB Trend Scalper 파라미터 최적화 (pychrome CDP 자동화)
Phase 1: BB Period × BB Std (45조합)
Phase 2: Take Profit × Stop Loss (49조합)
"""

import pychrome
import requests
import time
import csv
import itertools
import json

# ===================== 설정 =====================
CDP_URL    = "http://localhost:9222"
START_DATE = "2026-01-01"
WAIT_CHART = 4.0   # 차트 업데이트 대기(초) — 느리면 5~6으로 늘릴 것

# Phase 1: BB 핵심 파라미터
BB_PERIODS = list(range(5, 22, 2))        # 5,7,9,11,13,15,17,19,21
BB_STDS    = [0.5, 1.0, 1.5, 2.0, 2.5]   # 5가지

# Phase 2: 리스크 파라미터 (Phase 1 최적값 고정)
TAKE_PROFITS = list(range(20, 141, 20))   # 20,40,60,80,100,120,140
STOP_LOSSES  = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

# 설정창 input 인덱스 (스크린샷 순서 기준)
IDX = {
    "start_date":  0,   # Start Time 날짜
    "bb_period":   4,   # BB Period
    "bb_std":      5,   # BB 표준편차
    "take_profit": 8,   # Take Profit (%)
    "stop_loss":   10,  # Stop Loss (%)
}
# ================================================

# ── JavaScript 헬퍼 ──────────────────────────────

JS_OPEN_SETTINGS = """
(function() {
    const items = document.querySelectorAll('[data-name="legend-source-item"]');
    for (const item of items) {
        if (item.textContent.includes('BB Trend Scalper')) {
            item.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
            item.dispatchEvent(new MouseEvent('mouseover',  {bubbles: true}));
            const btn = item.querySelector('[data-name="legend-settings-action"]');
            if (btn) { btn.click(); return 'ok'; }
            return 'no-btn';
        }
    }
    return 'not-found';
})()
"""

JS_DIALOG_OPEN = "!!document.querySelector('[data-name=\"indicator-properties-dialog\"]')"

JS_SET_INPUT = """
(function(idx, val) {
    const dlg = document.querySelector('[data-name="indicator-properties-dialog"]');
    if (!dlg) return 'no-dialog';
    const inp = dlg.querySelectorAll('input')[idx];
    if (!inp) return 'no-input';
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, String(val));
    inp.dispatchEvent(new Event('input',  {bubbles: true}));
    inp.dispatchEvent(new Event('change', {bubbles: true}));
    return 'ok';
})(%d, %s)
"""

JS_CLICK_OK = """
(function() {
    const btn = document.querySelector('button[data-name="submit-button"]');
    if (btn) { btn.click(); return true; }
    return false;
})()
"""

JS_READ_PROFIT = """
(function() {
    // 방법 1: "총 손익" 텍스트 포함 요소 → 바로 다음 % 값 탐색 (한국어 TradingView)
    const all = document.querySelectorAll('*');
    for (const el of all) {
        const txt = (el.innerText || '').trim();
        if (!el.children.length && (txt === '총 손익' || txt === 'Net Profit')) {
            const candidates = [
                el.nextElementSibling,
                el.parentElement && el.parentElement.nextElementSibling,
            ];
            for (const c of candidates) {
                if (!c) continue;
                // "+43,247.76%" 형태 파싱
                const raw = c.innerText.replace(/[^-\d.]/g, '');
                const num = parseFloat(raw);
                if (!isNaN(num)) return num;
            }
        }
    }
    // 방법 2: "총 손익" 포함 부모 컨테이너에서 % 값 추출
    for (const el of all) {
        if ((el.innerText || '').includes('총 손익')) {
            const pct = el.innerText.match(/([+-]?[\d,]+\.?\d*)\s*%/);
            if (pct) return parseFloat(pct[1].replace(/,/g, ''));
        }
    }
    return null;
})()
"""


def js(tab, expr):
    """JavaScript 실행 → 결과값 반환"""
    res = tab.Runtime.evaluate(expression=expr, returnByValue=True)
    r = res.get("result", {})
    if r.get("type") == "undefined":
        return None
    return r.get("value")


def get_chart_tab():
    """TradingView 차트 탭에 연결된 pychrome Tab 반환"""
    tabs_info = requests.get(f"{CDP_URL}/json").json()
    chart = next(
        (t for t in tabs_info if "tradingview.com/chart" in t.get("url", "")),
        None
    )
    if not chart:
        raise RuntimeError("TradingView 차트 탭을 찾을 수 없습니다.")

    browser = pychrome.Browser(url=CDP_URL)
    tabs    = browser.list_tab()
    tab     = next((t for t in tabs if t.id == chart["id"]), tabs[0])
    tab.start()
    return tab


def open_settings(tab):
    """BB Trend Scalper 설정창 열기 (최대 3초 대기)"""
    js(tab, JS_OPEN_SETTINGS)
    for _ in range(10):
        if js(tab, JS_DIALOG_OPEN):
            time.sleep(0.3)
            return
        time.sleep(0.3)
    raise RuntimeError("설정창 열기 실패")


def set_params(tab, params: dict):
    """파라미터 dict를 순서대로 입력"""
    for key, val in params.items():
        result = js(tab, JS_SET_INPUT % (IDX[key], repr(str(val))))
        if result != "ok":
            raise RuntimeError(f"입력 실패: {key}={val} → {result}")
        time.sleep(0.12)


def apply_and_wait(tab):
    """OK 클릭 후 차트 업데이트 대기"""
    js(tab, JS_CLICK_OK)
    time.sleep(WAIT_CHART)


def read_profit(tab):
    """Strategy Tester 순수익률(%) 읽기"""
    return js(tab, JS_READ_PROFIT)


def run_combo(tab, params: dict):
    """단일 파라미터 조합 테스트 → 수익률 반환"""
    open_settings(tab)
    set_params(tab, {"start_date": START_DATE, **params})
    apply_and_wait(tab)
    return read_profit(tab)


def save_csv(filename, rows, fields):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  → 저장: {filename}")


# ─────────────────────────────────────────────
#  Phase 1: BB Period × BB Std
# ─────────────────────────────────────────────
def phase1(tab) -> dict | None:
    combos = list(itertools.product(BB_PERIODS, BB_STDS))
    total  = len(combos)
    rows   = []
    print(f"\n=== Phase 1 시작 ({total}조합, 예상 {total * WAIT_CHART / 60:.0f}분) ===")

    for i, (bp, bs) in enumerate(combos):
        print(f"  [{i+1:2}/{total}] BB_Period={bp:2}  BB_Std={bs}", end="  ", flush=True)
        try:
            profit = run_combo(tab, {"bb_period": bp, "bb_std": bs})
            print(f"→ {profit}%")
        except Exception as e:
            profit = None
            print(f"→ 오류: {e}")
        rows.append({"bb_period": bp, "bb_std": bs, "net_profit_pct": profit})

    save_csv("phase1_results.csv", rows, ["bb_period", "bb_std", "net_profit_pct"])

    valid = [r for r in rows if r["net_profit_pct"] is not None]
    best  = max(valid, key=lambda r: r["net_profit_pct"]) if valid else None
    print(f"Phase 1 최적: {best}")
    return best


# ─────────────────────────────────────────────
#  Phase 2: Take Profit × Stop Loss
# ─────────────────────────────────────────────
def phase2(tab, best_p1: dict) -> dict | None:
    combos = list(itertools.product(TAKE_PROFITS, STOP_LOSSES))
    total  = len(combos)
    bp, bs = best_p1["bb_period"], best_p1["bb_std"]
    rows   = []
    print(f"\n=== Phase 2 시작 ({total}조합, 예상 {total * WAIT_CHART / 60:.0f}분)"
          f"  BB_Period={bp}  BB_Std={bs} ===")

    for i, (tp, sl) in enumerate(combos):
        print(f"  [{i+1:2}/{total}] TP={tp:3}%  SL={sl}", end="  ", flush=True)
        try:
            profit = run_combo(tab, {"bb_period": bp, "bb_std": bs,
                                     "take_profit": tp, "stop_loss": sl})
            print(f"→ {profit}%")
        except Exception as e:
            profit = None
            print(f"→ 오류: {e}")
        rows.append({"bb_period": bp, "bb_std": bs,
                     "take_profit": tp, "stop_loss": sl, "net_profit_pct": profit})

    save_csv("phase2_results.csv", rows,
             ["bb_period", "bb_std", "take_profit", "stop_loss", "net_profit_pct"])

    valid = [r for r in rows if r["net_profit_pct"] is not None]
    best  = max(valid, key=lambda r: r["net_profit_pct"]) if valid else None
    print(f"Phase 2 최적: {best}")
    return best


# ─────────────────────────────────────────────
#  메인
# ─────────────────────────────────────────────
def main():
    print("TradingView 연결 중...")
    tab   = get_chart_tab()
    title = js(tab, "document.title")
    print(f"연결 성공: {title}")

    input("\nTradingView에서 [Strategy Tester] 탭 열어두고 Enter 입력...")

    best_p1 = phase1(tab)

    if best_p1:
        best_p2 = phase2(tab, best_p1)
        print("\n=== 최종 최적 파라미터 ===")
        print(json.dumps(best_p2, indent=2, ensure_ascii=False))
    else:
        print("Phase 1 실패 — 선택자 확인 필요")

    tab.stop()


if __name__ == "__main__":
    main()
