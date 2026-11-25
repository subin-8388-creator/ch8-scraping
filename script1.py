import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd


# 1단계: 웹페이지 HTML 가져오기 함수
def fetch_html(url):
    # 위키백과 차단을 막기 위해 수업 실습용임을 밝히는 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (University Python Class Practice; Contact: student@univ.ac.kr)"
    }
    try:
        # 10초 안에 응답이 없으면 시간 초과 처리
        response = requests.get(url, headers=headers, timeout=10)
        # 404, 500 등 HTTP 상태 코드 에러가 발생하면 예외를 일으킴
        response.raise_for_status()
        return response.text, None

    except requests.exceptions.Timeout:
        return None, "시간 초과 오류: 서버 응답이 너무 오래 걸립니다."
    except requests.exceptions.ConnectionError:
        return None, "연결 실패 오류: 인터넷 연결이나 주소를 확인해 주세요."
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP 오류가 발생했습니다: {e}"
    except Exception as e:
        return None, f"알 수 없는 오류가 발생했습니다: {e}"


# 2단계: HTML에서 원하는 표를 찾아 DataFrame으로 변환하는 함수
def parse_table(html):
    soup = BeautifulSoup(html, "html.parser")

    # 각주 번호([1], [2] 등)에 해당하는 모든 sup 태그를 미리 제거
    for sup in soup.find_all("sup"):
        sup.decompose()

    # class가 wikitable인 모든 표 찾기
    tables = soup.find_all("table", class_="wikitable")
    target_table = None

    for table in tables:
        first_row = table.find("tr")
        if first_row:
            # 첫 줄의 제목 칸(th) 텍스트들을 리스트로 모음
            headers = []
            for th in first_row.find_all("th"):
                headers.append(th.get_text(strip=True))

            # 첫 줄에 '관객수'와 '감독'이 모두 들어있는 첫 번째 표 선택
            header_text = " ".join(headers)
            if "관객수" in header_text and "감독" in header_text:
                target_table = table
                break

    # 조건에 맞는 표를 찾지 못한 경우
    if target_table is None:
        return None, "표 찾기 실패: '관객수'와 '감독'이 포함된 표를 찾을 수 없습니다."

    # 표의 모든 줄(tr) 가져오기
    rows = target_table.find_all("tr")

    # 첫 번째 줄(rows[0])에서 열 이름(컬럼명) 추출
    columns = []
    for th in rows[0].find_all("th"):
        columns.append(th.get_text(strip=True))

    # 두 번째 줄(rows[1:])부터 영화 데이터(td) 추출
    data = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) > 0:
            row_data = []
            for cell in cells:
                row_data.append(cell.get_text(strip=True))
            # 열 개수와 데이터 칸 개수가 일치하는 줄만 추가 (병합된 행 오류 방지)
            if len(row_data) == len(columns):
                data.append(row_data)

    df = pd.DataFrame(data, columns=columns)
    return df, None


# 3단계: 수집한 표 데이터를 분석하기 좋게 다듬는(전처리) 함수
def clean_data(df):
    # 컬럼명에 띄어쓰기나 괄호가 섞여 있을 수 있으므로 키워드로 실제 컬럼명 찾기
    title_col = ""
    audience_col = ""
    date_col = ""

    for col in df.columns:
        if "제목" in col or "작품" in col:
            title_col = col
        elif "관객" in col:
            audience_col = col
        elif "개봉" in col:
            date_col = col

    # 1) 제목에서 겹낫표(《, 》) 제거
    df["영화제목"] = df[title_col].str.replace("《", "").str.replace("》", "").str.strip()

    # 2) 관객수에서 숫자만 남기고 정수(int)로 변환
    clean_audience = []
    for val in df[audience_col]:
        digits = ""
        for ch in str(val):
            if ch.isdigit():  # 글자가 숫자인 경우에만 이어 붙임
                digits += ch
        if digits != "":
            clean_audience.append(int(digits))
        else:
            clean_audience.append(0)
    df["관객수_숫자"] = clean_audience

    # 3) 개봉일(예: 2014-07-30 또는 2014년 7월 30일)에서 개봉연도와 개봉월 분리
    years = []
    months = []
    for val in df[date_col]:
        text = str(val).strip()
        # 하이픈(-), 점(.), 한글(년, 월) 구분자를 모두 하이픈(-)으로 통일
        text = text.replace(".", "-").replace("년", "-").replace("월", "-")
        parts = text.split("-")

        # 앞의 두 조각이 숫자(연도, 월)인지 확인 후 추출
        if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            year_part = parts[0].strip()
            month_part = parts[1].strip()
            years.append(year_part + "년")
            months.append(int(month_part))
        else:
            years.append("알수없음")
            months.append(0)

    df["개봉연도"] = years
    df["개봉월"] = months

    # 관객수 기준 내림차순 정렬 (1위부터 순서대로)
    df = df.sort_values(by="관객수_숫자", ascending=False).reset_index(drop=True)
    return df


# 4단계: 화면에 지표, 표, 차트를 그리는 함수
def show_dashboard(df):
    st.subheader("핵심 흥행 지표")

    # 3개의 칸으로 나누어 핵심 지표 표시
    col1, col2, col3 = st.columns(3)

    total_movies = len(df)
    top_movie = df.loc[0, "영화제목"]
    top_audience = df.loc[0, "관객수_숫자"]

    col1.metric("천만 영화 수", f"{total_movies}편")
    col2.metric("역대 1위 영화", top_movie)
    col3.metric("역대 1위 관객수", f"{top_audience:,}명")

    st.divider()

    # 전체 데이터 표 출력
    st.subheader("천만 관객 한국 영화 목록")
    st.dataframe(df, use_container_width=True)

    st.divider()

    # 차트 1: 관객수 상위 10편 가로 막대 차트
    st.subheader("관객수 상위 10편")
    top10_df = df.head(10).set_index("영화제목")
    st.bar_chart(top10_df["관객수_숫자"], horizontal=True)

    # 차트 2: 개봉연도별 편수 막대 차트
    st.subheader("개봉연도별 천만 영화 편수")
    # 연도별로 몇 편인지 세고, 연도순(오름차순)으로 정렬
    year_counts = df["개봉연도"].value_counts().sort_index()
    st.bar_chart(year_counts)


# 메인 실행 함수 (앱의 전체 흐름 제어)
def main():
    st.title("대한민국 천만 관객 영화 분석기")
    st.write("위키백과 데이터를 수집하여 천만 관객 영화 기록을 분석합니다.")

    # 기본 URL 설정 및 텍스트 입력창 생성
    default_url = "https://ko.wikipedia.org/wiki/대한민국의_영화_흥행_기록"
    url = st.text_input("위키백과 문서 주소를 입력하세요", value=default_url)

    # 버튼을 눌렀을 때만 수집 및 분석 실행
    if st.button("데이터 수집 및 분석 시작"):
        with st.spinner("웹페이지에서 데이터를 가져오는 중입니다..."):
            html, fetch_error = fetch_html(url)

        # 1단계 에러 확인
        if fetch_error:
            st.error(fetch_error)
            return

        # 2단계 표 추출 및 에러 확인
        raw_df, parse_error = parse_table(html)
        if parse_error:
            st.error(parse_error)
            return

        # 3단계 데이터 정제
        cleaned_df = clean_data(raw_df)

        # 4단계 결과 화면 출력
        st.success("데이터 수집과 정제가 완료되었습니다!")
        show_dashboard(cleaned_df)


# 파이썬 파일이 직접 실행될 때 main() 함수 호출
if __name__ == "__main__":
    main()