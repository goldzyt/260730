from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

KOBIS_KEY = st.secrets.get("KOBIS_KEY", "")


@st.cache_data(ttl=86400)
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

            for g in movie_info.get("genres", []):
                genre_name = g.get("genreNm", "").strip()
                if genre_name:
                    tags.append(f"#{genre_name}")

            for n in movie_info.get("nations", []):
                nation_name = n.get("nationNm", "").strip()
                if nation_name:
                    tags.append(f"#{nation_name}")

            audits = movie_info.get("audits", [])
            if audits:
                watch_grade = audits[0].get("watchGradeNm", "").strip()
                if watch_grade:
                    clean_grade = watch_grade.replace("이상관람가", "관람가")
                    tags.append(f"#{clean_grade}")

            show_tm = movie_info.get("showTm", "").strip()
            if show_tm and show_tm.isdigit():
                tags.append(f"#{show_tm}분")

            directors = movie_info.get("directors", [])
            if directors:
                dir_name = directors[0].get("peopleNm", "").strip()
                if dir_name:
                    tags.append(f"#{dir_name}감독")
    except Exception:
        pass

    fallback_tags = ["#개봉작", "#인기영화", "#박스오피스"]
    for fallback in fallback_tags:
        if len(tags) >= 3:
            break
        if fallback not in tags:
            tags.append(fallback)

    return " ".join(tags[:5])


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

if not box_list:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(box_list)

for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])


def format_rank_change(change):
    if change > 0:
        return f"▲ {change}"
    elif change < 0:
        return f"▼ {abs(change)}"
    else:
        return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_change)
df["display_movieNm"] = df.apply(
    lambda x: f"{x['movieNm']} 🏆" if x["audiAcc"] >= 1000000 else x["movieNm"],
    axis=1,
)

with st.spinner("영화별 해시태그 생성 중..."):
    df["movie_tags"] = df["movieCd"].apply(get_movie_tags)

top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("선택일 1위", top["display_movieNm"])
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

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

st.dataframe(
    table,
    column_config={
        "영화 태그": st.column_config.TextColumn("영화 태그"),
        "관객수": st.column_config.NumberColumn(format="%d명"),
        "누적관객": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    },
    use_container_width=True,
    hide_index=True,
)

# 6. 관객수 상위 5편 파이 차트 (말랑말랑 파스텔 도넛 차트)
st.subheader("📈 관객수 상위 5편 비율")
top5 = table.sort_values("관객수", ascending=False).head(5)

pastel_colors = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF"]

fig = px.pie(
    top5,
    values="관객수",
    names="영화명",
    hole=0.55,
    color_discrete_sequence=pastel_colors,
)

fig.update_traces(
    textinfo="percent",
    textfont=dict(size=14, family="Nanum Gothic, Malgun Gothic, sans-serif"),
    marker=dict(line=dict(color="#FFFFFF", width=4)),
    hoverinfo="label+value+percent",
    hovertemplate="<b>%{label}</b><br>관객수: %{value:,}명 (%{percent})<extra></extra>",
)

fig.update_layout(
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.2,
        xanchor="center",
        x=0.5,
        font=dict(size=13),
    ),
    annotations=[
        dict(
            text="<b>TOP 5</b><br>관객 점유율",
            x=0.5,
            y=0.5,
            font_size=16,
            showarrow=False,
            font_color="#555555",
        )
    ],
    margin=dict(t=30, b=80, l=20, r=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

st.plotly_chart(fig, use_container_width=True)
