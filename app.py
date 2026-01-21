import streamlit as st
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
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# [패치] Streamlit 이미지 호환성
if not hasattr(st_image, 'image_to_url'):
    def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None, allow_emoji=False):
        if isinstance(image, str): return image
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
        return ""
    st_image.image_to_url = custom_image_to_url

# [패치] 그래프 한글 폰트 (Windows 및 클라우드 호환)
if platform.system() == 'Windows':
    try:
        plt.rc('font', family='Malgun Gothic')
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
else:
    plt.rcParams['axes.unicode_minus'] = False

# --- 구글 시트 매니저 ---
class SheetManager:
    SHEET_NAME = 'baseball_log_db'

    @staticmethod
    def get_connection():
        # Streamlit Secrets에서 인증 정보 가져오기
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SheetManager.SHEET_NAME)

    @staticmethod
    def get_users():
        try:
            sh = SheetManager.get_connection()
            worksheet = sh.worksheet("users")
            return worksheet.get_all_records()
        except: return []

    @staticmethod
    def add_user(username, password):
        sh = SheetManager.get_connection()
        ws = sh.worksheet("users")
        # [수정 1] 비밀번호 '0' 시작 문제 해결 (RAW 옵션 사용)
        # 문자열로 강제 변환 후, 엑셀 자동 변환을 막기 위해 RAW 모드로 저장
        ws.append_row([str(username), str(password)], value_input_option='RAW')

    @staticmethod
    def delete_user(username):
        sh = SheetManager.get_connection()
        ws = sh.worksheet("users")
        cell = ws.find(username)
        if cell: ws.delete_rows(cell.row)

    @staticmethod
    def get_log(username, date_str, log_type='daily'):
        try:
            sh = SheetManager.get_connection()
            ws = sh.worksheet("training_logs")
            df = pd.DataFrame(ws.get_all_records())
            if df.empty: return None
            filtered = df[(df['username'] == username) & (df['date'] == date_str) & (df['log_type'] == log_type)]
            if not filtered.empty: return filtered.iloc[0].to_dict()
            return None
        except: return None

    @staticmethod
    def save_log(log_data):
        sh = SheetManager.get_connection()
        ws = sh.worksheet("training_logs")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        target_row_idx = None
        if not df.empty:
            mask = (df['username'] == log_data['username']) & (df['date'] == log_data['date']) & (df['log_type'] == log_data['log_type'])
            if mask.any():
                target_row_idx = df.index[mask][0] + 2

        row_values = [
            0, log_data.get('username'), log_data.get('date'), log_data.get('duration', 0),
            log_data.get('location', ''), log_data.get('intensity', ''), log_data.get('satisfaction', ''),
            log_data.get('gudan_content', ''), log_data.get('p_swing', 0), log_data.get('p_live', 0),
            log_data.get('p_defense', 0), log_data.get('p_pitching', 0), log_data.get('p_running', 0),
            log_data.get('p_hanging', 0), log_data.get('p_etc', ''), log_data.get('coach_feedback', ''),
            log_data.get('self_good', ''), log_data.get('self_bad', ''), log_data.get('promise', ''),
            log_data.get('memo', ''), log_data.get('log_type', 'daily'), log_data.get('tactical_image', '')
        ]

        if target_row_idx:
            ws.update(f"A{target_row_idx}:V{target_row_idx}", [row_values])
        else:
            ws.append_row(row_values)

    @staticmethod
    def get_all_logs(username=None):
        try:
            sh = SheetManager.get_connection()
            ws = sh.worksheet("training_logs")
            df = pd.DataFrame(ws.get_all_records())
            if df.empty: return pd.DataFrame()
            if username: return df[df['username'] == username]
            return df
        except: return pd.DataFrame()

# --- 페이지 설정 ---
st.set_page_config(page_title="야구 훈련 일지", layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'is_admin' not in st.session_state: st.session_state.is_admin = False

# --- 로그인 페이지 ---
def login_page():
    _, c_logo, c_text, _ = st.columns([1, 1, 5, 1], vertical_alignment="center")
    with c_logo:
        try: st.image("logo.png", width=150)
        except: st.header("⚾")
    with c_text:
        st.markdown("## 수지리틀야구단 선수 훈련 일지")
    
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("user_login_form"):
            st.subheader("로그인")
            username = st.text_input("이름 (ID)")
            password = st.text_input("비밀번호", type="password")
            
            if st.form_submit_button("로그인", use_container_width=True):
                users = SheetManager.get_users()
                valid = False
                for u in users:
                    if str(u['username']) == username and str(u['password']) == password:
                        valid = True
                        break
                
                if valid:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.is_admin = False
                    st.rerun()
                else:
                    st.error("정보가 일치하지 않습니다.")

        st.divider()
        with st.expander("관리자 접속"):
            with st.form("admin_login_form"):
                st.write("관리자 인증")
                pin = st.text_input("PIN 번호", type="password")
                if st.form_submit_button("관리자 로그인"):
                    if pin == "98770491":
                        st.session_state.logged_in = True
                        st.session_state.username = "관리자"
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("PIN 번호가 올바르지 않습니다.")

# --- 일일 훈련 기록 ---
def render_daily_log(username, date_str, data):
    with st.form("daily_log_form"):
        st.markdown(f"### Training Journal : {date_str}")
        st.markdown("---")
        if data is None: data = {}
        
        get_val = lambda k, d: int(d[k]) if k in d and d[k] != '' else 0
        get_str = lambda k, d: str(d[k]) if k in d else ""

        c1, c2 = st.columns([1, 5])
        c1.markdown("**훈련 시간**"); duration = c2.number_input("분", value=get_val('duration', data), step=10, label_visibility="collapsed")
        
        c3, c4 = st.columns([1, 5])
        c3.markdown("**훈련 장소**")
        loc_opts = ["실외 구장", "실내 구장", "집", "기타"]
        saved_loc = get_str('location', data)
        loc = c4.radio("장소", loc_opts, index=loc_opts.index(saved_loc) if saved_loc in loc_opts else 0, horizontal=True, label_visibility="collapsed")
        
        lvl_opts = ["최상", "상", "중", "하", "최하"]
        c5, c6 = st.columns([1, 5])
        c5.markdown("**훈련 강도**")
        saved_int = get_str('intensity', data)
        intensity = c6.radio("강도", lvl_opts, index=lvl_opts.index(saved_int) if saved_int in lvl_opts else 2, horizontal=True, label_visibility="collapsed")
        
        c7, c8 = st.columns([1, 5])
        c7.markdown("**훈련 만족도**")
        saved_sat = get_str('satisfaction', data)
        satisfaction = c8.radio("만족도", lvl_opts, index=lvl_opts.index(saved_sat) if saved_sat in lvl_opts else 2, horizontal=True, label_visibility="collapsed")

        st.markdown("---")
        st.markdown("#### 훈련 내용")
        col_content_1, col_content_2 = st.columns(2)
        with col_content_2:
            st.info("💪 개인 훈련 (Personal Training)")
            def p_input(lbl, key, step=10):
                pc1, pc2 = st.columns([2, 1])
                pc1.write(f"• {lbl}")
                return pc2.number_input(lbl, value=get_val(key, data), step=step, label_visibility="collapsed")
            
            p_swing = p_input("연습 스윙 (회)", 'p_swing')
            p_live = p_input("라이브 배팅 (분)", 'p_live')
            p_defense = p_input("수비 훈련 (분)", 'p_defense')
            p_pitching = p_input("피칭 훈련 (개수)", 'p_pitching')
            p_running = p_input("런닝 훈련 (분)", 'p_running')
            p_hanging = p_input("철봉 매달리기 (분)", 'p_hanging', step=1)
            
            pc_etc1, pc_etc2 = st.columns([1, 2])
            pc_etc1.write("• 기타 훈련"); p_etc = pc_etc2.text_input("기타", value=get_str('p_etc', data), label_visibility="collapsed")

        with col_content_1:
            st.success("⚾ 구단 훈련 (Team Training)")
            gudan_content = st.text_area("구단 훈련 내용", value=get_str('gudan_content', data), height=380, label_visibility="collapsed")

        st.markdown("---")
        col_feed_1, col_feed_2 = st.columns(2)
        with col_feed_2:
            # [수정 3] 이모지 변경: 🧠 -> ✏️ (연필)
            st.error("✏️ 나의 분석 (Self Feedback)")
            # [수정 2] 입력창 디자인 개선: caption 제거 및 placeholder 적용
            sg = st.text_area("good", value=get_str('self_good', data), height=80, placeholder="잘된 부분 (Good)", label_visibility="collapsed")
            sb = st.text_area("bad", value=get_str('self_bad', data), height=80, placeholder="부족한 부분 (Bad)", label_visibility="collapsed")
        with col_feed_1:
            # [수정 3] 이모지 변경: 🗣️ -> 📢 (호루라기/확성기)
            st.warning("📢 코치 피드백 (Coach's Feedback)")
            cfb = st.text_area("coach", value=get_str('coach_feedback', data), height=220, label_visibility="collapsed")

        st.markdown("---")
        promise = st.text_area("다짐", value=get_str('promise', data), height=70, placeholder="오늘의 다짐", label_visibility="collapsed")
        memo = st.text_area("메모", value=get_str('memo', data), height=70, placeholder="추가 메모", label_visibility="collapsed")
        
        if st.form_submit_button("💾 금일 훈련 저장하기", type="primary"):
            log_data = {
                'username': username, 'date': date_str, 'duration': duration, 'location': loc, 
                'intensity': intensity, 'satisfaction': satisfaction, 'gudan_content': gudan_content,
                'p_swing': p_swing, 'p_live': p_live, 'p_defense': p_defense, 'p_pitching': p_pitching,
                'p_running': p_running, 'p_hanging': p_hanging, 'p_etc': p_etc,
                'coach_feedback': cfb, 'self_good': sg, 'self_bad': sb,
                'promise': promise, 'memo': memo, 'log_type': 'daily'
            }
            try:
                SheetManager.save_log(log_data)
                st.success("✅ 저장되었습니다!")
            except Exception as e:
                st.error(f"오류: {e}")

# --- 대시보드 ---
def render_dashboard(username, current_date):
    col_h1, col_h2 = st.columns([3, 1], vertical_alignment="center")
    with col_h1: st.header("📊 Dashboard")
    
    metrics_map = {"총 훈련 시간":("duration","분"), "연습 스윙":("p_swing","회"), "라이브 배팅":("p_live","분"), 
                   "수비 훈련":("p_defense","분"), "피칭 훈련":("p_pitching","개"), "런닝":("p_running","분"), "철봉":("p_hanging","분")}
    with col_h2:
        sel = st.selectbox("항목 선택", list(metrics_map.keys()))
        target_col, unit = metrics_map[sel]

    df = SheetManager.get_all_logs(username)
    if not df.empty and 'log_type' in df.columns: df = df[df['log_type'] == 'daily']
    
    if df.empty:
        st.info("데이터가 없습니다.")
        return

    df['date'] = pd.to_datetime(df['date']); df[target_col] = pd.to_numeric(df[target_col], errors='coerce').fillna(0)
    today = pd.Timestamp(current_date)
    
    def plot_metric(title, sub_df, idx, fmt, clr, lbls=None):
        st.subheader(title)
        if sub_df.empty: st.caption("데이터 없음"); st.divider(); return
        grouped = sub_df.groupby('month')[target_col].sum() if 'month' in sub_df.columns else sub_df.groupby('date')[target_col].sum()
        final = grouped.reindex(idx, fill_value=0)
        
        tot = int(final.sum()); act = sub_df[sub_df[target_col]>0].shape[0]; avg = int(tot/act) if act>0 else 0
        c1, c2 = st.columns(2); c1.metric(f"총 {sel}", f"{tot} {unit}"); c2.metric("일 평균", f"{avg} {unit}")
        
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(lbls if lbls else (final.index.strftime(fmt) if fmt else final.index), final.values, color=clr)
        st.pyplot(fig); st.divider()

    s_w = today - timedelta(days=today.weekday())
    plot_metric("1. 주간", df[(df['date']>=s_w)&(df['date']<=s_w+timedelta(6))], pd.date_range(s_w, periods=7), '%a', 'skyblue')
    
    s_m = today.replace(day=1); n_m = (s_m+timedelta(32)).replace(day=1)
    plot_metric("2. 월간", df[(df['date']>=s_m)&(df['date']<n_m)], pd.date_range(s_m, n_m-timedelta(1)), '%d', 'lightgreen')
    
    y_df = df[df['date'].dt.year==today.year].copy(); y_df['month']=y_df['date'].dt.month
    plot_metric("3. 연간", y_df, range(1,13), None, 'salmon', [f"{i}월" for i in range(1,13)])

# --- 관리자 페이지 ---
def admin_page():
    st.title("🛡️ 관리자 페이지")
    if st.sidebar.button("관리자 로그아웃"):
        st.session_state.logged_in = False; st.session_state.is_admin = False; st.rerun()
    
    t1, t2 = st.tabs(["👥 사용자 관리", "📥 데이터 확인"])
    with t1:
        st.write("등록된 사용자 목록")
        st.dataframe(pd.DataFrame(SheetManager.get_users()))
        c1, c2 = st.columns(2)
        with c1.form("add_user"):
            nu = st.text_input("새 ID"); np = st.text_input("새 비번", type="password")
            if st.form_submit_button("추가") and nu and np:
                SheetManager.add_user(nu, np); st.rerun()
        with c2.form("del_user"):
            users = SheetManager.get_users()
            du = st.selectbox("삭제할 ID", [u['username'] for u in users] if users else [])
            if st.form_submit_button("삭제") and du:
                if du != "관리자": SheetManager.delete_user(du); st.rerun()
                else: st.error("불가")

    with t2:
        df = SheetManager.get_all_logs()
        st.dataframe(df)
        if not df.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
            st.download_button("엑셀 다운로드", buffer, "baseball_log.xlsx")

# --- 메인 실행 로직 ---
def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state.username} 선수")
    if 'current_date' not in st.session_state: st.session_state.current_date = datetime.now().date()
    st.session_state.current_date = st.sidebar.date_input("날짜 선택", st.session_state.current_date)
    date_str = st.session_state.current_date.strftime("%Y-%m-%d")

    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False; st.rerun()

    tab1, tab2 = st.tabs(["📝 일일 훈련 일지", "📊 Dashboard"])
    with tab1: render_daily_log(st.session_state.username, date_str, SheetManager.get_log(st.session_state.username, date_str))
    with tab2: render_dashboard(st.session_state.username, st.session_state.current_date)

if __name__ == "__main__":
    if not st.session_state.logged_in:
        login_page()
    elif st.session_state.is_admin:
        admin_page()
    else:
        main_app()