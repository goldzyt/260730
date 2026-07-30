from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

# 비밀 금고에서 KOBIS 인증키 꺼내기
KOBIS_KEY = st.secrets.get("KOBIS_KEY", "")


# 별도 회원가입 없이 TMDB / KMDb 공용 API를 활용해 포스터 URL을 검색하는 함수
@st.cache_data(ttl=3600)  # Repeated search performance optimization
def get_movie_poster(movie_name):
    # 1차 시도: TMDB 오픈 API 이용
    try:
        encoded_title = requests.utils.quote(movie_name)
        tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key=15d2ea6d0dc1d476efbca3eba2b9bbf3&query={encoded_title}&language=ko-KR"
        res = requests.get(tmdb_url, timeout=3)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("poster_path"):
                return (
                    f"https://image.tmdb.org/t500{results[0]['poster_path']}"
                )
    except Exception:
        pass

    # 2차 시도: KMDb 공용 오픈 키 이용
    try:
        kmdb_url = "https://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp"
        params = {
            "collection": "kmdb_new2",
            "ServiceKey": "61141C063712T5122F02",  # KMDb 샘플 공용키
            "title": movie_name,
        }
        res = requests.get(kmdb_url, params=params, timeout=3)
        if res.status_code == 200:
            results = res.json().get("Data", [{}])[0].get("Result", [])
            if results and results[0].get("posters"):
                first_poster = results[0]["posters"].split("|")[0]
                if first_poster.startswith("http"):
                    return first_poster
    except Exception:
        pass

    # 포스터를 못 찾을 경우 기본 대체 이미지 반환
    encoded_name = requests.utils.quote(movie_name)
    return f"https://placehold.co/150x220/222222/FFFFFF/png?text={encoded_name}"


# 1. 날짜 선택기 설정 (최대 선택 가능 날짜: '어제')
yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    help="오늘 날짜 이후는 선택할 수 없습니다.",
)

target_dt = selected_date.strftime("%Y%m%d")

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(
    url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10
)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error(
        "인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요."
    )
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# 2. 비어있는 날짜 예외 처리
if not box_list:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자 데이터 형변환
for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])


# 3. 순위 변동 표시 함수 (양수: 빨간 위화살표, 음수: 파란 아래화살표)
def format_rank_change(change):
    if change > 0:
        return f"▲ {change}"
    elif change < 0:
        return f"▼ {abs(change)}"
    else:
        return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_change)

# 4. 누적 관객수 100만 이상 트로피 표시
df["display_movieNm"] = df.apply(
    lambda x: f"{x['movieNm']} 🏆" if x["audiAcc"] >= 1000000 else x["movieNm"],
    axis=1,
)

# 5. 영화 포스터 가져오기
with st.spinner("영화 포스터 불러오는 중..."):
    df["poster"] = df["movieNm"].apply(get_movie_poster)

# 1위 영화 상단 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("선택일 1위", top["display_movieNm"])
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

# 표 데이터 정리
table = df[
    [
        "rank",
        "poster",
        "순위변동",
        "display_movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()
table.columns = [
    "순위",
    "포스터",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader(f"📋 {selected_date.strftime('%Y년 %m월 %d일')} 박스오피스 TOP 10")
st.caption("💡 포스터 이미지에 마우스를 올리거나 클릭하면 크게 확대해 볼 수 있습니다.")

# Streamlit 데이터프레임 (포스터 호버/확대 기능 지원)
st.dataframe(
    table,
    column_config={
        "포스터": st.column_config.ImageColumn(
            "포스터", help="마우스를 올려 포스터를 크게 볼 수 있습니다."
        ),
        "관객수": st.column_config.NumberColumn(format="%d명"),
        "누적관객": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    },
    use_container_width=True,
    hide_index=True,
)

# 6. 관객수 상위 5편 파이 차트
st.subheader("📈 관객수 상위 5편 비율")
top5 = table.sort_values("관객수", ascending=False).head(5)

fig = px.pie(
    top5,
    values="관객수",
    names="영화명",
    title="상위 5개 영화 관객수 점유율",
    hole=0.3,
)
fig.update_traces(textinfo="percent+label")
st.plotly_chart(fig, use_container_width=True)
