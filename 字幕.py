import streamlit as st
import google.generativeai as genai
import time
import os

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
# 2026 最新推薦：使用穩定度最高的 Flash 模型
AI_MODEL_NAME = "gemini-flash-latest" 

if MY_API_KEY:
    genai.configure(api_key=MY_API_KEY)

# ==========================================
# 1. 頻道專屬校正規則
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
    generation_config = {
        "temperature": 0.05,        # 降到最低，防止 AI 亂編或跳字
        "top_p": 1,
        "max_output_tokens": 8192, # 確保長篇內容不會被強行切斷
    }
    
    # 建立模型時套用優化設定
    model = genai.GenerativeModel(
        model_name=AI_MODEL_NAME,
        generation_config=generation_config
    )
    
    # 處理手動輸入文字
    if manual_text and not uploaded_file:
        prompt = f"影片系列：{series}\n請校正以下逐字稿文字：\n\n{manual_text}"
        response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
            
   # --- 2. 處理檔案上傳 (Windows 穩定版) ---
    def process_content(series, uploaded_file=None, manual_text=None):
    # --- 優化參數設定：加入高精度配置 ---
    generation_config = {
        "temperature": 0.05,        # 降到最低，防止 AI 亂編或跳字
        "top_p": 1,
        "max_output_tokens": 8192, # 確保長篇內容不會被強行切斷
    }
    
    # 建立模型時套用優化設定
    model = genai.GenerativeModel(
        model_name=AI_MODEL_NAME,
        generation_config=generation_config
    )
    
    # 1. 處理手動輸入文字 (保持不變)
    if manual_text and not uploaded_file:
        prompt = f"影片系列：{series}\n請精準校正以下逐字稿文字，不可遺漏內容：\n\n{manual_text}"
        response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
            
    # 2. 處理檔案上傳
    elif uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        if file_ext == 'txt':
            content = uploaded_file.read().decode("utf-8")
            prompt = f"影片系列：{series}\n請精準校正以下文字，絕對不可刪減原文內容：\n\n{content}"
            response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
            for chunk in response:
                if chunk.text: yield chunk.text
        else:
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            audio_file = genai.upload_file(path=temp_path)
            
            # 狀態檢查 (保持不變)
            max_retries = 30
            retries = 0
            while audio_file.state.name == "PROCESSING" and retries < max_retries:
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
                retries += 1
            
            if audio_file.state.name != "ACTIVE":
                yield f"❌ 檔案處理失敗：{audio_file.state.name}"
                return

            # --- 優化 Prompt：強調「全文逐字」 ---
            prompt = (
                f"這是一段「{series}」系列的專業影音。你的任務是：\n"
                "1. 必須『全文還原』，絕對不可漏掉任何一句話。\n"
                "2. 針對語氣模糊的地方，請根據上下文推論最準確的詞語。\n"
                "3. 嚴格執行 Sunny 營養師的校正規則，但優先保證內容完整。\n"
                "4. 即使語句重複，也請完整記錄下來。"
            )

            response = model.generate_content(
                [audio_file, "\n\n", SYSTEM_INSTRUCTION, prompt],
                request_options={"timeout": 600},
                stream=True
            )
            for chunk in response:
                if chunk.text: yield chunk.text
                
            os.remove(temp_path)
            genai.delete_file(audio_file.name)
# ==========================================
# 3. Streamlit 介面
# ==========================================
def main():
    st.set_page_config(page_title="Sunny 影音校正器", layout="wide", page_icon="🎙️")
    st.title("🎙️ Sunny 營養師：影音轉文字與校正工具")

    with st.sidebar:
        st.header("⚙️ 設定")
        series = st.selectbox("影片系列", VIDEO_SERIES)
        st.divider()
        st.info(f"當前模型：{AI_MODEL_NAME}")
        if not MY_API_KEY:
            st.error("⚠️ 尚未設定 API Key！")

    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("📥 輸入內容")
        uploaded_file = st.file_uploader("上傳影音或文字檔", type=['mp3', 'm4a', 'wav', 'mp4', 'txt'])
        manual_text = st.text_area("或在此貼上文字：", height=300)

    with col_out:
        st.subheader("📤 校正結果")
        if st.button("🚀 開始執行", use_container_width=True):
            if not MY_API_KEY:
                st.error("請先在 Secrets 設定 API Key")
            elif not uploaded_file and not manual_text:
                st.warning("請提供檔案或文字內容")
            else:
                placeholder = st.empty()
                full_text = ""
                
                try:
                    # 這裡移除 status_msg 的依賴，改用單純的 placeholder
                    with st.status("AI 正在工作中...", expanded=True) as status:
                        for chunk_text in process_content(series, uploaded_file, manual_text):
                            full_text += chunk_text
                            placeholder.text_area("✨ 即時生成：", full_text, height=500)
                        status.update(label="✅ 校正完成！", state="complete", expanded=False)
                    
                    st.download_button(
                        label="💾 下載結果 (.txt)",
                        data=full_text,
                        file_name=f"{series}_校正.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
