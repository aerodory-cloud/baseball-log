import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import base64
import os
import platform
from PIL import Image
import matplotlib.pyplot as plt
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 캔버스 모듈 (설치 여부 체크)
try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st_canvas = None

import streamlit.elements.image as st_image

# [설정] 한글 폰트 및 이미지 호환성 패치
if not hasattr(st_image, 'image_to_url'):
    def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None, allow_emoji=False):
        if isinstance(image, str): return image
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
        return ""
    st_image.image_to_url = custom_image_to_url

if platform.system() == 'Windows':
    try:
        plt.rc('font', family='Malgun Gothic')
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
else:
    plt.rcParams['axes.unicode_minus'] = False

# --- [Core] 구글 시트 데이터베이스 매니저 ---
class SheetManager:
    SHEET_NAME = 'baseball_log_db'

    @staticmethod
    def _connect():
        """구글 시트 연결 (내부용)"""
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SheetManager.SHEET_NAME)

    @staticmethod
    def get_users():
        """유저 목록 가져오기"""
        try:
            ws = SheetManager._connect().worksheet("users")
            # [복구] 기존 아이디 로그인을 위해 numericise_data=False 필수
            # 이걸 빼면 '031'을 31(숫자)로 가져와서 로그인이 안됩니다.
            return ws.get_all_records(numericise_data=False)
        except: return []

    @staticmethod
    def add_user(username, password):
        """유저 추가 (단순 추가 방식)"""
        ws = SheetManager._connect().worksheet("users")
        # [원복] 가장 단순하게 맨 뒤에 추가하는 방식
        # 엑셀 특성상 숫자 앞의 0은 사라질 수 있지만, 등록은 무조건 됩니다.
        ws.append_row([str(username), str(password)])

    @staticmethod
    def delete_user(username):
        """유저 삭제"""
        ws = SheetManager._connect().worksheet("users")
        try:
            cell = ws.find(username)
            if cell: ws.delete_rows(cell.row)
        except: pass

    @staticmethod
    def get_logs(username=None):
        """모든 로그 가져오기"""
        try:
            ws = SheetManager._connect().worksheet("training_logs")
            df = pd.DataFrame(ws.get_all_records())
            if df.empty: return pd.DataFrame()
            if username: return df[df['username'] == username]
            return df
        except: return pd.DataFrame()

    @staticmethod
    def save_log(log_data):
        """로그 저장 또는 수정"""
        ws = SheetManager._connect().worksheet("training_logs")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        target_row = None
        if not df.empty:
            mask = (df['username'] == log_data['username']) & (df['date'] == log_data['date']) & (df['log_type'] == log_data['log_type'])
            if mask.any():
                target_row = df.index[mask][0] + 2

        row_vals = [
            0, log_data.get('username'), log_data.get('date'), log_data.get('duration', 0),
            log_data.get('location', ''), log_data.get('intensity', ''), log_data.get('satisfaction', ''),
            log_data.get('gudan_content', ''), log_data.get('p_swing', 0), log_data.get('p_live', 0),
            log_data.get('p_defense', 0), log_data.get('p_pitching', 0), log_data.get('p_running', 0),
            log_data.get('p_hanging', 0), log_data.get('p_etc', ''), log_data.get('coach_feedback', ''),
            log_data.get('self_good', ''), log_data.get('self_bad', ''), log_data.get('promise', ''),
            log_data.get('memo', ''), log_data.get('log_type', 'daily'), log_data.get('tactical_image', '')
        ]

        if target_row:
            ws.update(f"A{target_row}:V{target_row}", [row_vals])
        else:
            ws.append_row(row_vals)

# --- [UI] 페이지별 화면 구성 ---

def render_login():
    """로그인 페이지"""
    _, c_logo, c_text, _ = st.columns([1, 1, 5, 1], vertical_alignment="center")
    with c_logo:
        try: st.image("logo.png", width=150)
        except: st.header("⚾")
    with c_text:
        st.markdown("## 수지리틀야구단 선수 훈련 일지")
    
    st.write("")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            st.subheader("로그인")
            u_in = st.text_input("아이디"); p_in = st.text_input("비밀번호", type="password")
            if st.form_submit_button("접속하기", use_container_width=True):
                users = SheetManager.get_users()
                # [수정] 어떤 형태로 들어있든 무조건 문자로 변환해서 비교 (로그인 오류 해결)
                if any(str(u['username']).strip() == str(u_in).strip() and str(u['password']).strip() == str(p_in).strip() for u in users):
                    st.session_state.logged_in = True
                    st.session_state.username = u_in
                    st.session_state.is_admin = False
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호를 확인해주세요.")

        st.divider()
        with st.expander("관리자 모드"):
            with st.form("admin_form"):
                pin = st.text_input("PIN", type="password")
                if st.form_submit_button("관리자 접속"):
                    if pin == "98770491":
                        st.session_state.logged_in = True
                        st.session_state.username = "관리자"
                        st.session_state.is_admin = True
                        st.rerun()
                    else: st.error("PIN 번호 오류")

def render_daily_log(username, date_str):
    """일일 훈련 일지 작성"""
    logs = SheetManager.get_logs(username)
    data = {}
    if not logs.empty:
        filtered = logs[(logs['date'] == date_str) & (logs['log_type'] == 'daily')]
        if not filtered.empty: data = filtered.iloc[0].to_dict()

    val = lambda k: int(data[k]) if k in data and data[k] != '' else 0
    txt = lambda k: str(data[k]) if k in data else ""

    with st.form("daily_form"):
        st.markdown(f"### 📝 Training Journal : {date_str}")
        
        c1, c2 = st.columns([1, 4])
        c1.markdown("**⏱️ 훈련 시간**"); dur = c2.number_input("분", value=val('duration'), step=10, label_visibility="collapsed")
        
        c3, c4 = st.columns([1, 4])
        c3.markdown("**📍 훈련 장소**"); locs = ["실외 구장", "실내 구장", "집", "기타"]
        loc = c4.radio("장소", locs, index=locs.index(txt('location')) if txt('location') in locs else 0, horizontal=True, label_visibility="collapsed")
        
        lvls = ["최상", "상", "중", "하", "최하"]
        c5, c6 = st.columns([1, 4])
        c5.markdown("**🔥 훈련 강도**"); inte = c6.radio("강도", lvls, index=lvls.index(txt('intensity')) if txt('intensity') in lvls else 2, horizontal=True, label_visibility="collapsed")
        c7, c8 = st.columns([1, 4])
        c7.markdown("**😊 훈련 만족도**"); sat = c8.radio("만족", lvls, index=lvls.index(txt('satisfaction')) if txt('satisfaction') in lvls else 2, horizontal=True, label_visibility="collapsed")

        st.divider()
        
        wc1, wc2 = st.columns(2)
        with wc2:
            st.info("💪 개인 훈련 (Personal Training)")
            def p_row(label, k, step=10):
                rc1, rc2 = st.columns([2, 1])
                rc1.write(f"• {label}")
                return rc2.number_input(label, value=val(k), step=step, label_visibility="collapsed")
            
            p_swing = p_row("연습 스윙 (회)", 'p_swing')
            p_live = p_row("라이브 배팅 (분)", 'p_live')
            p_defense = p_row("수비 훈련 (분)", 'p_defense')
            p_pitching = p_row("피칭 훈련 (개)", 'p_pitching')
            p_running = p_row("런닝 훈련 (분)", 'p_running')
            p_hanging = p_row("철봉 매달리기 (분)", 'p_hanging', 1)
            
            ec1, ec2 = st.columns([1, 2])
            ec1.write("• 기타 훈련"); p_etc = ec2.text_input("기타", value=txt('p_etc'), label_visibility="collapsed")

        with wc1:
            st.success("⚾ 구단 훈련 (Team Training)")
            gudan = st.text_area("내용을 입력하세요", value=txt('gudan_content'), height=380, label_visibility="collapsed")

        st.divider()
        
        fc1, fc2 = st.columns(2)
        with fc2:
            st.error("🧠 나의 분석 (Self Feedback)")
            good = st.text_area("잘된 부분", value=txt('self_good'), height=80, placeholder="잘된 부분", label_visibility="collapsed")
            bad = st.text_area("부족한 부분", value=txt('self_bad'), height=80, placeholder="부족한 부분", label_visibility="collapsed")
        with fc1:
            st.warning("🗣️ 코치 피드백 (Coach's Feedback)")
            coach = st.text_area("coach", value=txt('coach_feedback'), height=220, label_visibility="collapsed")

        st.divider()
        
        prom = st.text_area("다짐", value=txt('promise'), height=70, placeholder="오늘의 다짐", label_visibility="collapsed")
        memo = st.text_area("메모", value=txt('memo'), height=70, placeholder="추가 메모", label_visibility="collapsed")

        if st.form_submit_button("💾 금일 훈련 저장하기", type="primary"):
            SheetManager.save_log({
                'username': username, 'date': date_str, 'log_type': 'daily',
                'duration': dur, 'location': loc, 'intensity': inte, 'satisfaction': sat,
                'gudan_content': gudan, 'p_swing': p_swing, 'p_live': p_live,
                'p_defense': p_defense, 'p_pitching': p_pitching, 'p_running': p_running,
                'p_hanging': p_hanging, 'p_etc': p_etc,
                'coach_feedback': coach, 'self_good': good, 'self_bad': bad,
                'promise': prom, 'memo': memo
            })
            st.success("✅ 저장되었습니다!")

def render_dashboard(username, current_date):
    """통계 대시보드"""
    h1, h2 = st.columns([3, 1], vertical_alignment="center")
    with h1: st.header("📊 Dashboard")
    
    metrics = {"총 훈련 시간":("duration","분"), "연습 스윙":("p_swing","회"), "라이브 배팅":("p_live","분"), 
               "수비 훈련":("p_defense","분"), "피칭 훈련":("p_pitching","개"), "런닝":("p_running","분"), "철봉":("p_hanging","분")}
    with h2:
        sel = st.selectbox("항목 선택", list(metrics.keys()))
        col, unit = metrics[sel]

    df = SheetManager.get_logs(username)
    if not df.empty and 'log_type' in df.columns: df = df[df['log_type'] == 'daily']
    
    if df.empty:
        st.info("데이터가 없습니다.")
        return

    df['date'] = pd.to_datetime(df['date'])
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    today = pd.Timestamp(current_date)
    
    def draw_chart(title, data, idx, fmt, color, x_labels=None):
        st.subheader(title)
        if data.empty: st.caption("데이터 없음"); st.divider(); return
        
        grp = data.groupby('month')[col].sum() if 'month' in data.columns else data.groupby('date')[col].sum()
        final = grp.reindex(idx, fill_value=0)
        
        total = int(final.sum())
        active = data[data[col] > 0].shape[0]
        avg = int(total/active) if active > 0 else 0
        
        m1, m2 = st.columns(2)
        m1.metric(f"총 {sel}", f"{total} {unit}"); m2.metric("일 평균", f"{avg} {unit}")
        
        fig, ax = plt.subplots(figsize=(10, 3.5))
        labels = x_labels if x_labels else (final.index.strftime(fmt) if fmt else final.index)
        ax.bar(labels, final.values, color=color)
        
        for i, v in enumerate(final.values):
            if v > 0: ax.text(i, v, str(int(v)), ha='center', va='bottom', fontsize=8)
            
        st.pyplot(fig); st.divider()

    s_w = today - timedelta(days=today.weekday())
    draw_chart("📅 이번 주", df[(df['date'] >= s_w) & (df['date'] <= s_w + timedelta(6))], 
               pd.date_range(s_w, periods=7), '%a', 'skyblue')
    
    s_m = today.replace(day=1); n_m = (s_m + timedelta(32)).replace(day=1)
    draw_chart("📅 이번 달", df[(df['date'] >= s_m) & (df['date'] < n_m)], 
               pd.date_range(s_m, n_m - timedelta(1)), '%d', 'lightgreen')
    
    y_df = df[df['date'].dt.year == today.year].copy()
    y_df['month'] = y_df['date'].dt.month
    draw_chart("📅 올 한해", y_df, range(1, 13), None, 'salmon', [f"{i}월" for i in range(1, 13)])

def render_admin():
    """관리자 페이지"""
    st.title("🛡️ 관리자 페이지")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False; st.rerun()
        
    t1, t2 = st.tabs(["👥 선수 관리", "💾 데이터 관리"])
    with t1:
        st.write("등록된 선수 목록")
        st.dataframe(pd.DataFrame(SheetManager.get_users()))
        
        c1, c2 = st.columns(2)
        with c1.form("add"):
            nu = st.text_input("새 ID"); np = st.text_input("새 비번 (숫자 가능)", type="password")
            if st.form_submit_button("추가"):
                if nu and np:
                    try: 
                        SheetManager.add_user(nu, np)
                        st.success(f"{nu} 추가 완료!")
                        st.rerun()
                    except Exception as e: st.error(f"오류: {e}")
                else: st.warning("ID와 비밀번호를 입력하세요.")
        
        with c2.form("del"):
            users = SheetManager.get_users()
            du = st.selectbox("삭제할 ID", [str(u['username']) for u in users] if users else [])
            if st.form_submit_button("삭제") and du:
                if du != "관리자": SheetManager.delete_user(du); st.rerun()
                else: st.error("관리자는 삭제 불가")

    with t2:
        df = SheetManager.get_logs()
        st.dataframe(df)
        if not df.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
            st.download_button("엑셀 다운로드", buffer, "log.xlsx")

# --- [Main] 앱 실행 로직 ---
st.set_page_config(page_title="야구 훈련 일지", layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'is_admin' not in st.session_state: st.session_state.is_admin = False

def main():
    if not st.session_state.logged_in:
        render_login()
    elif st.session_state.is_admin:
        render_admin()
    else:
        st.sidebar.markdown(f"### 👤 {st.session_state.username} 선수")
        
        if 'current_date' not in st.session_state: st.session_state.current_date = datetime.now().date()
        st.session_state.current_date = st.sidebar.date_input("날짜 선택", st.session_state.current_date)
        date_str = st.session_state.current_date.strftime("%Y-%m-%d")

        if st.sidebar.button("로그아웃"):
            st.session_state.logged_in = False; st.rerun()

        tab1, tab2 = st.tabs(["📝 일일 훈련 일지", "📊 Dashboard"])
        
        with tab1:
            render_daily_log(st.session_state.username, date_str)
        with tab2:
            render_dashboard(st.session_state.username, st.session_state.current_date)

if __name__ == "__main__":
    main()