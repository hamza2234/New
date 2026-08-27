# تقرير هندسة عكسية تعليمية آمنة لتطبيق soso

هذا التقرير يشرح تحليلاً ثابتاً تعليمياً للملف:

`artifacts/soso/soso.apk`

الهدف هنا فهم بنية تطبيق Android من الخارج بدون تعديل التطبيق، أو تجاوز حماية، أو استخراج أسرار، أو إعادة توقيع/نشر نسخة معدلة.

## حدود التحليل

ما تم عمله:

- قراءة metadata من `AndroidManifest.xml`.
- قراءة معلومات XAPK من `manifest.json`.
- تصنيف الصلاحيات المهمة.
- توضيح معنى split APKs بشكل تعليمي.

ما لم يتم عمله:

- لم يتم كسر حماية التطبيق أو تجاوز تسجيل الدخول.
- لم يتم تعديل APK أو إعادة توقيعه.
- لم يتم استخراج مفاتيح، tokens، بيانات مستخدمين، أو endpoints حساسة.
- لم يتم نشر أو بناء نسخة معدلة من التطبيق.

## معلومات عامة

- اسم الملف: `soso.apk`
- الحزمة: `com.instagram.android`
- الإصدار: `443.0.0.48.82`
- رقم الإصدار: `384910608`
- أقل إصدار Android: API 28
- Target SDK: API 36
- SHA-256 للملف: `75280ab7c07dd760d7eb9cb2da50cb9de83676a5d85ed7449d03a57c0bdfffe4`

## ملاحظة عن XAPK و split APK

تم تنزيل التطبيق في الأصل كحزمة XAPK:

- `soso.xapk`
- `soso.apk` وهو base APK بعد الاستخراج.
- `config.xxhdpi.apk` وهو split APK خاص بكثافة شاشة xxhdpi.

تطبيقات Android الحديثة قد لا تكون APK واحداً فقط. أحياناً تكون مقسمة إلى:

- base APK: يحتوي الكود والموارد الأساسية.
- split APKs: تحتوي موارد خاصة بلغة، دقة شاشة، أو معمارية جهاز.

لذلك عند التثبيت اليدوي، قد تحتاج تثبيت كل ملفات APK التابعة للحزمة معاً، أو استخدام ملف XAPK عبر أداة تدعم XAPK.

## حجم السطح الظاهر من الـmanifest

من قراءة الـmanifest:

- عدد الصلاحيات: 76
- Activities: 512
- Services: 100
- Receivers: 61
- Providers: 21
- Features: 13

هذه الأرقام طبيعية نسبياً لتطبيق كبير ومعقد، لأنها تعكس وجود واجهات كثيرة، خدمات خلفية، إشعارات، مشاركة، كاميرا، رسائل، وميزات متعددة.

## تصنيف الصلاحيات المهمة

### الشبكة والاتصال

- `android.permission.INTERNET`
- `android.permission.ACCESS_NETWORK_STATE`
- `android.permission.CHANGE_NETWORK_STATE`
- `android.permission.ACCESS_LOCAL_NETWORK`

هذه الصلاحيات تسمح للتطبيق بالاتصال بالإنترنت، معرفة حالة الشبكة، وبعض التفاعل مع الشبكات المحلية.

### الكاميرا والمايك والوسائط

- `android.permission.CAMERA`
- `android.permission.RECORD_AUDIO`
- `android.permission.READ_MEDIA_IMAGES`
- `android.permission.READ_MEDIA_VIDEO`
- `android.permission.READ_MEDIA_VISUAL_USER_SELECTED`
- `android.permission.ACCESS_MEDIA_LOCATION`

هذه مرتبطة بالتصوير، القصص، الريلز، رفع الصور والفيديو، والوصول المحدود أو الكامل للوسائط حسب إصدار Android وإعدادات المستخدم.

### الموقع

- `android.permission.ACCESS_FINE_LOCATION`

تستخدم عادةً لميزات الموقع، الوسوم الجغرافية، أو تحسين بعض الخدمات المعتمدة على الموقع بعد موافقة المستخدم.

### الحسابات والهوية

- `android.permission.AUTHENTICATE_ACCOUNTS`
- `android.permission.MANAGE_ACCOUNTS`
- `android.permission.GET_ACCOUNTS`
- `android.permission.USE_CREDENTIALS`
- `android.permission.CREDENTIAL_MANAGER_SET_ALLOWED_PROVIDERS`

هذه صلاحيات مرتبطة بتكامل الحسابات أو مزودي الاعتماد على Android. وجودها لا يعني تلقائياً أن التطبيق يستطيع الوصول لكل شيء بدون موافقة النظام والمستخدم.

### الإشعارات والخدمات الخلفية

- `android.permission.POST_NOTIFICATIONS`
- `android.permission.RECEIVE_BOOT_COMPLETED`
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_CAMERA`
- `android.permission.FOREGROUND_SERVICE_MICROPHONE`
- `android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK`
- `android.permission.FOREGROUND_SERVICE_DATA_SYNC`

هذه تساعد التطبيق على تشغيل إشعارات، مزامنة، مكالمات/كاميرا/مايك، وتشغيل خدمات foreground عندما يسمح Android بذلك.

### البلوتوث و NFC

- `android.permission.BLUETOOTH`
- `android.permission.BLUETOOTH_CONNECT`
- `android.permission.NFC`

هذه تستخدم للميزات التي تحتاج اتصالاً قريباً أو تكاملات أجهزة.

### الدفع والإعلانات والقياس

- `com.android.vending.BILLING`
- `com.google.android.gms.permission.AD_ID`
- `android.permission.ACCESS_ADSERVICES_AD_ID`
- `android.permission.ACCESS_ADSERVICES_ATTRIBUTION`

هذه مرتبطة بالدفع داخل التطبيق، معرف الإعلانات، وقياس الإسناد الإعلاني حسب سياسات Android وGoogle.

## قراءة تعليمية لبنية التطبيق

من منظور هندسة عكسية آمنة:

1. ابدأ دائماً بالـmanifest لأنه يوضح:
   - package name
   - components
   - permissions
   - deep links
   - providers/services/receivers
2. افحص هل التطبيق APK واحد أم split APK.
3. صنف الصلاحيات حسب الوظيفة بدلاً من اعتبارها كلها خطراً.
4. لا تستنتج سلوكاً حساساً من مجرد وجود صلاحية؛ السلوك الحقيقي يحتاج مراقبة تشغيلية بإذن وعلى جهاز اختبار.
5. لا تعدل APK لتجاوز حماية أو تسجيل دخول؛ هذا خارج التحليل التعليمي الآمن.

## أوامر آمنة مستخدمة للتحقق

```bash
file artifacts/soso/soso.apk
sha256sum artifacts/soso/soso.apk
```

وتم استخدام `apkutils2` لقراءة metadata من الـmanifest بدون تفكيك أو تعديل التطبيق.
