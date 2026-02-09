import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import base64
import os
import platform
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import streamlit.elements.image as st_image
import matplotlib.pyplot as plt

# [패치 1] Streamlit 이미지 처리 호환성
if not hasattr(st_image, 'image_to_url'):
    def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None, allow_emoji=False):
        if isinstance(image, str): return image
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
        return ""
    st_image.image_to_url = custom_image_to_url

# [패치 2] 그래프 한글 폰트 (Windows)
if platform.system() == 'Windows':
    try:
        plt.rc('font', family='Malgun Gothic')
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

# --- DB 매니저 ---
class DBManager:
    DB_NAME = 'baseball_log.db'

    @staticmethod
    def init_db():
        with sqlite3.connect(DBManager.DB_NAME) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
            # 기존 테이블 유지 (컬럼이 이미 존재한다고 가정)
            c.execute('''CREATE TABLE IF NOT EXISTS training_logs
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, duration INTEGER, location TEXT, 
                          intensity TEXT, satisfaction TEXT, gudan_content TEXT, p_swing INTEGER, p_live INTEGER, 
                          p_defense INTEGER, p_pitching INTEGER, p_running INTEGER, p_hanging INTEGER, p_etc TEXT, 
                          coach_feedback TEXT, self_good TEXT, self_bad TEXT, promise TEXT, memo TEXT, 
                          log_type TEXT, tactical_image TEXT)''')
            c.execute("SELECT * FROM users WHERE username = 'test'")
            if not c.fetchone():
                c.execute("INSERT INTO users VALUES ('test', '1234')")

    @staticmethod
    def run_query(query, params=(), fetch=False, return_df=False):
        with sqlite3.connect(DBManager.DB_NAME) as conn:
            if return_df:
                return pd.read_sql(query, conn, params=params)
            c = conn.cursor()
            c.execute(query, params)
            if fetch:
                return c.fetchall()
            conn.commit()

    @staticmethod
    def get_log(username, date_str, log_type='daily'):
        with sqlite3.connect(DBManager.DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM training_logs WHERE username=? AND date=? AND log_type=?", (username, date_str, log_type))
            return c.fetchone()

# --- 페이지 설정 및 초기화 ---
st.set_page_config(page_title="야구 훈련 일지", layout="wide")
DBManager.init_db()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'is_admin' not in st.session_state: st.session_state.is_admin = False

# --- UI: 로그인 ---
def login_page():
    _, c_logo, c_text, _ = st.columns([1, 1, 5, 1], vertical_alignment="center")
    with c_logo:
        if os.path.exists("logo.png"): st.image("logo.png", width=150)
        else: st.header("⚾")
    with c_text:
        st.markdown("## 수지리틀야구단 선수 훈련 일지")
    
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("로그인")
        username = st.text_input("이름 (ID)")
        password = st.text_input("비밀번호", type="password")
        if st.button("로그인", use_container_width=True):
            user = DBManager.run_query("SELECT password FROM users WHERE username = ?", (username,), fetch=True)
            if user and user[0][0] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("정보가 일치하지 않습니다.")
        
        st.divider()
        with st.expander("관리자 접속"):
            if st.button("관리자 로그인") and st.text_input("PIN", type="password") == "98770491":
                st.session_state.logged_in = True; st.session_state.username = "관리자"; st.session_state.is_admin = True
                st.rerun()

# --- UI: 일일 훈련 기록 ---
def render_daily_log(username, date_str, data):
    with st.form("daily_log_form"):
        st.markdown(f"### Training Journal : {date_str}")
        st.markdown("---")
        get_val = lambda k, d: data[k] if data else d

        c1, c2 = st.columns([1, 5])
        c1.markdown("**훈련 시간**"); duration = c2.number_input("분", value=get_val('duration', 0), step=10, label_visibility="collapsed")
        
        c3, c4 = st.columns([1, 5])
        c3.markdown("**훈련 장소**")
        # [수정] "연습 경기" 항목 추가
        loc_opts = ["실외 구장", "실내 구장", "집", "연습 경기", "기타"] 
        loc_idx = loc_opts.index(data['location']) if data and data['location'] in loc_opts else 0
        location = c4.radio("장소", loc_opts, index=loc_idx, horizontal=True, label_visibility="collapsed")
        
        lvl_opts = ["최상", "상", "중", "하", "최하"]
        c5, c6 = st.columns([1, 5])
        c5.markdown("**훈련 강도**"); intensity = c6.radio("강도", lvl_opts, index=lvl_opts.index(get_val('intensity', '중')), horizontal=True, label_visibility="collapsed")
        
        c7, c8 = st.columns([1, 5])
        c7.markdown("**훈련 만족도**"); satisfaction = c8.radio("만족도", lvl_opts, index=lvl_opts.index(get_val('satisfaction', '중')), horizontal=True, label_visibility="collapsed")

        st.markdown("---")
        st.markdown("#### 훈련 내용")
        col_content_1, col_content_2 = st.columns(2)
        with col_content_2:
            st.info("💪 개인 훈련 (Personal Training)")
            def p_input(lbl, key, step=10):
                pc1, pc2 = st.columns([2, 1])
                pc1.write(f"• {lbl}")
                return pc2.number_input(lbl, value=get_val(key, 0), step=step, label_visibility="collapsed")
            
            p_swing = p_input("연습 스윙 (회)", 'p_swing')
            p_live = p_input("라이브 배팅 (분)", 'p_live')
            p_defense = p_input("수비 훈련 (분)", 'p_defense')
            p_pitching = p_input("피칭 훈련 (개수)", 'p_pitching')
            p_running = p_input("런닝 훈련 (분)", 'p_running')
            p_hanging = p_input("철봉 매달리기 (분)", 'p_hanging', step=1)
            
            pc_etc1, pc_etc2 = st.columns([1, 2])
            pc_etc1.write("• 기타 훈련"); p_etc = pc_etc2.text_input("기타", value=get_val('p_etc', ""), label_visibility="collapsed")

        with col_content_1:
            st.success("⚾ 구단 훈련 (Team Training)")
            gudan_content = st.text_area("구단 훈련 내용", value=get_val('gudan_content', ""), height=380, label_visibility="collapsed")

        st.markdown("---")
        col_feed_1, col_feed_2 = st.columns(2)
        with col_feed_2:
            st.error("🧠 나의 분석")
            st.caption("잘된 부분"); self_good = st.text_area("good", value=get_val('self_good', ""), height=80, label_visibility="collapsed")
            st.caption("부족한 부분"); self_bad = st.text_area("bad", value=get_val('self_bad', ""), height=80, label_visibility="collapsed")
        with col_feed_1:
            st.warning("🗣️ Coach's Feedback")
            coach_feedback = st.text_area("coach", value=get_val('coach_feedback', ""), height=220, label_visibility="collapsed")

        st.markdown("---")
        promise = st.text_area("다짐", value=get_val('promise', ""), height=70, placeholder="오늘의 다짐", label_visibility="collapsed")
        memo = st.text_area("메모", value=get_val('memo', ""), height=70, placeholder="추가 메모", label_visibility="collapsed")
        
        if st.form_submit_button("💾 금일 훈련 저장하기", type="primary"):
            query = """INSERT OR REPLACE INTO training_logs 
                       (id, username, date, duration, location, intensity, satisfaction, gudan_content, 
                        p_swing, p_live, p_defense, p_pitching, p_running, p_hanging, p_etc, 
                        coach_feedback, self_good, self_bad, promise, memo, log_type)
                       VALUES ((SELECT id FROM training_logs WHERE username=? AND date=? AND log_type='daily'),
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'daily')"""
            params = (username, date_str, username, date_str, duration, location, intensity, satisfaction, gudan_content,
                      p_swing, p_live, p_defense, p_pitching, p_running, p_hanging, p_etc,
                      coach_feedback, self_good, self_bad, promise, memo)
            DBManager.run_query(query, params)
            st.success(f"✅ {date_str} 훈련 기록이 저장되었습니다!")

# --- UI: 전술 훈련 (숨김) ---
def render_tactical_log(username, date_str, data):
    st.markdown(f"### Tactical Training : {date_str}")
    # (내용 생략 - 필요 시 이전 코드 참조)

# --- UI: 대시보드 (개선됨) ---
def render_dashboard(username, current_date):
    # 상단 레이아웃: 제목과 콤보박스 배치
    col_header_1, col_header_2 = st.columns([3, 1], vertical_alignment="center")
    with col_header_1:
        st.header("📊 Dashboard")
    
    # 훈련 항목 매핑 (표시 이름 : (DB컬럼명, 단위))
    metrics_map = {
        "총 훈련 시간": ("duration", "분"),
        "연습 스윙": ("p_swing", "회"),
        "라이브 배팅": ("p_live", "분"),
        "수비 훈련": ("p_defense", "분"),
        "피칭 훈련": ("p_pitching", "개"),
        "런닝 훈련": ("p_running", "분"),
        "철봉 매달리기": ("p_hanging", "분")
    }
    
    with col_header_2:
        selected_metric_label = st.selectbox("분석 항목 선택", list(metrics_map.keys()))
        target_col, unit = metrics_map[selected_metric_label]

    df = DBManager.run_query(f"SELECT * FROM training_logs WHERE username='{username}' AND log_type='daily'", return_df=True)
    
    if df.empty:
        st.info("아직 훈련 데이터가 없습니다.")
        return

    # 데이터 전처리: 날짜 변환 및 결측치 0 처리
    df['date'] = pd.to_datetime(df['date'])
    df[target_col] = pd.to_numeric(df[target_col], errors='coerce').fillna(0)
    today = pd.Timestamp(current_date)
    
    # 공통 그래프 그리기 함수
    def plot_metric(title, sub_df, x_idx, x_fmt=None, bar_col='skyblue', x_labels_override=None):
        st.subheader(title)
        
        # 데이터가 비어있을 경우 처리
        if sub_df.empty:
            st.warning("기간 내 데이터가 없습니다.")
            st.divider()
            return

        # 그룹화 기준 (월간/주간은 date, 연간은 month)
        if 'month' in sub_df.columns and len(x_idx) == 12: # 연간 데이터인 경우
            grouped = sub_df.groupby('month')[target_col].sum()
        else:
            grouped = sub_df.groupby('date')[target_col].sum()
            
        final = grouped.reindex(x_idx, fill_value=0)
        
        total = int(final.sum())
        # 0보다 큰 값이 있는 날짜만 카운트하여 평균 계산
        active_days = sub_df[sub_df[target_col] > 0].shape[0]
        avg = int(total / active_days) if active_days > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.metric(f"기간 총 {selected_metric_label}", f"{total} {unit}")
        c2.metric(f"일 평균 {selected_metric_label}", f"{avg} {unit}")
        
        fig, ax = plt.subplots(figsize=(10, 4))
        
        # X축 라벨 설정
        if x_labels_override:
            plot_labels = x_labels_override
        elif x_fmt:
            plot_labels = final.index.strftime(x_fmt)
        else:
            plot_labels = final.index

        ax.bar(plot_labels, final.values, color=bar_col)
        ax.set_ylabel(unit)
        
        # 값이 있는 막대 위에 숫자 표시
        for i, v in enumerate(final.values):
            if v > 0:
                ax.text(i, v, str(int(v)), ha='center', va='bottom', fontsize=8)

        st.pyplot(fig)
        st.divider()

    # 1. 주간 데이터
    start_w = today - timedelta(days=today.weekday())
    end_w = start_w + timedelta(days=6)
    week_df = df[(df['date'] >= start_w) & (df['date'] <= end_w)].copy()
    plot_metric(f"1. 주간 {selected_metric_label} ({start_w.strftime('%m/%d')} ~ {end_w.strftime('%m/%d')})", 
                week_df, pd.date_range(start_w, periods=7), '%a', 'skyblue')

    # 2. 월간 데이터
    start_m = today.replace(day=1)
    next_m = (start_m + timedelta(days=32)).replace(day=1)
    month_df = df[(df['date'] >= start_m) & (df['date'] < next_m)].copy()
    plot_metric(f"2. 월간 {selected_metric_label} ({start_m.strftime('%Y-%m')})", 
                month_df, pd.date_range(start_m, next_m - timedelta(days=1)), '%d', 'lightgreen')

    # 3. 연간 데이터 (수정됨: 1월~12월 표시)
    year_df = df[df['date'].dt.year == today.year].copy()
    year_df['month'] = year_df['date'].dt.month
    
    # 1~12월 인덱스 생성 및 라벨링
    month_indices = range(1, 13)
    month_labels = [f"{i}월" for i in range(1, 13)]
    
    plot_metric(f"3. 연간 {selected_metric_label} ({today.year}년)", 
                year_df, month_indices, None, 'salmon', x_labels_override=month_labels)

# --- 관리자 페이지 ---
def admin_page():
    st.title("🛡️ 관리자 페이지")
    if st.sidebar.button("관리자 로그아웃"):
        st.session_state.logged_in = False; st.session_state.is_admin = False; st.rerun()
    
    t1, t2 = st.tabs(["👥 사용자 관리", "📥 데이터 확인"])
    with t1:
        st.dataframe(DBManager.run_query("SELECT username, password FROM users", return_df=True))
        c1, c2 = st.columns(2)
        new_u = c1.text_input("새 유저"); new_p = c1.text_input("새 비번", type="password")
        if c1.button("추가") and new_u and new_p:
            try: DBManager.run_query("INSERT INTO users VALUES (?, ?)", (new_u, new_p)); st.rerun()
            except: st.error("중복 ID")
        
        del_u = c2.selectbox("삭제 유저", DBManager.run_query("SELECT username FROM users", fetch=True))
        if c2.button("삭제") and del_u:
            if del_u[0] != "관리자": DBManager.run_query("DELETE FROM users WHERE username=?", (del_u[0],)); st.rerun()
            else: st.error("관리자 삭제 불가")

    with t2:
        df = DBManager.run_query("SELECT * FROM training_logs", return_df=True)
        st.dataframe(df)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
        st.download_button("엑셀 다운로드", buffer, "log.xls")

# --- 메인 실행 로직 ---
def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state.username} 선수")
    if 'current_date' not in st.session_state: st.session_state.current_date = datetime.now().date()
    st.session_state.current_date = st.sidebar.date_input("날짜 선택", st.session_state.current_date)
    date_str = st.session_state.current_date.strftime("%Y-%m-%d")

    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False; st.rerun()

    tab1, tab2 = st.tabs(["📝 일일 훈련 일지", "📊 Dashboard"])
    
    with tab1:
        data = DBManager.get_log(st.session_state.username, date_str)
        render_daily_log(st.session_state.username, date_str, data)
    
    # [숨김 처리된 전술 탭]
    if False:
        t_data = DBManager.get_log(st.session_state.username, date_str, 'tactical')
        render_tactical_log(st.session_state.username, date_str, t_data)

    with tab2:
        render_dashboard(st.session_state.username, st.session_state.current_date)

if __name__ == "__main__":
    if not st.session_state.logged_in: login_page()
    elif st.session_state.is_admin: admin_page()
    else: main_app()