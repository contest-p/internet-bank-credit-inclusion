import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

st.set_page_config(page_title="인터넷전문은행 중·저신용자 대출 규제 대시보드", layout="wide")

plt.rcParams['axes.unicode_minus'] = False

# 한글 폰트 자동 감지: 로컬(Windows: Malgun Gothic) / 클라우드(Linux: NanumGothic) 둘 다 대응
_KOREAN_FONT_CANDIDATES = ["Malgun Gothic", "NanumGothic", "AppleGothic"]
_available = {f.name for f in fm.fontManager.ttflist}
for _font in _KOREAN_FONT_CANDIDATES:
    if _font in _available:
        plt.rcParams['font.family'] = _font
        break

DATA_PATH = "data/데이터북_v4.xlsx"

st.title("인터넷전문은행 중·저신용자 대출 규제 실효성 대시보드")
st.caption("코디세이 미션 보너스 — 기간/은행/지표를 바꿔가며 탐색할 수 있습니다.")


@st.cache_data
def load_data():
    df_credit = pd.read_excel(DATA_PATH, sheet_name="월별_평균신용점수", skiprows=3)
    df_rate = pd.read_excel(DATA_PATH, sheet_name="월별_고금리비중", skiprows=3)
    df_credit["취급월"] = pd.to_datetime(df_credit["취급월"])
    df_rate["취급월"] = pd.to_datetime(df_rate["취급월"])
    df_credit["스프레드"] = df_credit["서민금융제외평균금리"] - df_credit["평균금리"]

    df_credit_wide = df_credit.pivot(index="취급월", columns="은행", values="평균신용점수").asfreq("MS")
    df_rate_wide = (
        df_rate.pivot(index="취급월", columns="은행", values="고금리8퍼센트이상비중")
        .asfreq("MS")
        .interpolate(method="linear")
    )
    df_spread_wide = df_credit.pivot(index="취급월", columns="은행", values="스프레드").asfreq("MS")

    return df_credit_wide, df_rate_wide, df_spread_wide


df_credit_wide, df_rate_wide, df_spread_wide = load_data()

METRICS = {
    "평균신용점수": (df_credit_wide, "점"),
    "고금리(8%↑) 취급비중": (df_rate_wide, "%"),
    "서민금융제외-평균금리 스프레드": (df_spread_wide, "%p"),
}

all_banks = list(df_credit_wide.columns)
min_date = min(df_credit_wide.index.min(), df_rate_wide.index.min())
max_date = max(df_credit_wide.index.max(), df_rate_wide.index.max())

with st.sidebar:
    st.header("필터")

    metric_name = st.selectbox("지표 선택", list(METRICS.keys()))

    selected_banks = st.multiselect("은행 선택", all_banks, default=all_banks)

    date_range = st.slider(
        "기간 선택",
        min_value=min_date.to_pydatetime(),
        max_value=max_date.to_pydatetime(),
        value=(min_date.to_pydatetime(), max_date.to_pydatetime()),
        format="YYYY-MM",
    )

    show_ma = st.checkbox("3개월 이동평균 함께 보기", value=False)

df_metric, unit = METRICS[metric_name]

if not selected_banks:
    st.warning("은행을 하나 이상 선택해 주세요.")
    st.stop()

filtered = df_metric.loc[date_range[0]:date_range[1], selected_banks]

if filtered.dropna(how="all").empty:
    st.warning("선택한 기간/은행 조합에 해당하는 데이터가 없습니다. 기간을 넓혀보세요.")
    st.stop()

col1, col2 = st.columns([3, 1])

with col1:
    fig, ax = plt.subplots(figsize=(10, 5))
    for bank in filtered.columns:
        ax.plot(filtered.index, filtered[bank], marker="o", markersize=3, label=bank)
        if show_ma:
            ax.plot(
                filtered.index,
                filtered[bank].rolling(3).mean(),
                linestyle="--",
                linewidth=1.5,
                alpha=0.8,
                label=f"{bank} (3개월 이동평균)",
            )
    if metric_name != "평균신용점수":
        ax.axhline(0, color="gray", linewidth=0.8, linestyle=":")
    ax.set_title(f"{metric_name} 추이 ({date_range[0]:%Y-%m} ~ {date_range[1]:%Y-%m})")
    ax.set_xlabel("취급월")
    ax.set_ylabel(f"{metric_name} ({unit})")
    ax.legend(fontsize=8)
    st.pyplot(fig)

with col2:
    st.subheader("선택 구간 요약")
    for bank in filtered.columns:
        s = filtered[bank].dropna()
        if len(s) == 0:
            continue
        st.metric(
            label=bank,
            value=f"{s.iloc[-1]:.2f} {unit}",
            delta=f"{(s.iloc[-1] - s.iloc[0]):+.2f} {unit} (구간 시작 대비)",
        )

st.subheader("원자료 (선택 구간)")
st.dataframe(filtered.round(2))

st.caption(
    "출처: 학술제 1차 출처 데이터북_v4(은행연합회·금융위 공시 원문 기반). "
    "고금리비중은 토스뱅크 2023-11, 2024-11 결측월을 선형보간 처리함."
)