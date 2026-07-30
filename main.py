import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# 1. 페이지 기본 설정 (와이드 모드 적용)
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 고령화율 지도")
st.caption("2015~2026년 인구 데이터 중 가장 최신 연도를 기준으로 65세 이상 인구 비율을 시각화합니다.")

# 2. 데이터 불러오기 함수 (캐싱 적용으로 속도 향상)
@st.cache_data
def load_data():
    # A. 인구 데이터 불러오기 (코드는 반드시 문자열(str)로 지정)
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # pandas로 csv.gz 파일을 읽을 때 코드 열을 문자열 타입으로 강제 지정
    df = pd.read_csv(pop_url, compression='gzip', dtype={'코드': str})
    
    # 행정동 코드(10자리)에서 앞 5자리를 추출하여 시군구 코드로 사용
    df['sigungu_code'] = df['코드'].str.slice(0, 5)
    
    # 데이터 중 가장 최신 연도 선택
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 65세 이상 컬럼 찾아내기 ('계_65세' ~ '계_100세 이상')
    # 나이 숫자를 추출하여 65세 이상인 '계_' 컬럼만 필터링합니다.
    total_cols = [c for c in df_latest.columns if c.startswith('계_')]
    age_65_plus_cols = []
    
    for col in total_cols:
        age_str = col.replace('계_', '').replace('세 이상', '').replace('세', '')
        if age_str.isdigit() and int(age_str) >= 65:
            age_65_plus_cols.append(col)
            
    # 전체 인구와 65세 이상 인구 합계 산출
    df_latest['전체인구'] = df_latest[total_cols].sum(axis=1)
    df_latest['고령인구'] = df_latest[age_65_plus_cols].sum(axis=1)
    
    # 시군구 단위로 집계 (시도, 시군구명 포함)
    sigungu_df = df_latest.groupby(['sigungu_code', '시도', '시군구'], as_index=False)[['전체인구', '고령인구']].sum()
    
    # 고령화율(%) 계산 및 소수점 둘째 자리 정리
    sigungu_df['고령화율'] = (sigungu_df['고령인구'] / sigungu_df['전체인구']) * 100
    sigungu_df['고령화율'] = sigungu_df['고령화율'].round(2)
    
    # B. 지도 경계 GeoJSON 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()
    
    return sigungu_df, geojson_data, latest_year

# 데이터 로딩 실행
with st.spinner("데이터와 지도 경계를 불러오는 중입니다..."):
    sigungu_df, geojson_data, latest_year = load_data()

st.write(f"**기준 연도:** {latest_year}년")

# 3. 고령화율 5단계 범주화 (지정한 경계값: 19%, 23%, 28%, 38%)
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

sigungu_df['고령화율_구간'] = pd.cut(
    sigungu_df['고령화율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 4. plotly 시각화 (단계구분도)
# 단계별 옅은 색 ~ 진한 색 컬러 맵 지정
color_discrete_map = {
    '19% 미만': '#edf8fb',
    '19% 이상 ~ 23% 미만': '#b2e2e2',
    '23% 이상 ~ 28% 미만': '#66c2a4',
    '28% 이상 ~ 38% 미만': '#2ca25f',
    '38% 이상': '#006d2c'
}

fig = px.choropleth_mapbox(
    sigungu_df,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 시군구 코드 (5자리)
    featureidkey='properties.코드',    # GeoJSON의 5자리 코드 속성
    color='고령화율_구간',             # 색상을 구분할 5단계 구간
    color_discrete_map=color_discrete_map,
    category_orders={'고령화율_구간': labels}, # 범례 순서 정렬
    hover_name='시군구',
    hover_data={
        'sigungu_code': False,
        '시도': True,
        '고령화율': ':.2f'
    },
    mapbox_style="white-bg",           # 지도 배경 타일 제거 (경계선만 표시)
    center={"lat": 35.8, "lon": 127.8},# 대한민국 중심 좌표 설정
    zoom=6.2                          # 기본 확대 정도
)

# 지도 스타일 및 레이아웃 세부 조절
fig.update_traces(marker_line_width=0.5, marker_line_color="gray")
fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    height=650,
    legend_title_text='고령화율 구간',
    legend=dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 5. 지도 하단 상위 10개 및 하위 10개 표 출력 (나란히 배치)
st.subheader("📊 시군구 고령화율 순위")

col1, col2 = st.columns(2)

# 고령화율 상위 10개 (높은 곳)
top10 = sigungu_df.sort_values(by='고령화율', ascending=False).head(10).reset_index(drop=True)
top10_display = top10[['시도', '시군구', '고령화율']].rename(columns={'고령화율': '고령화율 (%)'})

# 고령화율 하위 10개 (낮은 곳)
bottom10 = sigungu_df.sort_values(by='고령화율', ascending=True).head(10).reset_index(drop=True)
bottom10_display = bottom10[['시도', '시군구', '고령화율']].rename(columns={'고령화율': '고령화율 (%)'})

with col1:
    st.markdown("### 🔴 고령화율 가장 높은 곳 (Top 10)")
    st.dataframe(top10_display, use_container_width=True)

with col2:
    st.markdown("### 🔵 고령화율 가장 낮은 곳 (Top 10)")
    st.dataframe(bottom10_display, use_container_width=True)
