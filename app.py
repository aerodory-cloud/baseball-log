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

# [패치 1] 이미지 호환성
if not hasattr(st_image, 'image_to_url'):
    def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None, allow_emoji=False):
        if isinstance(image, str): return image
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
        return ""
    st_image.image_to_url = custom_image_to_url

# [패치 2] 한글 폰트 (클라우드 환경 대응: 폰트 없어도 에러 안 나게 처리)
if platform.system() == 'Windows':
    try:
        plt.rc('font', family='Malgun Gothic')
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
else:
    # 리눅스(클라우드)에서는 기본 폰트 사용
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
        except Exception as e:
            return []

    @staticmethod
    def add_user(username, password):
        sh = SheetManager.get_connection()
        ws = sh.worksheet("users")
        ws.append_row([username, password])

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
            # 데이터프레임 필터링
            filtered = df[(df['username'] == username) & (df['date'] == date_str) & (df['log_type'] == log_type)]
            if not filtered.empty:
                return filtered.iloc[0].to_dict()
            return None
        except: return None

    @staticmethod
    def save_log(log_data):
        sh = SheetManager.get_connection()
        ws = sh.worksheet("training_logs")
        df = pd.DataFrame(ws.get_all_records())
        
        target_row = None
        if not df.empty:
            mask = (df['username'] == log_data['username']) & (df['date'] == log_data['date']) & (df['log_type'] == log_data['log_type'])
            if mask.any():
                target_row = df.index[mask][0] + 2 # 헤더 보정

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

    @staticmethod
    def get_all_logs(username=None):
        try:
            sh = SheetManager.get_connection()
            ws = sh.worksheet("training_logs")
            df = pd.DataFrame(ws.get_all_records())
            if df.empty: return df
            if username: return df[df['username'] == username]
            return df
        except: return pd.DataFrame()

# --- 메인 앱 로직 ---
st.set_page_config(page_title="야구 훈련 일지", layout="wide")
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'is_admin' not in st.session_state: st.session_state.is_admin = False

def login_page():
    _, c_logo, c_text, _ = st.columns([1, 1, 5, 1], vertical_alignment="center")
    with c_logo: st.header("⚾")
    with c_text: st.markdown("## 수지리틀야구단 선수 훈련 일지")
    
    st.write("")
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.subheader("로그인")
        username = st.text_input("이름 (ID)")
        password = st.text_input("비밀번호", type="password")
        if st.button("로그인", use_container_width=True):
            users = SheetManager.get_users()
            valid = any(str(u['username'])==username and str(u['password'])==password for u in users)
            if valid:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else: st.error("정보 불일치")
        
        st.divider()
        with st.expander("관리자 접속"):
            if st.button("관리자 로그인") and st.text_input("PIN", type="password") == "98770491":
                st.session_state.logged_in=True; st.session_state.username="관리자"; st.session_state.is_admin=True; st.rerun()

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state.username} 선수")
    if 'current_date' not in st.session_state: st.session_state.current_date = datetime.now().date()
    st.session_state.current_date = st.sidebar.date_input("날짜 선택", st.session_state.current_date)
    date_str = st.session_state.current_date.strftime("%Y-%m-%d")
    if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    tab1, tab2 = st.tabs(["📝 일일 훈련 일지", "📊 Dashboard"])
    
    with tab1:
        data = SheetManager.get_log(st.session_state.username, date_str) or {}
        with st.form("daily"):
            st.markdown(f"### Training Journal : {date_str}")
            get = lambda k,d: d.get(k, 0); get_t = lambda k,d: d.get(k, "")
            
            c1,c2=st.columns([1,5]); c1.write("**훈련 시간**"); dur=c2.number_input("분",value=int(get('duration',data)),step=10,label_visibility="collapsed")
            c3,c4=st.columns([1,5]); c3.write("**장소**"); loc_opts=["실외 구장","실내 구장","집","기타"]
            loc=c4.radio("장소",loc_opts,index=loc_opts.index(get_t('location',data)) if get_t('location',data) in loc_opts else 0,horizontal=True,label_visibility="collapsed")
            c5,c6=st.columns([1,5]); c5.write("**강도**"); lvls=["최상","상","중","하","최하"]
            inte=c6.radio("강도",lvls,index=lvls.index(get_t('intensity',data)) if get_t('intensity',data) in lvls else 2,horizontal=True,label_visibility="collapsed")
            c7,c8=st.columns([1,5]); c7.write("**만족도**"); sat=c8.radio("만족",lvls,index=lvls.index(get_t('satisfaction',data)) if get_t('satisfaction',data) in lvls else 2,horizontal=True,label_visibility="collapsed")
            
            st.divider(); st.write("#### 훈련 내용")
            cc1, cc2 = st.columns(2)
            with cc2:
                st.info("💪 개인 훈련")
                ps=st.number_input("연습 스윙(회)",value=int(get('p_swing',data)),step=10)
                pl=st.number_input("라이브 배팅(분)",value=int(get('p_live',data)),step=10)
                pd_val=st.number_input("수비 훈련(분)",value=int(get('p_defense',data)),step=10)
                pp=st.number_input("피칭 훈련(개)",value=int(get('p_pitching',data)),step=10)
                pr=st.number_input("런닝 훈련(분)",value=int(get('p_running',data)),step=10)
                ph=st.number_input("철봉(분)",value=int(get('p_hanging',data)),step=1)
                pe=st.text_input("기타",value=get_t('p_etc',data))
            with cc1:
                st.success("⚾ 구단 훈련"); gc=st.text_area("내용",value=get_t('gudan_content',data),height=380)
            
            st.divider(); st.write("#### 피드백")
            cf1, cf2 = st.columns(2)
            with cf2: st.error("나의 분석"); sg=st.text_area("Good",value=get_t('self_good',data)); sb=st.text_area("Bad",value=get_t('self_bad',data))
            with cf1: st.warning("코치 피드백"); cfb=st.text_area("Coach",value=get_t('coach_feedback',data),height=200)
            
            st.divider(); pro=st.text_input("다짐",value=get_t('promise',data)); mem=st.text_input("메모",value=get_t('memo',data))
            
            if st.form_submit_button("💾 저장", type="primary"):
                SheetManager.save_log({
                    'username':st.session_state.username, 'date':date_str, 'duration':dur, 'location':loc,
                    'intensity':inte, 'satisfaction':sat, 'gudan_content':gc, 'p_swing':ps, 'p_live':pl,
                    'p_defense':pd_val, 'p_pitching':pp, 'p_running':pr, 'p_hanging':ph, 'p_etc':pe,
                    'coach_feedback':cfb, 'self_good':sg, 'self_bad':sb, 'promise':pro, 'memo':mem
                })
                st.success("저장 완료!")

    with tab2:
        # 대시보드
        st.header("📊 Dashboard")
        metrics = {"총 훈련 시간":("duration","분"), "연습 스윙":("p_swing","회"), "라이브 배팅":("p_live","분"), 
                   "수비 훈련":("p_defense","분"), "피칭 훈련":("p_pitching","개"), "런닝":("p_running","분"), "철봉":("p_hanging","분")}
        sel = st.selectbox("항목 선택", list(metrics.keys()))
        col_name, unit = metrics[sel]
        
        df = SheetManager.get_all_logs(st.session_state.username)
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']); df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)
            today = pd.Timestamp(st.session_state.current_date)
            
            def draw_chart(tit, sub_df, idx, fmt, clr, lbls=None):
                st.subheader(tit)
                if sub_df.empty: st.caption("데이터 없음"); return
                grp = sub_df.groupby('month')[col_name].sum() if 'month' in sub_df else sub_df.groupby('date')[col_name].sum()
                fin = grp.reindex(idx, fill_value=0)
                fig, ax = plt.subplots(figsize=(10,3))
                ax.bar(lbls if lbls else (fin.index.strftime(fmt) if fmt else fin.index), fin.values, color=clr)
                st.pyplot(fig)
            
            # 주간
            s_w = today - timedelta(days=today.weekday())
            draw_chart("주간", df[(df['date']>=s_w)&(df['date']<=s_w+timedelta(6))], pd.date_range(s_w, periods=7), '%a', 'skyblue')
            # 월간
            s_m = today.replace(day=1); n_m = (s_m+timedelta(32)).replace(day=1)
            draw_chart("월간", df[(df['date']>=s_m)&(df['date']<n_m)], pd.date_range(s_m, n_m-timedelta(1)), '%d', 'lightgreen')
            # 연간
            y_df = df[df['date'].dt.year==today.year].copy(); y_df['month']=y_df['date'].dt.month
            draw_chart("연간", y_df, range(1,13), None, 'salmon', [f"{i}월" for i in range(1,13)])
        else:
            st.info("데이터가 없습니다.")

if __name__ == "__main__":
    if not st.session_state.logged_in: login_page()
    else: main_app()