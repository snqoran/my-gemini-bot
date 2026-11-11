# تشغيل Alexa مع Gemini Live — خطوات التجربة

## ما الذي يفعله البرنامج؟
- Alexa تلتقط الكلام وتحوله إلى نص عبر `AskGeminiIntent`.
- `/alexa` يتحقق من توقيع Amazon وتوقيت الطلب ومعرّف المهارة.
- يرسل السؤال النصي إلى `gemini-3.8-live` ويحصل على تفريغ النص للصوت الناتج.
- تعيد Alexa نطق النص، وتستمر جلسة المهارة لسؤال آخر.
- صفحة الاختبار الخاصة بـ Gemini Live على `/` باقية كما هي.

**مهم:** هذا ليس اتصالاً صوتياً مباشراً من ميكروفون Echo إلى Gemini. لكل سؤال طلب Alexa منفصل. لا تستخدم المهارة قبل إعداد التحقق. ولم يتم اختبارها فعلياً مع جهاز Alexa بعد.

## إعداد مهارة Alexa
1. افتح https://developer.amazon.com/alexa/console/ask
2. Create Skill > Custom > Provision your own > Start from Scratch، وحدد English (US).
3. في Build > Interaction Model > JSON Editor ألصق محتوى الملف `alexa-interaction-model-en-US.json` ثم Save Model و Build Model.
4. من صفحة المهارة انسخ **Skill ID** (يبدأ عادةً بـ `amzn1.ask.skill.`).
5. في Render > Environment أضف `ALEXA_SKILL_ID` وقيمته Skill ID؛ لا تغير `GEMINI_API_KEY` أو `TEST_CHAT_PIN`.
6. في Build > Endpoint اختر HTTPS، وضع:
   `https://my-gemini-bot-2-3dtq.onrender.com/alexa`
   واستخدم شهادة جهة إصدار موثوقة (trusted certificate authority).
7. بعد نشر Render، استخدم تبويب Test في Developer Console لتجربة “open gemini helper”، ثم “ask what is the weather on Mars”.
8. إذا ظهرت أخطاء، راجع Render Logs دون تصوير أو إرسال مفاتيح API.

## التحقق والحماية
- تُرفض الطلبات إذا لم يُضبط `ALEXA_SKILL_ID` أو فشل التوقيع أو انتهى توقيت الطلب.
- يستخدم الكود مفوض التحقق الرسمي من Amazon، مع ترويسة `Signature-256`.
- صفحة الاختبار النصي والصوتي محمية بـ `TEST_CHAT_PIN`، ولا ينبغي مشاركة الرمز.
- إعدادات API Key تبقى في Render، وليست جزءاً من المستودع العام.

## حدود مهمة
- مهلة رد Alexa نحو 8 ثوانٍ إجمالاً، لهذا وضعت مهلة لاستدعاء Gemini Live. إذا تأخر الاتصال تعطي Alexa رسالة خطأ قصيرة دون أن ينفذ الطلب لوقت غير محدود.
- استضافة Render المجانية تنام بعد الخمول، ويمكن أن يستغرق الاستيقاظ نحو دقيقة. قد تفشل مهارة Alexa في أول استدعاء حتى لو نجح الاختبار في المتصفح.
- الإنجليزية (US) لغة نموذج التفاعل التجريبي؛ التعرف على السؤال العربي بواسطة Alexa غير مضمون بهذه الإعدادات. يمكن أن يكون جواب Gemini بالعربية إذا وصل نص عربي.
- إذا لم يُرجع Gemini Live تفريغاً نصياً للرد الصوتي، لن تحصل Alexa على جواب نصي، وسيظهر رد اعتذار.
- حالة التطبيق في Render “Live” تثبت تشغيل الخادم فقط، ولا تثبت نجاح Skill أو إتاحة Gemini في كل مرة.
- لم نعدّل أي ملف في Masa AI.

المصادر:
- https://developer.amazon.com/en-US/docs/alexa/custom-skills/host-a-custom-skill-as-a-web-service.html
- https://developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html
- https://developer.amazon.com/en-US/docs/alexa/custom-skills/request-and-response-json-reference.html
