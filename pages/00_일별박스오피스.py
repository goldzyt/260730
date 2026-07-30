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


# KOBIS 영화 상세 정보 API를 활용해 3~5개의 해시태그 생성하는 함수
@st.cache_data(ttl=86400)  # 하루 동안 캐싱
def get_movie_tags(movie_cd):
    tags = []

    try:
        detail_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
        res = requests.get(
            detail_url,
            params={"key": KOBIS_KEY, "movieCd": movie_cd},
            timeout=3,
        )
        if res.status_code == 200:
            movie_info = (
                res.json()
                .get("movieInfoResult", {})
                .get("movieInfo", {})
            )

            # 1. 장르 추출 (최대 3개)
            genres = movie_info.get("genres", [])
            for g in genres:
                genre_name = g.get("genreNm", "").strip()
                if genre_name:
                    tags.append(f"#{genre_name}")

            # 2. 대표 제작 국가 추출
            nations = movie_info.get("nations", [])
            for n in nations:
                nation_name = n.get("nationNm", "").strip()
                if nation_name:
                    tags.append(f"#{nation_name}")

            # 3. 관람 등급 추출
            audits = movie_info.get("audits", [])
            if audits:
                watch_grade = audits[0].get("watchGradeNm", "").strip()
                if watch_grade:
                    # '12세이상관람가' -> '12세관람가' 등으로 간결하게 다듬기
                    clean_grade = watch_grade.replace("이상관람가", "관람가")
                    tags.append(f"#{clean_grade}")

            # 4. 러닝 타임(상영 시간) 추출
            show_tm = movie_info.get("showTm", "").strip()
            if show_tm and show_tm.isdigit():
                tags.append(f"#{show_tm}분")

            # 5. 감독 이름 추출 (태그 수가 부족할 경우를 대비)
            directors = movie_info.get("directors", [])
            if directors:
                dir_name = directors[0].get("peopleNm", "").strip()
                if dir_name:
                    tags.append(f"#{dir_name}감독")

    except Exception:
        pass

    # 태그 개수를 최소 3개 ~ 최대 5개로 조정
    # 정보가 부족해서 3개 미만일 경우 기본 태그 추가
    fallback_tags = ["#개봉작", "#인기영화", "#박스오피스"]
    for fallback in fallback_tags:
        if len(tags) >= 3:
            break
        if fallback not in tags:
            tags.append(fallback)

    # 최대 5개까지만 자르기
    tags = tags[:5]

    return " ".join(tags)


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


# 3. 순위 변동 표시 함수 (양수: ▲, 음수: ▼)
def format_rank_change(change):
    if change > 0:
        return f"▲ {change}"
    elif change < 0:
        return f"▼ {abs(change)}"
    else:
        return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_change)

# 4. 100만 관객 이상 트로피 표시
df["display_movieNm"] = df.apply(
    lambda x: f"{x['movieNm']} 🏆" if x["audiAcc"] >= 1000000 else x["movieNm"],
    axis=1,
)

# 5. 해시태그 생성 (최소 3개, 최대 5개)
with st.spinner("영화별 해시태그 생성 중..."):
    df["movie_tags"] = df["movieCd"].apply(get_movie_tags)

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
        "순위변동",
        "display_movieNm",
        "movie_tags",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()

table.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "영화 태그",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader(f"📋 {selected_date.strftime('%Y년 %m월 %d일')} 박스오피스 TOP 10")

# Streamlit 데이터프레임
st.dataframe(
    table,
    column_config={
        "영화 태그": st.column_config.TextColumn(
            "영화 태그", help="장르, 국가, 등급, 러닝타임 등 상세 해시태그"
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
