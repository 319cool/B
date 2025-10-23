import streamlit as st
import requests
import datetime
import pandas as pd

# ---------- 기본 설정 ----------
st.set_page_config(page_title="학교 급식 주간 조회", layout="centered")
NEIS_BASE = "https://open.neis.go.kr/hub"
DEFAULT_KEY = st.secrets.get("NEIS_API_KEY", None)

st.title("🍱 전국 학교 급식 주간 조회")
st.caption("NEIS Open API를 이용해 선택한 날짜가 포함된 주의 급식 메뉴를 보여줍니다.")

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
def get_meal_range(api_key: str, atpt_code: str, sch_code: str, start_date: str, end_date: str):
    """기간 내 급식 정보 가져오기"""
    params = {
        "KEY": api_key,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sch_code,
        "MLSV_FROM_YMD": start_date,
        "MLSV_TO_YMD": end_date
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

# ---------- 날짜 선택 ----------
selected_date = st.date_input("📅 날짜 선택", value=datetime.date.today())

# 선택된 날짜가 포함된 주 계산 (월요일~일요일)
week_start = selected_date - datetime.timedelta(days=selected_date.weekday())
week_end = week_start + datetime.timedelta(days=6)

st.markdown(f"**📆 주간 기간:** {week_start} ~ {week_end}")

if st.button("주간 급식 조회"):
    with st.spinner("급식 정보를 불러오는 중..."):
        meals = get_meal_range(
            API_KEY,
            school_option["ATPT_OFCDC_SC_CODE"],
            school_option["SD_SCHUL_CODE"],
            week_start.strftime("%Y%m%d"),
            week_end.strftime("%Y%m%d")
        )

    if not meals:
        st.warning("선택한 주간의 급식 정보가 없습니다.")
        st.stop()

    # 점심만 필터링
    lunch = [m for m in meals if str(m.get("MMEAL_SC_CODE")) == "2"]

    if not lunch:
        st.info("해당 주간에 점심 급식 정보가 없습니다.")
        st.stop()

    df = pd.DataFrame([
        {
            "date": datetime.datetime.strptime(m["MLSV_YMD"], "%Y%m%d").date(),
            "menu": clean_menu(m["DDISH_NM"]),
            "kcal": m.get("CAL_INFO", "")
        }
        for m in lunch
    ])
    df = df.sort_values("date")

    st.subheader(f"🍱 {school_option['name']} ({week_start} ~ {week_end}) 주간 급식표")

    for _, row in df.iterrows():
        weekday_name = ["월", "화", "수", "목", "금", "토", "일"][row["date"].weekday()]
        st.markdown(f"### 🗓️ {row['date']} ({weekday_name}요일)")
        st.markdown(row["menu"])
        if row["kcal"]:
            st.caption(f"칼로리: {row['kcal']}")
        st.write("---")
