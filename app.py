import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv

# --- 1. 讀取環境變數 (本地端優先) ---
load_dotenv()

# 初始化 API_KEY
API_KEY = os.getenv("OPENAI_API_KEY")

# --- 2. 如果本地沒抓到，再試試看雲端 Secrets (預防崩潰處理) ---
if not API_KEY:
    try:
        # 只有在 st.secrets 真的有東西時才讀取
        if "OPENAI_API_KEY" in st.secrets:
            API_KEY = st.secrets["OPENAI_API_KEY"]
    except Exception:
        # 如果連 secrets 功能都還沒初始化，就安靜地跳過
        pass

# --- 3. 初始化 OpenAI 客戶端 ---
if API_KEY:
    client = OpenAI(api_key=API_KEY)
else:
    # 這裡用 st.warning 代替噴錯，畫面會好看很多
    st.warning("🔑 尚未偵測到 API Key。本地請檢查 .env 檔案，雲端請檢查 Secrets 設定。")
    client = None
    client = None

# --- 1. 網頁初始配置 ---
st.set_page_config(page_title="轉學考英文衝刺GOGO", page_icon="🎯", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #007bff; }
    div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    textarea { font-family: 'Consolas', monospace; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 資料持久化功能 (優化：加入空白檔案處理) ---
DATA_FILE = "study_data.csv"
EXT_DATA_FILE = "study_ext.json"

def load_all_data():
    history = []
    ext_data = {"notes": "", "wrong_questions": ""}
    
    # 讀取 CSV
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            if not df.empty:
                history = df.to_dict('records')
        except:
            history = []
            
    # 讀取 JSON
    if os.path.exists(EXT_DATA_FILE):
        try:
            with open(EXT_DATA_FILE, "r", encoding="utf-8") as f:
                ext_data = json.load(f)
        except:
            pass
    return history, ext_data

def save_all_data(history, ext_data):
    # 儲存 CSV
    pd.DataFrame(history).to_csv(DATA_FILE, index=False)
    # 儲存 JSON
    with open(EXT_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(ext_data, f, ensure_ascii=False, indent=4)

# --- 3. 初始化 Session State ---
loaded_history, loaded_ext = load_all_data()

if 'word_notes' not in st.session_state: 
    st.session_state['word_notes'] = loaded_ext.get("notes", "")
if 'wrong_notes' not in st.session_state: 
    st.session_state['wrong_notes'] = loaded_ext.get("wrong_questions", "")
if 'daily_test' not in st.session_state: 
    st.session_state['daily_test'] = ""
if 'weekly_test' not in st.session_state: 
    st.session_state['weekly_test'] = ""
if 'learning_history' not in st.session_state: 
    st.session_state['learning_history'] = loaded_history

# 計算平均正確率作為進度條
if st.session_state['learning_history']:
    all_acc = [item["正確率 (%)"] for item in st.session_state['learning_history']]
    st.session_state['auto_progress'] = sum(all_acc) / len(all_acc)
else:
    st.session_state['auto_progress'] = 5.0

# --- 4. 側邊欄：進度顯示與筆記 ---
with st.sidebar:
    st.header("📓 單詞隨手記")
    # 使用 key 確保狀態同步
    st.session_state['word_notes'] = st.text_area("記錄新單字/片語：", value=st.session_state['word_notes'], height=250, key="side_notes_input")
    
    if st.button("💾 立即存檔筆記"):
        save_all_data(st.session_state['learning_history'], {"notes": st.session_state['word_notes'], "wrong_questions": st.session_state['wrong_notes']})
        st.success("存檔成功！")
    st.divider()

    st.header("📈 學習進度")
    st.progress(min(st.session_state['auto_progress'] / 100, 1.0))
    st.write(f"目前平均正確率：{st.session_state['auto_progress']:.1f}%")
    st.divider()
    
    st.header("🛡️ 預算管理中心")
    budget_mode = st.toggle("啟動預算保護", value=True, help="開啟後將使用 gpt-4o-mini，成本節省 90% 以上")
    if budget_mode:
        st.success("目前模式：小資省錢 (mini)")
        current_model = "gpt-4o-mini"
    else:
        st.warning("目前模式：高階解析 (gpt-4o)")
        current_model = "gpt-4o"

    
# --- 5. 主要功能區 ---
st.title("🎯轉學考英文衝刺GOGO")

tabs = st.tabs(["💡 題目解析", "✍🏻 寫作批改", "📝 測驗中心", "❌ 錯題筆記區", "📊 數據紀錄"])

# --- Tab 1: 題目解析 ---
with tabs[0]:
    st.header("🤖 AI 解題分析")
    user_input = st.text_area("貼上題目與選項：", height=200, placeholder="例如：The committee decided to ___ the proposal...", key="tab1_input")
    
    if st.button("🚀 進行深度解析"):
        if user_input and client:
            with st.spinner("正在進行多典比對分析中..."):
                try:
                    # 最終精煉版 Prompt
                    detailed_prompt = (
                        "你是一位專業的大學英文轉學考指導教授。請針對以下題目進行深度解析，格式如下：\n\n"
                        "1. **【正確答案】**：選項與單字。\n\n"
                        "2. **【解題邏輯】**：說明選擇原因，並解釋其他選項為何錯誤（詞性、語意）。\n\n"
                        "3. **【核心文法】**：分析句子文法結構（如：分詞構句、倒裝、關係代名詞等），並解釋此文法之規則。\n\n"
                        "4. **【單字：】**\n"
                        "   列出題目中值得學習的 3-5 個高階單字及其用法，交叉比對「Merriam-Webster」、「Cambridge Dictionary」及「英漢詞典」後整理：\n"
                        "   - **意思**：列出 1-3 個最重要定義及詞性（直接給予意思，不需要例句，且不侷限於本題上下文）。\n"
                        "   - **搭配詞 (Collocations)**：提供 1-3 個該單字的常見搭配法（動詞、形容詞或介係詞）。\n\n"
                        "5. **【全文翻譯】**：流暢的中譯。\n\n"
                        f"題目內容：\n{user_input}"
                    )
                    
                    resp = client.chat.completions.create(
                        model=current_model, 
                        messages=[
                            {"role": "system", "content": "你是一位專業的英文解題導師，擅長提供精煉、準確的單字定義與結構化分析。"},
                            {"role": "user", "content": detailed_prompt}
                        ],
                        temperature=0.4
                    )
                    
                    st.success("深度分析完成！")
                    st.markdown(resp.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"發生錯誤：{e}")
        else:
            st.warning("請輸入題目內容！")

# --- Tab 2: 寫作批改 ---
with tabs[1]:
    st.header("✍🏻 寫作批改")
    essay_input = st.text_area("輸入文章段落...", height=300, key="tab2_input")
    if st.button("📝 提交批改"):
        if essay_input and client:
            with st.spinner("AI 批改中..."):
                try:
                    resp = client.chat.completions.create(
                        model=current_model, 
                        messages=[{"role": "user", "content": f"請扮演英文老師，批改、評分並提供優化建議與範文：{essay_input}"}]
                    )
                    st.write(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

# --- Tab 3: 測驗中心 ---
with tabs[2]:
    st.header("📝 測驗中心")
    test_mode = st.radio("選擇測驗類型：", ["☀️ 每日出題 ", "🗓️ 每週大會考 "], horizontal=True)
    if st.button("⚡ 生成題目"):
        if client:
            with st.spinner("AI 正在出題..."):
                try:
                    context = f"單字筆記：{st.session_state['word_notes']}\n錯題紀錄：{st.session_state['wrong_notes']}"
                    spec = "3題單字選擇題及1題文法找錯題" if "每日" in test_mode else "30題單字選擇題及10題文法找錯題"
                    m_target = "daily" if "每日" in test_mode else "weekly"
                    prompt = f"你是一位轉學考名師。根據以下背景知識出題：\n{context}\n\n規格：{spec}。難度對標台政大。附詳細解析。請優先變換錯題型。"
                    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                    st.session_state[f'{m_target}_test'] = resp.choices[0].message.content
                except Exception as e:
                    st.error(f"生成失敗：{e}")

    if "每日" in test_mode and st.session_state['daily_test']:
        st.markdown(st.session_state['daily_test'])
    elif "每週" in test_mode and st.session_state['weekly_test']:
        st.markdown(st.session_state['weekly_test'])

# --- Tab 4: 錯題筆記區 ---
with tabs[3]:
    st.header("❌ 錯題筆記區")
    # 使用 key 確保狀態同步
    st.session_state['wrong_notes'] = st.text_area("我的錯題庫：", value=st.session_state['wrong_notes'], height=500, key="main_wrong_notes_input")
    if st.button("💾 儲存錯題庫"):
        save_all_data(st.session_state['learning_history'], {"notes": st.session_state['word_notes'], "wrong_questions": st.session_state['wrong_notes']})
        st.success("錯題紀錄已更新！")

# --- Tab 5: 📊 數據紀錄 ---
with tabs[4]:
    st.header("📊 進度紀錄")
    col_a, col_b = st.columns(2)
    with col_a: total_q = st.number_input("總題數", min_value=1, value=4)
    with col_b: correct_q = st.number_input("答對數", min_value=0, max_value=total_q, value=2)
    
    if st.button("💾 儲存進度"):
        acc = round((correct_q / total_q) * 100, 1)
        st.session_state['learning_history'].append({
            "日期": pd.Timestamp.now().strftime("%m-%d"), 
            "總題數": total_q, 
            "答對數": correct_q, 
            "正確率 (%)": acc
        })
        save_all_data(st.session_state['learning_history'], {"notes": st.session_state['word_notes'], "wrong_questions": st.session_state['wrong_notes']})
        st.success("進度已紀錄！")
        st.rerun()

    if st.session_state['learning_history']:
        df = pd.DataFrame(st.session_state['learning_history'])
        st.line_chart(df.set_index("日期")["正確率 (%)"])
        st.table(df)
        
        if st.button("🗑️ 清空所有歷史紀錄"):
            st.session_state['learning_history'] = []
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            st.rerun()