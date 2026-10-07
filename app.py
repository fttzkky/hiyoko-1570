import streamlit as st
import yfinance as yf
import pandas as pd


st.set_page_config(page_title="ひよこ1570", layout="wide")
st.title("ひよこ1570")
st.caption("日経平均シグナル判定 × 1570リターン確認ツール（ひよこ式ベース）")


st.sidebar.header("⚙️ パラメータ設定")


mode = st.sidebar.radio(
    "判定モード",
    ["円モード（ひよこさん原著）", "%モード（価格水準補正）"],
    index=0
)


if mode == "円モード（ひよこさん原著）":
    threshold_yen = st.sidebar.slider(
        "シグナル閾値（円）",
        min_value=500, max_value=3000, value=1000, step=100,
        help="この円以上の下落で買いシグナル、この円以上の上昇で売りシグナル"
    )
    threshold_pct = None
else:
    threshold_pct = st.sidebar.slider(
        "シグナル閾値（前日比 %）",
        min_value=0.5, max_value=5.0, value=1.5, step=0.1,
        help="この%以上の下落で買いシグナル、この%以上の上昇で売りシグナル"
    )
    threshold_yen = None


start_year = st.sidebar.slider(
    "集計開始年",
    min_value=2010, max_value=2024, value=2020, step=1
)
start_date = f"{start_year}-01-01"


st.sidebar.markdown("---")
st.sidebar.markdown("**現在の設定**")
if threshold_yen:
    st.sidebar.markdown(f"- 閾値: **±{threshold_yen:,}円**")
else:
    st.sidebar.markdown(f"- 閾値: **±{threshold_pct:.1f}%**")
st.sidebar.markdown(f"- 開始: **{start_year}年〜**")
st.sidebar.markdown("---")
st.sidebar.markdown("**関連アプリ**")
st.sidebar.markdown("[ちょるこ式](https://choruko-swing-dwf39ocwzqubb3uattpjmi.streamlit.app)")
st.sidebar.markdown("[ひよこ式](https://choruko-swing-anvaomt9aunocm5irspcob.streamlit.app)")
st.sidebar.markdown("[レバウン式](https://reboun-app-fqpqv4e5nqdkqy3tibcxqn.streamlit.app)")
st.sidebar.markdown("---")
st.sidebar.markdown("⚠️ 投資判断はご自身の責任で")


@st.cache_data(ttl=3600, show_spinner="データ取得中...")
def get_data(start):
    n225_raw = yf.Ticker("^N225").history(start=start)
    n225_raw.index = n225_raw.index.tz_localize(None)
    n225 = n225_raw[["Close"]].copy()
    n225.columns = ["N225"]
    n225["change"] = n225["N225"].diff()
    n225["change_pct"] = n225["N225"].pct_change() * 100

    lev_raw = yf.download("1570.T", start=start, progress=False)
    if isinstance(lev_raw.columns, pd.MultiIndex):
        lev_raw.columns = lev_raw.columns.droplevel(1)
    lev = lev_raw[["Close"]].copy()
    lev.columns = ["LEV"]
    lev.index = pd.to_datetime(lev.index).tz_localize(None)

    df = n225.join(lev, how="left")
    return df


df = get_data(start_date)


if threshold_yen:
    buy_days = df[df["change"] <= -threshold_yen].copy()
    sell_days = df[df["change"] >= threshold_yen].copy()
    label = f"±{threshold_yen:,}円"
else:
    buy_days = df[df["change_pct"] <= -threshold_pct].copy()
    sell_days = df[df["change_pct"] >= threshold_pct].copy()
    label = f"±{threshold_pct:.1f}%"


latest = df.iloc[-1]
today_change = latest["change"]
today_pct = latest["change_pct"]
today_close = latest["N225"]


st.subheader("📡 本日のシグナル")
col1, col2, col3 = st.columns(3)
col1.metric(
    "日経平均",
    f"¥{today_close:,.0f}",
    f"{today_change:+,.0f}円 ({today_pct:+.2f}%)"
)


if threshold_yen:
    is_buy = today_change <= -threshold_yen
    is_sell = today_change >= threshold_yen
    detail = f"{today_change:+,.0f}円"
else:
    is_buy = today_pct <= -threshold_pct
    is_sell = today_pct >= threshold_pct
    detail = f"{today_pct:+.2f}%"


if is_buy:
    col2.success(f"🟢 買いシグナル（{detail}）")
elif is_sell:
    col2.error(f"🔴 売りシグナル（{detail}）")
else:
    col2.info(f"⬜ 待機（{detail}）")


col3.info(f"判定閾値: {label}")


st.divider()


st.subheader(f"📊 過去の{label}超え集計（{start_year}年〜）")


col1, col2 = st.columns(2)
col1.metric("🟢 買いシグナル", f"{len(buy_days)}回")
col2.metric("🔴 売りシグナル", f"{len(sell_days)}回")


st.subheader("📅 年別シグナル回数")
buy_by_year = buy_days.groupby(buy_days.index.year).size().rename("🟢 買い")
sell_by_year = sell_days.groupby(sell_days.index.year).size().rename("🔴 売り")
year_df = pd.concat([buy_by_year, sell_by_year], axis=1).fillna(0).astype(int)
year_df.index.name = "年"
st.dataframe(year_df, use_container_width=True)


st.divider()


def fmt_table(d):
    rows = []
    for idx, row in d.iterrows():
        pos = df.index.get_loc(idx)
        r = {
            "日付": idx.strftime("%Y-%m-%d"),
            "日経平均終値": int(round(row["N225"])),
            "前日差(円)": int(round(row["change"])),
            "前日比(%)": round(row["change_pct"], 2),
            "1570終値": int(round(row["LEV"])) if pd.notna(row.get("LEV")) else None,
        }
        for days, label_d in [(1, "1570翌日%"), (3, "1570 3日後%"), (5, "1570 5日後%")]:
            if pos + days < len(df):
                lev_now = df["LEV"].iloc[pos]
                lev_fut = df["LEV"].iloc[pos + days]
                if pd.notna(lev_now) and pd.notna(lev_fut) and lev_now != 0:
                    r[label_d] = round((lev_fut - lev_now) / lev_now * 100, 2)
                else:
                    r[label_d] = None
            else:
                r[label_d] = None
        rows.append(r)
    result = pd.DataFrame(rows).sort_values("日付", ascending=False)
    return result


tab1, tab2 = st.tabs(["🟢 買いシグナル一覧", "🔴 売りシグナル一覧"])


def color_ret(val):
    if val is None: return ""
    try:
        v = float(val)
        return "color: red" if v < 0 else "color: blue"
    except:
        return ""


with tab1:
    t = fmt_table(buy_days)
    styled = t.style.map(color_ret, subset=["1570翌日%", "1570 3日後%", "1570 5日後%"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    if len(buy_days) > 0:
        st.markdown("---")
        for col in ["1570翌日%", "1570 3日後%", "1570 5日後%"]:
            vals = t[col].dropna()
            if len(vals) > 0:
                wins = (vals > 0).sum()
                total = len(vals)
                avg = vals.mean()
                st.markdown(f"**{col}** ｜ 勝率: **{wins}/{total} ({wins/total*100:.1f}%)** ｜ 平均リターン: **{avg:+.2f}%**")


with tab2:
    t = fmt_table(sell_days)
    styled = t.style.map(color_ret, subset=["1570翌日%", "1570 3日後%", "1570 5日後%"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    if len(sell_days) > 0:
        st.markdown("---")
        for col in ["1570翌日%", "1570 3日後%", "1570 5日後%"]:
            vals = t[col].dropna()
            if len(vals) > 0:
                wins = (vals > 0).sum()
                total = len(vals)
                avg = vals.mean()
                st.markdown(f"**{col}** ｜ 勝率: **{wins}/{total} ({wins/total*100:.1f}%)** ｜ 平均リターン: **{avg:+.2f}%**")
