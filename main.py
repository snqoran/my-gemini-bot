import os
from fastapi import FastAPI, Request
import google.generativeai as genai

app = FastAPI()

# 1. إعداد مفتاح الـ API لـ Gemini من متغيرات البيئة
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

@app.post("/alexa")
async def alexa_skill(request: Request):
    # استقبال البيانات القادمة من خوادم أمازون أليكسا
    data = await request.json()
    request_type = data["request"]["type"]
    
    # حالة 1: عند فتح المهارة (أليكسا، افتحي جمناي)
    if request_type == "LaunchRequest":
        return speech_response("مرحباً بك في مساعدك البحثي المنزلي المدعوم بـ جمناي. أنا جاهز لأي سؤال أو بحث الآن.", should_close=False)
        
    # حالة 2: عندما يطرح المستخدم سؤالاً بحثياً أو عاماً
    elif request_type == "IntentRequest":
        intent_name = data["request"]["intent"]["name"]
        
        if intent_name == "AskGeminiIntent" or intent_name == "AMAZON.SearchIntent":
            # استخراج السؤال الذي نطقته أنت
            try:
                user_question = data["request"]["intent"]["slots"]["question"]["value"]
            except KeyError:
                return speech_response("عذراً، لم أسمع سؤالك بوضوح. هل يمكنك إعادته؟", should_close=False)
            
            # أمر بحثي عام ومباشر يناسب النطق الصوتي لأليكسا دون قيود جامعية
            prompt = f"أنت مساعد بحثي منزلي ذكي عبر أليكسا. أجب باختصار شديد ومباشر وبأسلوب يناسب النطق الصوتي على السؤال التالي: {user_question}"
            
            # إرسال السؤال لـ Gemini وجلب الإجابة
            response = model.generate_content(prompt)
            ai_answer = response.text
            
            return speech_response(ai_answer, should_close=True)
            
    # حالة 3: عند إغلاق المهارة
    elif request_type == "SessionEndedRequest":
        return {}

    return speech_response("عذراً، حدث خطأ في معالجة طلبك البحثي.", should_close=True)

# دالة مساعدة لتهيئة الرد الصوتي المتوافق مع أليكسا
def speech_response(output_text, should_close=True):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": output_text
            },
            "shouldEndSession": should_close
        }
    }
