import os
import hmac
import logging
import asyncio
import base64
import io
import wave
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

app = FastAPI(title="Gemini Alexa Bridge")
logger = logging.getLogger(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1alpha")) if api_key else None
MODEL_NAME = "gemini-3.8-flash"

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تجربة Gemini</title><style>
body{font-family:system-ui,sans-serif;max-width:650px;margin:40px auto;padding:0 16px;background:#f7f8fb;color:#172033}
main{background:white;padding:24px;border-radius:18px;box-shadow:0 4px 22px #0001}
input,textarea,button{box-sizing:border-box;width:100%;padding:12px;border-radius:9px;margin:9px 0;font:inherit}
input,textarea{border:1px solid #aaa}button{background:#1769d2;color:white;border:0;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#566}
</style></head><body><main><h2>تجربة Gemini</h2>
<p>هذه صفحة اختبار خاصة، وليست مهارة Alexa النهائية.</p>
<label>رمز الاختبار (TEST_CHAT_PIN)</label><input id="pin" type="password" autocomplete="off">
<label>سؤالك</label><textarea id="q" rows="3" maxlength="500" placeholder="اكتب سؤالك هنا"></textarea>
<button id="send">إرسال نصياً</button><button id="live">تجربة Gemini Live بالصوت</button><pre id="out" role="status"></pre><audio id="player" controls style="width:100%;display:none"></audio>
<small>إذا لم يتم إعداد TEST_CHAT_PIN في Render، فالمحادثة معطلة لحماية مفتاح Gemini.</small></main>
<script>
document.getElementById('send').onclick=async()=>{
 const out=document.getElementById('out');out.textContent='جارٍ إرسال السؤال...';
 try{
 const r=await fetch('/test-chat',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({pin:document.getElementById('pin').value,question:document.getElementById('q').value})});
 const data=await r.json();out.textContent=r.ok?data.answer:(data.detail||'حدث خطأ');
 }catch(e){out.textContent='تعذر الاتصال بالخادم';}
};

document.getElementById('live').onclick=async()=>{
 const out=document.getElementById('out'), player=document.getElementById('player');
 out.textContent='جارٍ تجربة Gemini Live...';player.style.display='none';
 try {
 const r=await fetch('/test-live',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({pin:document.getElementById('pin').value,question:document.getElementById('q').value})});
 const data=await r.json();
 if(!r.ok){out.textContent=data.detail||'تعذرت التجربة';return;}
 out.textContent=data.answer||'تم استلام الصوت، اضغط تشغيل.';
 if(data.audio){player.src='data:audio/wav;base64,'+data.audio;player.style.display='block';}
 }catch(e){out.textContent='تعذر الاتصال بالخادم';}
};
</script></body></html>"""

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home():
    return PAGE

@app.get("/health")
async def health():
    return {"status": "ok", "gemini_key_configured": bool(api_key)}

class ChatInput(BaseModel):
    pin: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=500)

@app.post("/test-chat", include_in_schema=False)
async def test_chat(body: ChatInput):
    configured_pin = os.environ.get("TEST_CHAT_PIN", "")
    if not configured_pin:
        raise HTTPException(status_code=503, detail="أضف TEST_CHAT_PIN في Environment داخل Render أولاً")
    if not hmac.compare_digest(body.pin.encode(), configured_pin.encode()):
        raise HTTPException(status_code=401, detail="رمز الاختبار غير صحيح")
    if not api_key:
        raise HTTPException(status_code=503, detail="مفتاح Gemini غير مُعدّ في الخادم")
    try:
        answer = client.models.generate_content(
            model=MODEL_NAME,
            contents="أجب باختصار وبوضوح وبنفس لغة السؤال: " + body.question
        ).text
        return {"answer": answer or "لم أستلم إجابة نصية"}
    except Exception:
        logger.exception("Gemini request failed")
        raise HTTPException(status_code=502, detail="تعذر الاتصال بـ Gemini. راجع Render Logs.")


async def live_answer(question: str):
    pcm = bytearray()
    transcript = []
    async with client.aio.live.connect(
        model="gemini-3.8-live",
        config={"response_modalities": ["AUDIO"], "output_audio_transcription": {}},
    ) as session:
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": "أجب باختصار شديد وبنفس اللغة: " + question}]},
            turn_complete=True,
        )
        async for event in session.receive():
            content = event.server_content
            if content:
                if content.output_transcription and content.output_transcription.text:
                    transcript.append(content.output_transcription.text)
                if content.model_turn:
                    for part in content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            pcm.extend(part.inline_data.data)
                            if len(pcm) > 3000000:
                                raise ValueError("Audio too large")
                if content.turn_complete:
                    break
    if not pcm:
        raise ValueError("No audio returned")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(bytes(pcm))
    return {"answer": "".join(transcript), "audio": base64.b64encode(buffer.getvalue()).decode("ascii")}


@app.post("/test-live", include_in_schema=False)
async def test_live(body: ChatInput):
    configured_pin = os.environ.get("TEST_CHAT_PIN", "")
    if not configured_pin:
        raise HTTPException(status_code=503, detail="رمز الاختبار غير معد")
    if not hmac.compare_digest(body.pin.encode(), configured_pin.encode()):
        raise HTTPException(status_code=401, detail="رمز الاختبار غير صحيح")
    if not api_key:
        raise HTTPException(status_code=503, detail="مفتاح Gemini غير معد")
    try:
        return await asyncio.wait_for(live_answer(body.question), timeout=35)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="انتهت مهلة Gemini Live")
    except Exception:
        logger.exception("Gemini Live request failed")
        raise HTTPException(status_code=502, detail="تعذرت تجربة Gemini Live؛ راجع سجلات Render.")


@app.post("/alexa")
async def alexa_skill(request: Request):
    # تنبيه: يجب التحقق من توقيع Amazon قبل استخدام هذا المسار في مهارة حقيقية.
    try:
        data = await request.json()
        req = data["request"]
        request_type = req["type"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="طلب Alexa غير صالح")

    if request_type == "LaunchRequest":
        return speech_response("مرحباً بك في مساعدك البحثي المنزلي المدعوم بـ جمناي. أنا جاهز لأي سؤال.", False)
    if request_type == "SessionEndedRequest":
        return {}
    if request_type == "IntentRequest":
        intent = req.get("intent", {})
        if intent.get("name") in ("AskGeminiIntent", "AMAZON.SearchIntent"):
            question = (intent.get("slots", {}).get("question") or {}).get("value")
            if not question:
                return speech_response("عذراً، لم أسمع سؤالك بوضوح. أعد السؤال.", False)
            if not api_key:
                return speech_response("خدمة Gemini غير مهيأة حالياً.")
            try:
                answer = client.models.generate_content(
                    model=MODEL_NAME,
                    contents="أنت مساعد منزلي عبر أليكسا. أجب باختصار مناسب للصوت: " + question
                ).text
                return speech_response(answer or "لم أستلم إجابة.")
            except Exception:
                logger.exception("Alexa Gemini request failed")
                return speech_response("عذراً، تعذر الوصول إلى Gemini الآن.")
    return speech_response("عذراً، لم أفهم الطلب.")

def speech_response(output_text, should_close=True):
    return {"version": "1.0", "response": {
        "outputSpeech": {"type": "PlainText", "text": output_text},
        "shouldEndSession": should_close
    }}
