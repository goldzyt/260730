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

# 2. 데이터 불러오기 (캐싱을 적용하여 속도 최적화)
@st.cache_data
def load_data():
    # 인구 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # GeoJSON 지도 경계 데이터 URL
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    
    # 1) GeoJSON 다운로드
    geojson_data = requests.get(geojson_url).json()
    
    # 2) CSV 읽기 ('코드' 열을 문자열로 다루기 위해 dtype 지정)
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 코드가 10자리 미만일 경우를 대비해 10자리 문자열로 맞춤 (앞에 0 채우기)
    df['코드'] = df['코드'].str.zfill(10)
    
    # 시군구 코드 추출 (앞 5자리)
    df['sigungu_code'] = df['코드'].str[:5]
    
    # 가장 최신 연도 추출
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 3) 65세 이상 및 전체 인구 집계 준비
    # '계_'로 시작하고 숫자가 들어간 열 중에서 65세 이상인 열 추출
    total_pop_col = '계_총인구' if '계_총인구' in df.columns else None
    
    # age_cols: '계_65세'부터 '계_100세 이상'까지 관련 열 수집
    age_cols = []
    total_cols = []
    
    for col in df.columns:
        if col.startswith('계_'):
            total_cols.append(col)
            # 숫자 추출 (예: '계_65세' -> 65)
            age_str = col.replace('계_', '').replace('세 이상', '').replace('세', '')
            if age_str.isdigit():
                age = int(age_str)
                if age >= 65:
                    age_cols.append(col)
            elif col == '계_100세 이상':
                age_cols.append(col)

    # 4) 시군구 단위(5자리 코드)로 인구 합산
    # '계_총인구' 열이 없다면 전체 '계_' 열을 모두 더함
    if '계_전체' in df.columns:
        df_latest['전체인구'] = df_latest['계_전체']
    else:
        # 모든 계_XX세 열 합산
        df_latest['전체인구'] = df_latest[total_cols].sum(axis=1)
        
    df_latest['고령인구'] = df_latest[age_cols].sum(axis=1)
    
    # 시군구 코드별로 그룹화 (시도, 시군구 이름도 함께 유지)
    grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        '전체인구': 'sum',
        '고령인구': 'sum'
    }).reset_index()
    
    # 고령화율 계산 (%)
    grouped['고령화율'] = (grouped['고령인구'] / grouped['전체인구']) * 100
    grouped['고령화율'] = grouped['고령화율'].round(2)
    
    return grouped, geojson_data, latest_year

# 데이터 로딩 실행
with st.spinner("데이터를 불러오는 중입니다..."):
    df_sigungu, geojson_data, latest_year = load_data()

st.caption(f"기준 연도: **{latest_year}년**")

# 3. 5단계 범례 구간 나누기 (Cut)
# 구간 기준: 19% 미만, 19~23%, 23~28%, 28~38%, 38% 이상
bins = [-1, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_sigungu['고령화율_구간'] = pd.cut(
    df_sigungu['고령화율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 4. 분홍색 계열 5단계 단색 컬러맵 설정 (연한 분홍 -> 진한 분홍)
color_discrete_map = {
    '19% 미만': '#FDE0EB',
    '19% 이상 ~ 23% 미만': '#F9A8D4',
    '23% 이상 ~ 28% 미만': '#F472B6',
    '28% 이상 ~ 38% 미만': '#EC4899',
    '38% 이상': '#9D174D'
}

# 5. Plotly 지도 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',           # df의 시군구 코드
    featureidkey='properties.코드',     # GeoJSON의 5자리 코드 속성
    color='고령화율_구간',              # 범례로 사용할 5단계 구간 열
    color_discrete_map=color_discrete_map,
    category_orders={'고령화율_구간': labels}, # 범례 순서 고정
    hover_name='시군구',                # 마우스 오버 시 상단에 표시될 이름
    hover_data={
        'sigungu_code': False,
        '고령화율_구간': False,
        '시도': True,
        '고령화율': ':.2f'             # 소수점 2자리까지 %로 표현
    },
    labels={
        '시도': '시도명',
        '고령화율': '고령화율(%)',
        '고령화율_구간': '고령화 비율 구간'
    },
    center={"lat": 35.9, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.2,
    mapbox_style="white-bg"             # 타일 없이 흰 배경 유지
)

# 지도 레이아웃 및 경계선 설정
fig.update_traces(
    marker_line_width=0.5,
    marker_line_color="#666666"         # 시군구 경계선 색상 (옅은 회색)
)

fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    height=650,
    legend_title_text='고령화율 구간',
    legend=dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255, 255, 255, 0.8)" # 범례 배경 살짝 투명하게
    )
)

# 스트림릿에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 6. 하단 상위 10개 / 하위 10개 표 나란히 배치
st.subheader("📊 고령화율 상위 및 하위 지역 Top 10")

col1, col2 = st.columns(2)

# 고령화율 높은 순 정렬
top10 = df_sigungu.sort_values('고령화율', ascending=False).head(10)[['시도', '시군구', '고령화율']].reset_index(drop=True)
top10.index = top10.index + 1  # 순위 1부터 시작

# 고령화율 낮은 순 정렬
bottom10 = df_sigungu.sort_values('고령화율', ascending=True).head(10)[['시도', '시군구', '고령화율']].reset_index(drop=True)
bottom10.index = bottom10.index + 1

with col1:
    st.markdown("##### 🔴 고령화율이 높은 지역 Top 10")
    st.dataframe(
        top10.style.format({'고령화율': '{:.2f}%'}),
        use_container_width=True
    )

with col2:
    st.markdown("##### 🔵 고령화율이 낮은 지역 Top 10")
    st.dataframe(
        bottom10.style.format({'고령화율': '{:.2f}%'}),
        use_container_width=True
    )
