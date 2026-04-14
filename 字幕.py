import streamlit as st
import google.generativeai as genai
import time
import os

# ==========================================
# 0. 系統核心設定
# ==========================================
# ⚠️ 這是你的真實金鑰，請務必確保你的 GitHub 倉庫是「私密 (Private)」的！
MY_API_KEY = "AIzaSyBnBZLt4PZg92PgY5kkt5LE7imjaZDZKi4"

# 目前預設使用 "gemini-1.5-pro" (旗艦版，最聰明、最精準)
# 如果你覺得 Pro 版速度有點慢，可以隨時改成 "gemini-1.5-flash" (極速版)
AI_MODEL_NAME = "gemini-1.5-pro" 

# 讓系統直接吃你的金鑰
if MY_API_KEY:
    genai.configure(api_key=MY_API_KEY)

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
# 2. 核心處理邏輯 (串流輸出)
# ==========================================
def process_content(series, uploaded_file=None, manual_text=None):
    model = genai.GenerativeModel(AI_MODEL_NAME)
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        # 處理純文字檔
        if file_ext == 'txt':
            content = uploaded_file.read().decode("utf-8")
            prompt = f"影片系列：{series}\n請校正以下逐字稿文字：\n\n{content}"
            response = model.generate_content([SYSTEM_INSTRUCTION, prompt], stream=True)
            for chunk in response:
                if chunk.text: yield chunk.text
                
        # 處理音軌或影片檔
        else:
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 上傳至 Google 伺服器
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
            
            # 即時輸出文字
            for chunk in response:
                if chunk.text: yield chunk.text
                
            # 清理暫存檔案
            os.remove(temp_path)
            genai.delete_file(audio_file.name)
            
    # 處理手動輸入
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
        st.write(f"當前使用模型：**{AI_MODEL_NAME}**")
        st.write("💡 提示：上傳 **MP3** 或 **M4A** 音檔速度最快。")

    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("📥 輸入內容")
        uploaded_file = st.file_uploader(
            "上傳音軌、影片或文字檔", 
            type=['mp3', 'm4a', 'wav', 'mp4', 'mov', 'txt']
        )
        
        # 檔案載入成功提示
        if uploaded_file is not None:
            st.success(f"✅ 檔案「{uploaded_file.name}」已成功載入！")

        st.write("--- 或 ---")
        manual_text = st.text_area("在此貼上原始文字：", height=300)

    with col_out:
        st.subheader("📤 校正結果")
        if st.button("🚀 開始執行", use_container_width=True):
            # 這裡已經完美修復！
            if not MY_API_KEY:
                st.error("⚠️ 錯誤：你還沒有在程式碼第 10 行輸入真實的 API Key！")
            elif not uploaded_file and not manual_text:
                st.warning("⚠️ 請先提供檔案或貼入文字")
            else:
                status_msg = st.info("正在連線至 AI 大腦，請稍候...")
                try:
                    result_box = st.empty()
                    full_text = ""
                    
                    # 執行並即時顯示結果
                    for chunk_text in process_content(series, uploaded_file, manual_text):
                        status_msg.empty() 
                        full_text += chunk_text
                        result_box.text_area("✨ 正在即時生成中 (可隨時預覽)...", full_text, height=500)
                        
                    st.balloons()
                    st.success("🎉 處理完畢！可直接全選複製到剪映。")
                    
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
