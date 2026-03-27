import json
from typing import Dict, Optional
from pydantic import BaseModel, Field

# 嘗試引入 Google Generative AI
try:
    import google.generativeai as genai
except ImportError:
    genai = None

class ReadmeSchema(BaseModel):
    """定義 README.md 結構化輸出的 Schema"""
    project_name: str = Field(..., description="專案名稱，需簡潔有力")
    architecture: str = Field(..., description="高階技術架構與邏輯說明（可包含語言、框架、工具等）")
    quick_start: str = Field(..., description="如何安裝與啟動此項目的指令與步驟，使用 Markdown 的 bash 語法格式化。請保持精簡，切勿無意義地重複。")
    logic_formula: str = Field(..., description="一個數學或邏輯公式，用以專業且客觀地展現專案核心邏輯的抽象概念或演算法複雜度。例如: $$O(N \\log N)$$")

class ProjectAnalyzer:
    """負責串接 Gemini 進行代碼邏輯分析，並產出結構化 README。"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if not genai:
            raise ImportError("缺漏套件！請執行 `pip install google-generativeai pydantic`。")
        if not self.api_key:
            raise ValueError("未提供 GEMINI_API_KEY。請設定環境變數或確保傳入有效密鑰。")
        
        genai.configure(api_key=self.api_key)
        # 推薦使用 gemini-1.5-pro 或 gemini-2.5-pro 分析程式碼邏輯
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.excuse_model = genai.GenerativeModel("gemini-2.5-flash")

    def analyze_and_generate(self, tree: str, files_content: Dict[str, str]) -> ReadmeSchema:
        """解析專案結構與代碼，並呼叫 LLM 產出符合 Schema 的物件"""
        
        # 將檔案內容轉為易讀字串
        files_str = "\n".join([f"--- File: {path} ---\n{content}\n" for path, content in files_content.items()])

        system_prompt = (
            "你是一個資深的系統架構師與技術主導者，具備卓越的技術洞察力與嚴謹的態度。\n"
            "你的任務是分析一份專案的目錄結構與部分核心程式碼，然後自動對結構與意圖進行逆向工程。\n"
            "請嚴格依據定義的 JSON Schema 輸出，文字風格必須保持「專業、輕鬆且客觀、用淺顯易懂的文字介紹工具的功能與使用方法」。\n"
            "【強烈要求】你生成的 JSON 結構必須完整包含：project_name, architecture, quick_start, logic_formula 這四個欄位。如果原始碼沒有提供明顯的架構或公式，你要主動根據程式碼特徵推斷並填寫，絕對不可遺漏欄位。\n"
            "【重要】在產生 logic_formula 時，對於字串內的數學公式請使用雙錢號 $$ 包覆（如 $$O(N)$$），絕對禁止使用單一反斜線，以避免造成 JSON 解析失敗。\n\n"
            "【Few-shot Example 語氣參考】\n"
            "Architecture: 本專案採用 Python FastAPI 框架搭配 Pydantic 進行資料驗證，實現了輕量且高效的微服務架構，並確保了嚴格的型別安全。\n"
            "Logic Formula: 表示核心模組的預期時間複雜度。\n"
        )

        user_prompt = f"""
        系統指引: {system_prompt}
        
        以下是目標專案的目錄樹：
        {tree}
        
        以下是部分核心檔案內容：
        {files_str}
        
        【強制要求】
        1. 請務必回傳合法的 JSON 字串（不要使用 ```json 或任何 Markdown 修飾），格式必須正好包含這四個 key。
        2. 每個欄位的說明請保持精準且具體，避免任何冗長的廢話或重複的句子。
        
        期望格式：
        {{
            "project_name": "字串",
            "architecture": "字串",
            "quick_start": "字串",
            "logic_formula": "字串"
        }}
        """

        # 使用 Gemini Structured Outputs 功能確保返回符合 JSON Schema 的資料結構
        response = self.model.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0,
                max_output_tokens=8192
            )
        )
        
        if not response.text:
            raise ValueError("LLM 未返回預期的解析結果")
            
        raw_text = response.text.strip()
        # 防呆機制：去除可能包含的 Markdown ```json 修飾
        if raw_text.startswith("```"):
            lines = raw_text.strip("`").split("\n")
            if lines[0].lower() == "json":
                lines = lines[1:]
            raw_text = "\n".join(lines).strip()

        try:
            result = ReadmeSchema.model_validate_json(raw_text)
        except Exception as e:
            raise ValueError(f"JSON 結構驗證或解析失敗！\n原始 LLM 輸出為: {raw_text}\n錯誤詳情: {e}")
            
        return result

    def get_ai_excuse(self, error_msg: str) -> str:
        """若發生不預期錯誤，呼叫 LLM 產生幽默的錯誤分析，這也是一種 fallback。"""
        try:
            prompt = (
                "你是一個專業的系統維運工程師，正在向使用者解釋為什麼剛才的系統分析任務發生了以下錯誤。\n"
                "請用簡明扼要、專業客觀的語氣說明異常原因：\n\n"
                f"原始錯誤: {error_msg}"
            )
            res = self.excuse_model.generate_content(prompt)
            return res.text or "未知的 AI 沉默錯誤..."
        except Exception:
            return f"連 AI 錯誤解釋器也罷工了... 原始錯誤為: {error_msg}"
