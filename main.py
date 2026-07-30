import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    layout="wide"
)

st.title("🗺️ 전국 시군구 고령화 지도")
st.markdown("시군구별 65세 이상 인구 비율(고령화율)을 5단계로 나타낸 지도입니다.")

# 2. 데이터 불러오기 (Streamlit 캐싱을 적용하여 실행 속도 최적화)
@st.cache_data
def load_data():
    # 인구 데이터 및 GeoJSON 지도 경계 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    
    # 1) GeoJSON 지도 데이터 다운로드
    geojson_data = requests.get(geojson_url).json()
    
    # 2) CSV 파일 읽기 ('코드' 열은 숫자가 아닌 10자리 문자열로 지정)
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 혹시 모를 짧은 코드를 대비해 10자리 문자열로 맞춤 (앞에 0 채우기)
    df['코드'] = df['코드'].str.zfill(10)
    
    # 시군구 코드 추출 (행정동 코드 앞 5자리)
    df['sigungu_code'] = df['코드'].str[:5]
    
    # 데이터 내 가장 최신 연도 자동 선택
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 3) 65세 이상 인구 및 전체 인구 집계 준비
    # '계_'로 시작하는 열 중 성별 합산 열들을 찾습니다.
    total_cols = [col for col in df.columns if col.startswith('계_')]
    
    # 65세 이상에 해당하는 열만 선별합니다.
    senior_cols = []
    for col in total_cols:
        # '계_100세 이상' 처리
        if col == '계_100세 이상':
            senior_cols.append(col)
            continue
        
        # '계_0세' ~ '계_99세' 형태에서 숫자만 추출
        age_str = col.replace('계_', '').replace('세', '')
        if age_str.isdigit():
            if int(age_str) >= 65:
                senior_cols.append(col)
                
    # 읍면동별 전체 인구 및 65세 이상 고령 인구 계산
    df_latest['전체인구'] = df_latest[total_cols].sum(axis=1)
    df_latest['고령인구'] = df_latest[senior_cols].sum(axis=1)
    
    # 4) 시군구 단위(5자리 코드)로 인구 합산 (시도, 시군구 이름도 함께 보존)
    grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        '전체인구': 'sum',
        '고령인구': 'sum'
    }).reset_index()
    
    # 고령화율(%) 계산 및 소수점 2자리 반올림
    grouped['고령화율'] = (grouped['고령인구'] / grouped['전체인구']) * 100
    grouped['고령화율'] = grouped['고령화율'].round(2)
    
    return grouped, geojson_data, latest_year

# 데이터 로딩 실행
with st.spinner("최신 인구 데이터와 지도 경계를 불러오는 중입니다..."):
    df_sigungu, geojson_data, latest_year = load_data()

st.caption(f"📅 기준 연도: **{latest_year}년**")

# 3. 고령화율 5단계 구간 나누기 (Cut)
# 구간 경계값: 19% 미만, 19~23%, 23~28%, 28~38%, 38% 이상
bins = [-1, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_sigungu['고령화율_구간'] = pd.cut(
    df_sigungu['고령화율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 4. 연파랑/구름 느낌의 5단계 그라데이션 색상 설정 (옅은 맑은 하늘색 -> 진한 바다/구름 그림자색)
color_discrete_map = {
    '19% 미만': '#E0F2FE',            # 매우 옅은 파스텔 하늘색 (구름 느낌)
    '19% 이상 ~ 23% 미만': '#BAE6FD',  # 부드러운 연파랑
    '23% 이상 ~ 28% 미만': '#7DD3FC',  # 선명한 하늘색
    '28% 이상 ~ 38% 미만': '#38BDF8',  # 또렷한 파랑
    '38% 이상': '#0284C7'             # 짙은 딥블루
}

# 5. Plotly 지도 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',           # df의 5자리 시군구 코드
    featureidkey='properties.코드',     # GeoJSON 내부의 5자리 코드 속성
    color='고령화율_구간',              # 범례로 사용할 5단계 구간 열
    color_discrete_map=color_discrete_map,
    category_orders={'고령화율_구간': labels}, # 범례 순서 고정
    hover_name='시군구',                # 마우스 올려놓았을 때 상단 굵은 글씨
    hover_data={
        'sigungu_code': False,          # 코드는 마우스 오버 창에서 숨김
        '고령화율_구간': False,          # 구간 명칭 숨김
        '시도': True,                   # 시도 이름 표시
        '고령화율': ':.2f'             # 고령화율(%) 표시
    },
    labels={
        '시도': '시도명',
        '고령화율': '고령화율(%)',
        '고령화율_구간': '고령화 비율 구간'
    },
    center={"lat": 35.9, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.3,                           # 초기 확대/축소 비율
    mapbox_style="white-bg"             # 배경 지도 타일 없이 흰 바탕으로 설정
)

# 지도 세부 레이아웃 및 경계선 디자인 설정
fig.update_traces(
    marker_line_width=0.6,
    marker_line_color="#94A3B8"         # 경계선을 옅은 슬레이트 회색으로 깔끔하게 처리
)

fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    height=680,
    legend_title_text='고령화율 구간',
    legend=dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255, 255, 255, 0.85)", # 범례 배경을 은은한 반투명 흰색으로 처리
        bordercolor="#E2E8F0",
        borderwidth=1
    )
)

# 스트림릿 화면에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 6. 하단 상위 10개 / 하위 10개 표 나란히 배치
st.subheader("📊 고령화율 상위 및 하위 지역 Top 10")

col1, col2 = st.columns(2)

# 고령화율 높은 순 정렬 (상위 10개)
top10 = df_sigungu.sort_values('고령화율', ascending=False).head(10)[['시도', '시군구', '고령화율']].reset_index(drop=True)
top10.index = top10.index + 1  # 순위를 1번부터 시작하도록 설정

# 고령화율 낮은 순 정렬 (하위 10개)
bottom10 = df_sigungu.sort_values('고령화율', ascending=True).head(10)[['시도', '시군구', '고령화율']].reset_index(drop=True)
bottom10.index = bottom10.index + 1

with col1:
    st.markdown("##### 📈 고령화율이 가장 높은 지역 Top 10")
    st.dataframe(
        top10.style.format({'고령화율': '{:.2f}%'}),
        use_container_width=True
    )

with col2:
    st.markdown("##### 📉 고령화율이 가장 낮은 지역 Top 10")
    st.dataframe(
        bottom10.style.format({'고령화율': '{:.2f}%'}),
        use_container_width=True
    )
