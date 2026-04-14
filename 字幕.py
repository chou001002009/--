import streamlit as st
import google.generativeai as genai
import time
import os

# ==========================================
# 1. 頻道專屬設定
# ==========================================
VIDEO_SERIES = ["送你營養吃", "阿環格格出遊去", "阿環格格花錢去", "Vlog", "其他"]

SYSTEM_INSTRUCTION = """你現在是一位專業的 YouTube 影片逐字稿聽打與校正助理，專門處理「Sunny營養師」頻道的影片。
你的任務是：
1. 接收「音訊內容」或「原始文字」。
2. 根據以下「絕對校正規則」進行修正：
   - 【稱謂】：保留安媽、阿嬤、阿環等稱謂變體，不要強制統一。
   - 【台語】：還原為漢字（如：哩賀、安捏）。
   - 【名詞】：水氣->牙齒、各美心->鉻鎂鋅、糖流到臉->糖尿病、一瓶->一邊。
   - 【代名詞】：統一使用「你」與「他」。
   - 【程度詞】：一律使用「蠻」。
   - 【格式】：每行絕對不可超過 16 個字，不需標點符號，適合剪映文稿匹配。
   - 【開場】：若是「送你營養吃」系列，請確保開場白格式精確。

請直接輸出最終純文字字幕，不要有任何解釋。"""

# ==========================================
# 2. 核心功能
# ==========================================
def process_content(api_key, series, uploaded_file=None, manual_text=None):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # 模式 A：上傳了檔案
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        # 如果是文字檔
        if file_ext == 'txt':
            content = uploaded_file.read().decode("utf-8")
            prompt = f"影片系列：{series}\n請校正以下文字內容：\n\n{content}"
            response = model.generate_content([SYSTEM_INSTRUCTION, prompt])
            return response.text
        
        # 如果是影片或音訊
        else:
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            video_file = genai.upload_file(path=temp_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            prompt = f"這部影片屬於「{series}」系列，請生成校正後的逐字稿。"
            response = model.generate_content([video_file, "\n\n", SYSTEM_INSTRUCTION, prompt])
            
            os.remove(temp_path) # 清除暫存
            return response.text

    # 模式 B：手動輸入文字
    elif manual_text:
        prompt = f"影片系列：{series}\n請校正以下文字內容：\n\n{manual_text}"
        response = model.generate_content([SYSTEM_INSTRUCTION, prompt])
        return response.text
    
    return "未提供任何內容"

# ==========================================
# 3. 介面
# ==========================================
def main():
    st.set_page_config(page_title="Sunny 萬用校正器", layout="wide", page_icon="📝")
    st.title("📝 Sunny 營養師：影片/文字萬用校正器")

    with st.sidebar:
        api_key = st.text_input("輸入 Gemini API Key", type="password")
        series = st.selectbox("影片系列", VIDEO_SERIES)
        st.info("支援格式：MP4, MOV, MP3, TXT")

    # 建立分欄
    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("📥 內容輸入")
        uploaded_file = st.file_uploader("上傳影片或文字檔 (.txt)", type=['mp4', 'mov', 'mp3', 'm4a', 'txt'])
        
        st.write("--- 或 ---")
        manual_text = st.text_area("直接貼上逐字稿文字：", height=300)

    with col_out:
        st.subheader("📤 校正結果")
        if st.button("🚀 開始執行校正", use_container_width=True):
            if not api_key:
                st.error("請輸入 API Key")
            elif not uploaded_file and not manual_text:
                st.warning("請提供檔案或文字")
            else:
                with st.spinner("AI 正在工作中..."):
                    try:
                        result = process_content(api_key, series, uploaded_file, manual_text)
                        st.text_area("校正完成：", result, height=500)
                        st.success("完成！")
                    except Exception as e:
                        st.error(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
