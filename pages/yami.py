import streamlit as st
import requests
import datetime
import pandas as pd
import plotly.graph_objects as go

# ---------- 기본 설정 ----------
st.set_page_config(page_title="학교 급식 조회", layout="centered")
NEIS_BASE = "https://open.neis.go.kr/hub"
DEFAULT_KEY = st.secrets.get("NEIS_API_KEY", None)

st.title("🍱 전국 학교 급식 메뉴 서비스")
st.caption("NEIS Open API를 이용해 학교 급식 메뉴를 보여줍니다.")

# ---------- API Key ----------
api_key_input = st.text_input("🔑 NEIS API Key", type="password", placeholder="secrets.toml에 저장 시 생략 가능")
API_KEY = api_key_input.strip() or DEFAULT_KEY
if not API_KEY:
    st.warning("NEIS API Key가 필요합니다. [NEIS Open API](https://open.neis.go.kr)에서 발급받아 주세요.")
    st.stop()


# ---------- 함수 정의 ----------
@st.cache_data(show_spinner=False)
def find_school(api_key: str, name: str):
    """학교명으로 NEIS에서 학교 검색"""
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": name
    }
    r = requests.get(f"{NEIS_BASE}/schoolInfo", params=params, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    if "schoolInfo" not in data:
        return []
    try:
        rows = data["schoolInfo"][1]["row"]
    except Exception:
        return []
    return [
        {
            "label": f"{r['SCHUL_NM']} ({r['ATPT_OFCDC_SC_NM']})",
            "ATPT_OFCDC_SC_CODE": r["ATPT_OFCDC_SC_CODE"],
            "SD_SCHUL_CODE": r["SD_SCHUL_CODE"],
            "name": r["SCHUL_NM"],
            "office": r["ATPT_OFCDC_SC_NM"]
        }
        for r in rows
    ]


@st.cache_data(show_spinner=False)
def get_meal_month(api_key: str, atpt_code: str, sch_code: str, year: int, month: int):
    """해당 월의 급식 정보 전체 불러오기"""
    start_date = datetime.date(year, month, 1)
    end_date = (start_date + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    params = {
        "KEY": api_key,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sch_code,
        "MLSV_FROM_YMD": start_date.strftime("%Y%m%d"),
        "MLSV_TO_YMD": end_date.strftime("%Y%m%d")
    }
    r = requests.get(f"{NEIS_BASE}/mealServiceDietInfo", params=params, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    if "mealServiceDietInfo" not in data:
        return []
    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except Exception:
        return []
    return rows


def clean_menu(txt):
    """메뉴 문자열 정리"""
    if not txt:
        return ""
    txt = txt.replace("<br/>", "\n").replace("<br>", "\n")
    import re
    txt = re.sub(r"[0-9]+\.", "", txt)
    return txt.strip()


def make_calendar(meals_df: pd.DataFrame, year: int, month: int):
    """월별 급식 달력 생성 (Plotly)"""
    days = [datetime.date(year, month, d) for d in range(1, 32)
            if datetime.date(year, month, 1).replace(day=d).month == month]
    day_of_week = [d.weekday() for d in days]  # 0=월,6=일
    text = []
    for d in days:
        row = meals_df[meals_df["date"] == d]
        if not row.empty:
            text.append(f"{d.day}\n🍽️ {row.iloc[0]['menu'].splitlines()[0]}")
        else:
            text.append(str(d.day))

    fig = go.Figure(
        data=go.Scatter(
            x=day_of_week,
            y=[(d.day-1)//7 for d in days],
            text=text,
            mode="text",
            textfont=dict(size=12),
        )
    )
    fig.update_xaxes(
        tickvals=list(range(7)),
        ticktext=["월", "화", "수", "목", "금", "토", "일"],
        showgrid=False
    )
    fig.update_yaxes(visible=False)
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10,b=10,l=10,r=10))
    return fig


# ---------- UI: 학교 자동완성 ----------
school_query = st.text_input("🏫 학교명 입력", placeholder="예: 서울고등학교")

if school_query:
    results = find_school(API_KEY, school_query)
    if results:
        school_option = st.selectbox("검색된 학교", results, format_func=lambda x: x["label"])
    else:
        st.warning("검색된 학교가 없습니다.")
        st.stop()
else:
    st.info("학교명을 입력하면 자동완성 목록이 표시됩니다.")
    st.stop()


# ---------- 달력 보기 ----------
today = datetime.date.today()
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("조회 연도", min_value=2010, max_value=2100, value=today.year)
with col2:
    month = st.number_input("조회 월", min_value=1, max_value=12, value=today.month)

if st.button("급식 달력 보기"):
    with st.spinner("급식 정보를 불러오는 중..."):
        meals = get_meal_month(API_KEY, school_option["ATPT_OFCDC_SC_CODE"], school_option["SD_SCHUL_CODE"], year, month)

    if not meals:
        st.warning(f"{year}년 {month}월의 급식 정보가 없습니다.")
        st.stop()

    # 점심(2)만 필터링
    lunch = [m for m in meals if str(m.get("MMEAL_SC_CODE")) == "2"]

    df = pd.DataFrame([
        {"date": datetime.datetime.strptime(m["MLSV_YMD"], "%Y%m%d").date(),
         "menu": clean_menu(m["DDISH_NM"])}
        for m in lunch
    ])

    st.subheader(f"📅 {school_option['name']} ({year}년 {month}월 급식 달력)")
    st.plotly_chart(make_calendar(df, year, month), use_container_width=True)

    # 상세 메뉴 표시
    st.write("---")
    st.subheader("📋 날짜별 점심 메뉴")
    for _, row in df.iterrows():
        st.markdown(f"**{row['date']}**\n\n{row['menu']}")
        st.write("---")

