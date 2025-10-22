# app.py
import streamlit as st
import requests
import datetime
import pandas as pd

# --- 설정 ---
NEIS_BASE = "https://open.neis.go.kr/hub"
# 사용자가 앱 내에 키를 입력하거나 streamlit secrets에 NEIS_API_KEY를 넣어두면 사용합니다.
DEFAULT_KEY = st.secrets.get("NEIS_API_KEY", None)

st.set_page_config(page_title="학교 급식 메뉴 조회", layout="centered")

st.title("🏫 학교 급식메뉴 조회 (NEIS Open API)")
st.markdown("학교 이름을 입력하면 해당 학교의 급식(오늘 점심)을 보여줍니다. 먼저 NEIS(Open API) 인증키가 필요합니다.")

# 입력: API 키 (입력 없으면 secrets 또는 빈값으로 처리)
api_key_input = st.text_input("NEIS API Key (없으면 secrets의 NEIS_API_KEY 사용)", type="password")
API_KEY = api_key_input.strip() or DEFAULT_KEY

if not API_KEY:
    st.warning("NEIS API Key가 필요합니다. https://open.neis.go.kr 에서 발급받아 입력하세요.")
    st.stop()

# 사용자 입력: 지역(선택) + 학교명
col1, col2 = st.columns([1,2])
with col1:
    region = st.selectbox(
        "시도교육청",
        options=[
            "전체","서울특별시교육청","부산광역시교육청","대구광역시교육청","인천광역시교육청",
            "광주광역시교육청","대전광역시교육청","울산광역시교육청","세종특별자치시교육청",
            "경기도교육청","강원도교육청","충청북도교육청","충청남도교육청",
            "전라북도교육청","전라남도교육청","경상북도교육청","경상남도교육청","제주특별자치도교육청"
        ]
    )
with col2:
    school_name = st.text_input("학교명 (예: 서울고등학교, 금호초등학교 등)", max_chars=80)

date = st.date_input("조회일자", value=datetime.date.today())
query_date = date.strftime("%Y%m%d")

st.write("---")

@st.cache_data(show_spinner=False)
def find_school(api_key: str, name: str, region_name: str = None):
    """
    학교명으로 학교기본정보(schoolInfo)를 조회하여,
    후보 학교 리스트(교육청코드, 학교코드, 학교명)를 반환.
    """
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": name
    }
    # region_name이 제공되면 ATPT_OFCDC_SC_NM 파라미터로 필터 (NEIS에 따라 일부 지역명 매칭 필요)
    if region_name and region_name != "전체":
        # NEIS의 ATPT_OFCDC_SC_NM 값들이 '서울특별시교육청' 형태인데 사용자가 선택한 항목과 맞춤
        params["ATPT_OFCDC_SC_NM"] = region_name

    url = f"{NEIS_BASE}/schoolInfo"
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    # NEIS는 오류/메시지 구조가 있으니 안전하게 파싱
    if "schoolInfo" not in data or len(data["schoolInfo"]) < 1:
        return []
    try:
        items = data["schoolInfo"][1]["row"]
    except Exception:
        items = []
    results = []
    for it in items:
        results.append({
            "ATPT_OFCDC_SC_CODE": it.get("ATPT_OFCDC_SC_CODE"),
            "ATPT_OFCDC_SC_NM": it.get("ATPT_OFCDC_SC_NM"),
            "SD_SCHUL_CODE": it.get("SD_SCHUL_CODE"),
            "SCHUL_NM": it.get("SCHUL_NM"),
            "ENG_SCHUL_NM": it.get("ENG_SCHUL_NM", ""),
            "LCTN_ADRES": it.get("LCTN_ADRES", "")
        })
    return results

@st.cache_data(show_spinner=False)
def get_meal(api_key: str, atpt_code: str, sch_code: str, ymd: str):
    """
    mealServiceDietInfo로 해당 날짜의 급식을 조회
    """
    params = {
        "KEY": api_key,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": sch_code,
        "MLSV_YMD": ymd
    }
    url = f"{NEIS_BASE}/mealServiceDietInfo"
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "mealServiceDietInfo" not in data or len(data["mealServiceDietInfo"]) < 1:
        return []
    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except Exception:
        rows = []
    return rows

if st.button("급식 조회"):
    if not school_name.strip():
        st.error("학교명을 입력해 주세요.")
        st.stop()

    with st.spinner("학교 검색 중..."):
        try:
            schools = find_school(API_KEY, school_name.strip(), region)
        except Exception as e:
            st.error(f"학교 검색 실패: {e}")
            st.stop()

    if not schools:
        st.info("검색 결과가 없습니다. 학교명을 조금 다르게 입력해 보거나 시도교육청을 변경해 보세요.")
        st.stop()

    # 여러 후보가 있으면 선택
    if len(schools) > 1:
        st.write("검색된 학교 후보:")
        df_sch = pd.DataFrame(schools)
        # 보여주기
        st.dataframe(df_sch[["ATPT_OFCDC_SC_NM","SCHUL_NM","LCTN_ADRES","SD_SCHUL_CODE"]])
        idx = st.number_input("목록 중 표시된 행 번호 선택 (위 표의 0-based index)", min_value=0, max_value=len(schools)-1, value=0)
        chosen = schools[int(idx)]
    else:
        chosen = schools[0]

    st.markdown(f"**선택된 학교:** {chosen['SCHUL_NM']}  |  **교육청:** {chosen['ATPT_OFCDC_SC_NM']}")
    atpt = chosen["ATPT_OFCDC_SC_CODE"]
    sd = chosen["SD_SCHUL_CODE"]

    with st.spinner("급식 정보를 가져오는 중..."):
        try:
            meals = get_meal(API_KEY, atpt, sd, query_date)
        except Exception as e:
            st.error(f"급식 정보 가져오기 실패: {e}")
            st.stop()

    if not meals:
        st.info(f"{query_date}에 대한 급식 정보가 없습니다.")
        st.stop()

    # mealServiceDietInfo의 DDISH_NM에 점심/아침/저녁 구분 포함되므로 MMEAL_SC_CODE 확인
    # 보통 MMEAL_SC_CODE == "2"가 점심입니다. (1:아침, 2:중식, 3:석식)
    lunch_items = [m for m in meals if m.get("MMEAL_SC_CODE") in ("2", 2, "2 " , " 2")]
    if not lunch_items:
        # 점심 코드가 확실치 않으면 전체의 첫 item 사용
        lunch_items = meals

    # DDISH_NM 필드에서 메뉴 텍스트를 정리 (줄바꿈/숫자/알레르기 표기 제거)
    def clean_ddish(txt):
        if not txt:
            return ""
        txt = txt.replace("<br/>", "\n").replace("<br>", "\n")
        # NEIS는 메뉴에 숫자/알레르기 예: "감자채볶음1.5.10.13." 형태 -> 숫자와 마침표 제거
        import re
        txt = re.sub(r"[0-9]+\.", "", txt)
        txt = re.sub(r"\s*\d+\s*$", "", txt)
        return txt.strip()

    # 여러 행일 수 있으므로 합쳐서 표시
    displayed = []
    for item in lunch_items:
        menu = clean_ddish(item.get("DDISH_NM",""))
        kcal = item.get("CAL_INFO","")
        displayed.append({
            "date": item.get("MLSV_YMD",""),
            "meal_code": item.get("MMEAL_SC_CODE",""),
            "menu": menu,
            "kcal": kcal,
            "origin_info": item.get("ORPLC_INFO",""),
            "nutr_info": item.get("NTR_INFO","")
        })

    df = pd.DataFrame(displayed)
    # 보기 좋게 변환
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.date
        st.subheader(f"{df.iloc[0]['date']} 점심 메뉴")
        for i, row in df.iterrows():
            st.markdown(f"**메뉴:**\n{row['menu']}")
            if row['kcal']:
                st.caption(f"칼로리: {row['kcal']}")
            if row['origin_info']:
                st.caption(f"원산지/비고: {row['origin_info']}")
            st.write("---")
    else:
        st.info("표시할 급식 정보가 없습니다.")
