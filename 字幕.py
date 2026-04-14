import streamlit as st
import google.generativeai as genai
import time
import os
import uuid

# ==========================================
# 0. 系統核心設定
# ==========================================
def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except:
        pass
    return os.environ.get("GEMINI_API_KEY", "")

MY_API_KEY = get_api_key()

# ⚠️ 建議：如果 Flash 效果不佳，可手動將下方改為 "gemini-1.5-pro"
AI_MODEL_NAME = "models/gemini-2.5-pro"

if MY_API_KEY:
    genai.configure(api_key=MY_API_KEY)

# ==========================================
# 1. 頻道專屬校正規則
# ==========================================
VIDEO_SERIES = ["送你營養吃", "阿環格格出遊去", "阿環格格花錢去", "Vlog", "其他"]

SYSTEM_INSTRUCTION = """你現在是一位專業的逐字稿聽寫與校正專家，專門處理「Sunny營養師」頻道的內容。
你的任務是：
1. 絕對執行「全文還原」：聽到什麼就寫什麼，嚴禁摘要、嚴禁刪減任何對話。
2. 即使內容重複、語助詞多，也必須完整記錄。
3. 根據以下規則校正：
   - 【人物】：保留安媽、阿嬤、阿環、Sunny等稱謂。
   - 【台語】：錯誤國語同音字還原為台語漢字（如：哩賀、歹勢、安捏）。
   - 【專有名詞】：水氣->牙齒、好有嚇->比較划算、各美心->鉻鎂鋅、糖流到臉->糖尿病、一瓶->一邊。
   - 【格式】：每行大約 16 個字左右，不需標點符號，但優先保證文字完整。
   - 【贅字】：只刪除「啊、呢、嗯、喔、耶、嘛」這六個，其餘保留。
   - 【副詞】：一律使用「蠻」，不可使用「滿」。

請直接輸出校正後的純文字結果。"""

# ==========================================
# 2. 核心處理邏輯
# ==========================================
def process_content(series, uploaded_file=None, manual_text=None):
    # 高精度配置：強迫 AI 進入「死板模式」
    generation_config = {
        "temperature": 0.2,  # 徹底取消創造力，只准聽寫
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }
    
    # 解除安全過濾，避免醫療內容被擋
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    model = genai.GenerativeModel(
        model_name=AI_MODEL_NAME,
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    
    # 處理手動文字
    if manual_text and not uploaded_file:
        prompt = f"影片系列：{series}\n請精準校正以下文字，絕對不可刪減內容：\n\n{manual_text}"
        response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
            
    # 處理影音檔案
    elif uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        if file_ext == 'txt':
            content = uploaded_file.read().decode("utf-8")
            prompt = f"影片系列：{series}\n請精準校正以下文字，不可刪減：\n\n{content}"
            response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
            for chunk in response:
                if chunk.text: yield chunk.text
        else:
            # 使用 UUID 產生英文檔名，解決 Windows 中文路徑錯誤
            temp_filename = f"temp_{uuid.uuid4().hex}.{file_ext}"
            temp_path = os.path.join(os.getcwd(), temp_filename)
            
            try:
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 上傳至 Google
                audio_file = genai.upload_file(path=temp_path)
                
                # 等待檔案就緒
                max_retries = 60
                retries = 0
                while audio_file.state.name == "PROCESSING" and retries < max_retries:
                    time.sleep(2)
                    audio_file = genai.get_file(audio_file.name)
                    retries += 1
                
                if audio_file.state.name != "ACTIVE":
                    yield f"❌ 檔案處理失敗：{audio_file.state.name}"
                    return

                # 強力命令：不准摘要
                prompt = (
                    f"這是「{series}」系列的影音。請執行『極致精準全文聽寫』。\n"
                    "1. 禁止摘要！禁止刪減！必須逐字逐句寫下來。\n"
                    "2. 內容長度必須與音軌相符，不可遺漏任何細節。\n"
                    "3. 嚴格執行校正規則，但以『內容完整』為最高優先。"
                )

                response = model.generate_content(
                    [audio_file, "\n\n", SYSTEM_INSTRUCTION, prompt],
                    request_options={"timeout": 600},
                    stream=True
                )
                for chunk in response:
                    if chunk.text: yield chunk.text
                
                # 刪除雲端檔案
                genai.delete_file(audio_file.name)

            except Exception as e:
                yield f"發生錯誤：{e}"
                
            finally:
                # 釋放檔案並刪除暫存
                time.sleep(1)
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

# ==========================================
# 3. Streamlit 介面
# ==========================================
def main():
    st.set_page_config(page_title="Sunny 影音校正器", layout="wide", page_icon="🎙️")
    st.title("🎙️ Sunny 營養師：影音轉文字與精準校正")

    with st.sidebar:
        st.header("⚙️ 設定")
        series = st.selectbox("影片系列", VIDEO_SERIES)
        st.divider()
        st.info(f"當前模型：{AI_MODEL_NAME}")
        st.write("💡 提示：如果內容不夠完整，請試著上傳「無背景音樂」的純人聲音檔。")

    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("📥 輸入內容")
        uploaded_file = st.file_uploader("上傳影音 (建議 MP3) 或文字檔", type=['mp3', 'm4a', 'wav', 'mp4', 'txt'])
        manual_text = st.text_area("或在此貼上原始逐字稿：", height=300)

    with col_out:
        st.subheader("📤 校正結果")
        if st.button("🚀 開始執行 (高精度模式)", use_container_width=True):
            if not MY_API_KEY:
                st.error("請先在 Secrets 設定 API Key")
            elif not uploaded_file and not manual_text:
                st.warning("請提供內容")
            else:
                placeholder = st.empty()
                full_text = ""
                
                try:
                    with st.status("AI 聽打校正中... 請勿關閉視窗", expanded=True) as status:
                        for chunk_text in process_content(series, uploaded_file, manual_text):
                            full_text += chunk_text
                            placeholder.text_area("✨ 即時生成內容：", full_text, height=600)
                        status.update(label="✅ 處理完成！", state="complete", expanded=False)
                    
                    st.download_button(
                        label="💾 下載完整逐字稿 (.txt)",
                        data=full_text,
                        file_name=f"{series}_精準校正.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"執行出錯：{e}")

if __name__ == "__main__":
    main()
