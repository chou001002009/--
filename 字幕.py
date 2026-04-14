import streamlit as st
import google.generativeai as genai
import time
import os


with st.sidebar:
    st.write(f"系統套件版本: {genai.__version__}")
    try:
        models = [m.name for m in genai.list_models()]
        st.write("目前可用的模型清單：")
        st.write(models)
    except Exception as e:
        st.error(f"無法列出模型清單：{e}")
# ==========================================
# 0. 系統核心設定 (保險箱模式)
# ==========================================
def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except:
        pass
    return os.environ.get("GEMINI_API_KEY", "")

MY_API_KEY = get_api_key()

# 這裡改用通用名稱，並強迫初始化時直接對齊
if MY_API_KEY:
    genai.configure(api_key=MY_API_KEY)
    # 改用這個最保險的宣告方式
    AI_MODEL_NAME = "gemini-1.5-flash" 
else:
    AI_MODEL_NAME = "gemini-1.5-flash"
# ==========================================
# 1. 頻道專屬設定
# ==========================================
VIDEO_SERIES = ["送你營養吃", "阿環格格出遊去", "阿環格格花錢去", "Vlog", "其他"]

SYSTEM_INSTRUCTION = """你現在是一位專業的 YouTube 影片逐字稿聽打與校正助理，專門處理「Sunny營養師」頻道的內容。
你的任務是：
1. 接收「音軌檔案」或「原始逐字稿文字」。
2. 根據以下「絕對校正規則」進行修正：
   - 【人物】：保留安媽、阿嬤、阿環、Sunny等稱謂，不要強制統一。
   - 【台語】：錯誤國語同音字還原為台語漢字（如：哩賀、歹勢、安捏）。
   - 【專有名詞】：水氣->牙齒、好有嚇->比較划算、各美心->鉻鎂鋅、糖流到臉->糖尿病、一瓶->一邊。
   - 【格式】：每行絕對不可超過 16 個字，不需加上任何標點符號。
   - 【贅字】：只刪除「啊、呢、嗯、喔、耶、嘛」這六個。
   - 【副詞】：一律使用「蠻」，不可使用「滿」。

請直接輸出校正後的純文字結果，不要有任何額外的解釋。"""

# ==========================================
# 2. 核心處理邏輯
# ==========================================
def process_content(series, uploaded_file=None, manual_text=None):
    model = genai.GenerativeModel(AI_MODEL_NAME)
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext == 'txt':
            content = uploaded_file.read().decode("utf-8")
            prompt = f"影片系列：{series}\n請校正以下逐字稿文字：\n\n{content}"
            response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
            for chunk in response:
                if chunk.text: yield chunk.text
        else:
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            audio_file = genai.upload_file(path=temp_path)
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
            
            prompt = f"這是「{series}」系列的影片音軌，請聽取內容並依照規則生成校正後的純文字逐字稿。"
            response = model.generate_content(
                [audio_file, "\n\n", SYSTEM_INSTRUCTION, prompt],
                request_options={"timeout": 600},
                stream=True
            )
            for chunk in response:
                if chunk.text: yield chunk.text
                
            os.remove(temp_path)
            genai.delete_file(audio_file.name)
            
    elif manual_text:
        prompt = f"影片系列：{series}\n請校正以下逐字稿文字：\n\n{manual_text}"
        response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text

# ==========================================
# 3. Streamlit 介面
# ==========================================
def main():
    st.set_page_config(page_title="Sunny 影音/文字校正器", layout="wide", page_icon="🎙️")
    st.title("🎙️ Sunny 營養師：影音轉文字與校正工具")

    with st.sidebar:
        st.header("⚙️ 設定")
        series = st.selectbox("影片系列", VIDEO_SERIES)
        st.divider()
        st.write(f"當前模型：**{AI_MODEL_NAME}**")
        if not MY_API_KEY:
            st.warning("⚠️ 尚未偵測到 API Key，請前往 Secrets 設定。")

    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("📥 輸入內容")
        uploaded_file = st.file_uploader("上傳音軌或文字檔", type=['mp3', 'm4a', 'wav', 'mp4', 'txt'])
        if uploaded_file:
            st.success(f"✅ 「{uploaded_file.name}」載入成功")
        st.write("--- 或 ---")
        manual_text = st.text_area("在此貼上原始文字：", height=300)

    with col_out:
        st.subheader("📤 校正結果")
        if st.button("🚀 開始執行", use_container_width=True):
            if not MY_API_KEY:
                st.error("⚠️ 錯誤：保險箱內沒有 API Key！請參考教學設定 Secrets。")
            elif not uploaded_file and not manual_text:
                st.warning("⚠️ 請先提供檔案或文字")
            else:
                status_msg = st.info("AI 正在分析與校正中...")
                try:
                    result_box = st.empty()
                    full_text = ""
                    for chunk_text in process_content(series, uploaded_file, manual_text):
                        status_msg.empty() 
                        full_text += chunk_text
                        result_box.text_area("✨ 即時生成內容：", full_text, height=500)
                        
                    st.balloons()
                    st.success("🎉 校正完畢！")
                    st.download_button(
                        label="💾 下載校正後的文字檔 (.txt)",
                        data=full_text,
                        file_name=f"{series}_校正結果.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
