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
WAIT_CHART = 4.0   # 차트 업데이트 대기(초)

# Phase 1: BB 핵심 파라미터
BB_PERIODS = list(range(5, 22, 2))        # 5,7,9,11,13,15,17,19,21
BB_STDS    = [0.5, 1.0, 1.5, 2.0, 2.5]

# Phase 2: 리스크 파라미터
TAKE_PROFITS = list(range(20, 141, 20))   # 20,40,60,80,100,120,140
STOP_LOSSES  = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

# 설정창 input 실제 인덱스 (확인 완료)
IDX = {
    "start_date":  2,
    "bb_period":   6,
    "bb_std":      7,
    "take_profit": 10,
    "stop_loss":   12,
}
# ================================================

JS_SET_INPUT = """
(function(idx, val) {
    const inp = document.querySelectorAll('input')[idx];
    if (!inp) return 'no-input-' + idx;
    inp.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, String(val));
    inp.dispatchEvent(new Event('input',  {bubbles: true}));
    inp.dispatchEvent(new Event('change', {bubbles: true}));
    inp.dispatchEvent(new KeyboardEvent('keydown',  {key:'Tab', bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup',    {key:'Tab', bubbles:true}));
    return inp.value;
})(%d, %s)
"""

JS_CLICK_OK = """
(function() {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
        const txt = btn.textContent.trim();
        if (txt === '확인' || txt === 'OK' || txt === 'Apply') {
            btn.click(); return txt;
        }
    }
    // data-name 으로 시도
    const sub = document.querySelector('[data-name="submit-button"]');
    if (sub) { sub.click(); return 'submit-btn'; }
    return 'not-found';
})()
"""

JS_READ_PROFIT = """
(function() {
    function normalize(txt) {
        // U+2212 수학 마이너스 → 일반 하이픈으로 변환
        return txt.replace(/−/g, '-');
    }
    const all = document.querySelectorAll('*');
    for (const el of all) {
        if (!el.children.length && (el.innerText||'').trim() === '총 손익') {
            const next = el.nextElementSibling
                      || (el.parentElement && el.parentElement.nextElementSibling);
            if (next) {
                const txt = normalize(next.innerText || '');
                // "%" 포함 값 중 첫 번째 숫자 추출
                const m = txt.match(/([+-]?[\d,]+\.?\d*)\s*%/);
                if (m) return parseFloat(m[1].replace(/,/g, ''));
                // 폴백: 숫자만 추출
                const num = parseFloat(txt.replace(/[^-\d.]/g, ''));
                if (!isNaN(num)) return num;
            }
        }
    }
    return null;
})()
"""


def js(tab, expr):
    r = tab.Runtime.evaluate(expression=expr, returnByValue=True)
    return r.get("result", {}).get("value")


def mouse_move(tab, x, y):
    tab.Input.dispatchMouseEvent(type="mouseMoved", x=x, y=y)


def mouse_click(tab, x, y):
    tab.Input.dispatchMouseEvent(type="mousePressed", x=x, y=y, button="left", clickCount=1)
    time.sleep(0.05)
    tab.Input.dispatchMouseEvent(type="mouseReleased", x=x, y=y, button="left", clickCount=1)


def get_chart_tab():
    tabs_info = requests.get(f"{CDP_URL}/json").json()
    chart = next(
        (t for t in tabs_info if "tradingview.com/chart" in t.get("url", "")), None
    )
    if not chart:
        raise RuntimeError("TradingView 차트 탭을 찾을 수 없습니다.")
    browser = pychrome.Browser(url=CDP_URL)
    tabs    = browser.list_tab()
    tab     = next((t for t in tabs if t.id == chart["id"]), tabs[0])
    tab.start()
    return tab


def open_settings(tab):
    """BB Trend Scalper 설정창 열기 (CDP 마우스 이벤트 사용)"""
    # 1) 제목 위로 hover
    title_pos = js(tab, """(function(){
        const t=[...document.querySelectorAll('.title-l31H9iuA')]
                 .find(t=>t.textContent.includes('BB Trend Scalper'));
        if(!t) return null;
        const r=t.getBoundingClientRect();
        return JSON.stringify({x:r.x+r.width/2, y:r.y+r.height/2});
    })()""")
    if not title_pos:
        raise RuntimeError("BB Trend Scalper 제목을 찾을 수 없습니다.")
    p = json.loads(title_pos)
    mouse_move(tab, p["x"], p["y"])
    time.sleep(0.6)

    # 2) 설정 버튼 위치 → 클릭
    btn_pos = js(tab, """(function(){
        const titles=document.querySelectorAll('.title-l31H9iuA');
        for(const t of titles){
            if(t.textContent.includes('BB Trend Scalper')){
                let el=t;
                for(let i=0;i<8;i++){
                    el=el.parentElement; if(!el) break;
                    const btn=el.querySelector('[data-qa-id="legend-settings-action"]');
                    if(btn){
                        const r=btn.getBoundingClientRect();
                        return JSON.stringify({x:r.x+r.width/2, y:r.y+r.height/2});
                    }
                }
            }
        }
        return null;
    })()""")
    if not btn_pos:
        raise RuntimeError("설정 버튼을 찾을 수 없습니다.")
    b = json.loads(btn_pos)
    mouse_move(tab, b["x"], b["y"])
    time.sleep(0.2)
    mouse_click(tab, b["x"], b["y"])

    # 3) 설정창 열릴 때까지 대기 (최대 5초)
    for _ in range(10):
        cnt = js(tab, "document.querySelectorAll('input').length")
        if cnt and cnt > 5:
            time.sleep(0.3)
            return
        time.sleep(0.5)
    raise RuntimeError("설정창이 열리지 않았습니다.")


def set_params(tab, params: dict):
    for key, val in params.items():
        result = js(tab, JS_SET_INPUT % (IDX[key], repr(str(val))))
        if result is None or "no-input" in str(result):
            raise RuntimeError(f"입력 실패: {key}={val} (index={IDX[key]}, result={result})")
        time.sleep(0.1)


def apply_and_wait(tab):
    result = js(tab, JS_CLICK_OK)
    if result == "not-found":
        # 좌표로 OK 버튼 찾기 시도
        raise RuntimeError("OK 버튼을 찾을 수 없습니다.")
    time.sleep(WAIT_CHART)


def read_profit(tab):
    return js(tab, JS_READ_PROFIT)


def run_combo(tab, params: dict):
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


def main():
    print("TradingView 연결 중...")
    tab   = get_chart_tab()
    title = js(tab, "document.title")
    print(f"연결 성공: {title}")

    input("\nTradingView에서 [전략 리포트] 탭 열어두고 Enter 입력...")

    best_p1 = phase1(tab)
    if best_p1:
        best_p2 = phase2(tab, best_p1)
        print("\n=== 최종 최적 파라미터 ===")
        print(json.dumps(best_p2, indent=2, ensure_ascii=False))
    else:
        print("Phase 1 실패")

    tab.stop()


if __name__ == "__main__":
    main()
