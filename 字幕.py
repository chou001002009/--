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
1. 聽取影片音訊並轉成文字。
2. 根據以下「絕對校正規則」進行修正：
   - 【稱謂】：保留安媽、阿嬤、阿環等稱謂變體，不要強制統一。
   - 【台語】：還原為漢字（如：哩賀、安捏）。
   - 【名詞】：水氣->牙齒、各美心->鉻鎂鋅、糖流到臉->糖尿病、一瓶->一邊。
   - 【代名詞】：統一使用「你」與「他」。
   - 【程度詞】：一律使用「蠻」。
   - 【格式】：每行絕對不可超過 16 個字，不需標點符號，適合剪映文稿匹配。
   - 【開場】：若是「送你營養吃」系列，請確保開場白格式精確（哈囉各位朋友大家好...我是安媽...）。

請直接輸出最終純文字字幕，不要有任何解釋或標題。"""

# ==========================================
# 2. 功能函式
# ==========================================
def process_video_with_gemini(api_key, file_path, series):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # 上傳檔案到 Google 伺服器 (暫存)
    st.info("正在上傳影片至 AI 伺服器進行分析...")
    video_file = genai.upload_file(path=file_path)
    
    # 等待檔案處理完成
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        raise ValueError("影片處理失敗")

    # 執行生成
    prompt = f"這部影片屬於「{series}」系列，請幫我生成校正後的逐字稿。"
    response = model.generate_content(
        [video_file, "\n\n", SYSTEM_INSTRUCTION, prompt],
        request_options={"timeout": 600}
    )
    
    # 清除伺服器上的檔案 (選用)
    genai.delete_file(video_file.name)
    
    return response.text

# ==========================================
# 3. Streamlit 介面
# ==========================================
def main():
    st.set_page_config(page_title="Sunny 影片自動校正器", layout="wide")
    st.title("🎥 Sunny 營養師：影片 -> 逐字稿自動校正")
    
    with st.sidebar:
        api_key = st.text_input("輸入 Gemini API Key", type="password")
        series = st.selectbox("影片系列", VIDEO_SERIES)
        st.divider()
        st.write("建議影片長度在 10 分鐘內以獲得最佳速度。")

    uploaded_file = st.file_uploader("請上傳影片 (MP4, MOV, m4a, MP3)", type=['mp4', 'mov', 'm4a', 'mp3'])

    if uploaded_file is not None:
        if st.button("🚀 開始分析並生成字幕"):
            if not api_key:
                st.error("請先輸入 API Key")
                return
            
            try:
                # 1. 儲存上傳的檔案到本地臨時目錄
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                with st.spinner("AI 正在聽取影片並校正中... 請給它一點時間 (約需影片長度的 1/4 時間)"):
                    result = process_video_with_gemini(api_key, temp_path, series)
                    
                    st.success("校正完成！")
                    st.text_area("校正後的逐字稿 (可直接複製到剪映)", result, height=500)
                
                # 2. 刪除本地臨時檔
                os.remove(temp_path)
                
            except Exception as e:
                st.error(f"錯誤：{e}")

if __name__ == "__main__":
    main()