import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="ひよこ1570", page_icon="🐣", layout="wide")
st.title("🐣 ひよこ1570")
st.caption("ひよこ式STEP3判定 × 1570（日経レバレッジETF）専用版")

# --- サイドバー ---
st.sidebar.header("⚙️ 設定")
lookback_days = st.sidebar.slider("過去何営業日まで遡るか", min_value=1, max_value=10, value=5)
start_date = st.sidebar.date_input("バックテスト開始日", value=datetime(2020, 1, 1))

st.sidebar.markdown("---")
st.sidebar.markdown("**関連アプリ**")
st.sidebar.markdown("[ちょるこ式](https://choruko-swing-dwf39ocwzqubb3uattpjmi.streamlit.app)")
st.sidebar.markdown("[ひよこ式](https://choruko-swing-anvaomt9aunocm5irspcob.streamlit.app)")
st.sidebar.markdown("[レバウン式](https://reboun-app-fqpqv4e5nqdkqy3tibcxqn.streamlit.app)")

# --- データ取得 ---
@st.cache_data(ttl=3600)
def load_data(start):
    end = datetime.today().strftime("%Y-%m-%d")
    raw = yf.download("1570.T", start=start, end=end, progress=False)
    if isinstance(raw, pd.DataFrame) and isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    return df

with st.spinner("1570データ取得中..."):
    try:
        df = load_data(start_date.strftime("%Y-%m-%d"))
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

if df.empty or len(df) < 30:
    st.error("データが取得できませんでした。")
    st.stop()

# --- STEP3指標計算 ---
def calc_rci(series, period=9):
    if len(series) < period:
        return 0.0
    recent = series.iloc[-period:].values
    n = period
    dr = np.arange(1, n + 1)
    pr = pd.Series(recent).rank(ascending=True).values
    dsq = np.sum((dr - pr) ** 2)
    return round((1 - 6 * dsq / (n * (n ** 2 - 1))) * 100, 1)

def calc_step3_at(df, end_idx):
    if end_idx == -1:
        sub = df
    else:
        sub = df.iloc[:end_idx + 1]
    if len(sub) < 30:
        return None
    close   = sub["Close"]
    ma25    = close.rolling(25).mean()
    ma50    = close.rolling(50).mean()
    ma100   = close.rolling(100).mean()
    bb_std  = close.rolling(25).std()
    if pd.isna(ma25.iloc[-1]) or pd.isna(bb_std.iloc[-1]) or bb_std.iloc[-1] == 0:
        return None
    bb_sigma = (close.iloc[-1] - ma25.iloc[-1]) / bb_std.iloc[-1]
    rci      = calc_rci(close, 9)
    change   = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
    ma25_dev = (close.iloc[-1] - ma25.iloc[-1]) / ma25.iloc[-1] * 100
    ma50_dev  = (close.iloc[-1] - ma50.iloc[-1])  / ma50.iloc[-1]  * 100 if not pd.isna(ma50.iloc[-1])  else None
    ma100_dev = (close.iloc[-1] - ma100.iloc[-1]) / ma100.iloc[-1] * 100 if not pd.isna(ma100.iloc[-1]) else None
    return {
        "price":      round(float(close.iloc[-1])),
        "change_pct": round(float(change), 2),
        "ma25_dev":   round(float(ma25_dev), 2),
        "ma50_dev":   round(float(ma50_dev), 2)  if ma50_dev  is not None else None,
        "ma100_dev":  round(float(ma100_dev), 2) if ma100_dev is not None else None,
        "bb_sigma":   round(float(bb_sigma), 2),
        "rci":        round(float(rci), 1),
    }

def count_s3n(s3):
    return sum([
        s3["change_pct"] <= -2.5,
        s3["ma25_dev"]   <  0,
        s3["bb_sigma"]   <= -3.0,
        s3["rci"]        <= -80,
    ])

# --- 本日の判定 ---
s3_today = calc_step3_at(df, -1)
if s3_today is None:
    st.error("指標計算に失敗しました。")
    st.stop()

s3n_today = count_s3n(s3_today)

st.markdown("---")
st.subheader(f"📊 本日の1570 STEP3判定（{df.index[-1].date()}）")

col1, col2, col3, col4 = st.columns(4)
col1.metric("株価", f"¥{s3_today['price']:,}", f"{s3_today['change_pct']:+.1f}%")
col2.metric("BB", f"{s3_today['bb_sigma']:.2f}σ", "✅" if s3_today['bb_sigma'] <= -3.0 else "❌")
col3.metric("RCI", f"{s3_today['rci']:.0f}%", "✅" if s3_today['rci'] <= -80 else "❌")
col4.metric("STEP3クリア", f"{s3n_today}/4", "🟢 買いシグナル" if s3n_today >= 3 else ("🟡" if s3n_today >= 2 else "🔴"))

with st.expander("詳細チェック", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.write("✅" if s3_today["change_pct"] <= -2.5 else "❌", f"前日比: {s3_today['change_pct']:+.1f}%　（条件: ≤ -2.5%）")
        st.write("✅" if s3_today["ma25_dev"] < 0 else "❌", f"MA25乖離: {s3_today['ma25_dev']:+.1f}%　（条件: < 0%）")
        ma50_str  = f"{s3_today['ma50_dev']:+.1f}%" if s3_today['ma50_dev'] is not None else "データ不足"
        ma100_str = f"{s3_today['ma100_dev']:+.1f}%" if s3_today['ma100_dev'] is not None else "データ不足"
        st.write("📊", f"MA50乖離: {ma50_str}")
        st.write("📊", f"MA100乖離: {ma100_str}")
    with c2:
        st.write("✅" if s3_today["bb_sigma"] <= -3.0 else "❌", f"BB: {s3_today['bb_sigma']:.2f}σ　（条件: ≤ -3.0σ）")
        st.write("✅" if s3_today["rci"] <= -80 else "❌", f"RCI: {s3_today['rci']:.0f}%　（条件: ≤ -80%）")

# --- 過去N日遡り ---
st.markdown("---")
st.subheader(f"🕐 過去{lookback_days}営業日以内にシグナルあり？")

best_s3n  = s3n_today
best_date = str(df.index[-1].date())
best_s3   = s3_today

for i in range(1, lookback_days):
    idx = len(df) - 1 - i
    if idx < 30:
        break
    s3_past = calc_step3_at(df, idx)
    if s3_past is None:
        continue
    s3n_past = count_s3n(s3_past)
    if s3n_past > best_s3n:
        best_s3n  = s3n_past
        best_date = str(df.index[idx].date())
        best_s3   = s3_past

if best_s3n >= 3:
    st.success(f"✅ {best_date} に {best_s3n}/4クリアのシグナルあり")
    if best_date != str(df.index[-1].date()):
        with st.expander(f"{best_date} の詳細"):
            st.write("✅" if best_s3["change_pct"] <= -2.5 else "❌", f"前日比: {best_s3['change_pct']:+.1f}%")
            st.write("✅" if best_s3["ma25_dev"] < 0 else "❌", f"MA25乖離: {best_s3['ma25_dev']:+.1f}%")
            st.write("✅" if best_s3["bb_sigma"] <= -3.0 else "❌", f"BB: {best_s3['bb_sigma']:.2f}σ")
            st.write("✅" if best_s3["rci"] <= -80 else "❌", f"RCI: {best_s3['rci']:.0f}%")
else:
    st.info(f"過去{lookback_days}日以内にシグナルなし（最大 {best_s3n}/4）")

# --- バックテスト ---
st.markdown("---")
st.subheader("📋 バックテスト：STEP3シグナル一覧")

records = []
for i in range(25, len(df) - 1):
    s3 = calc_step3_at(df, i)
    if s3 is None:
        continue
    if count_s3n(s3) >= 3:
        row = {
            "シグナル日": df.index[i].date(),
            "株価(円)": s3["price"],
            "前日比(%)": s3["change_pct"],
            "MA25乖離(%)": s3["ma25_dev"],
            "BB(σ)": s3["bb_sigma"],
            "RCI(%)": s3["rci"],
            "クリア数": count_s3n(s3),
        }
        for days, label in [(1, "翌日%"), (3, "3日後%"), (5, "5日後%")]:
            if i + days < len(df):
                ret = (df["Close"].iloc[i + days] - df["Close"].iloc[i]) / df["Close"].iloc[i] * 100
                row[label] = round(float(ret), 2)
            else:
                row[label] = None
        records.append(row)

if records:
    bt_df = pd.DataFrame(records)

    col1, col2, col3 = st.columns(3)
    col1.metric("シグナル発生回数", f"{len(bt_df)}回")
    col2.metric("分析期間", f"{df.index[25].date()} 〜 {df.index[-2].date()}")
    col3.metric("総営業日数", f"{len(df)}日")

    st.markdown("---")
    for col in ["翌日%", "3日後%", "5日後%"]:
        vals = bt_df[col].dropna()
        if len(vals) > 0:
            wins = (vals > 0).sum()
            total = len(vals)
            avg = vals.mean()
            st.markdown(f"**{col}** ｜ 勝率: **{{wins}}/{{total}} ({{wins/total*100:.1f}}%)** ｜ 平均リターン: **{{avg:+.2f}}%**")

    st.markdown("---")

    def color_ret(val):
        if val is None or val == "-": return ""
        try:
            v = float(val)
            return "color: red" if v < 0 else "color: blue"
        except:
            return ""

    styled = bt_df.style.map(color_ret, subset=["翌日%", "3日後%", "5日後%"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.warning("シグナルが見つかりませんでした。")

# --- チャート ---
st.markdown("---")
st.subheader("📈 1570 終値チャート")
st.line_chart(df["Close"], use_container_width=True)

st.caption("⚠️ 投資判断はご自身の責任で")
