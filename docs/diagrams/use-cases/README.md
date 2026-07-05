# مخططات حالات الاستخدام والتسلسل - LeadScope AI

تم إنشاء هذه المخططات من قراءة الكود في `apps/api` و `apps/web`، وليس من افتراضات خارجية.

## ملفات حالات الاستخدام

- `overall-use-case.puml`: نظرة عامة على الأدوار والوظائف الرئيسية للنظام.
- `roles/account-owner-use-case.puml`: حالات استخدام دور `account_owner`.
- `roles/admin-use-case.puml`: حالات استخدام دور `admin`.
- `roles/manager-use-case.puml`: حالات استخدام دور `manager`.
- `roles/member-use-case.puml`: حالات استخدام دور `member`.
- `modules/authentication-use-case.puml`: المصادقة، التسجيل، الرموز، والتحقق من الجلسة.
- `modules/leads-discovery-use-case.puml`: اكتشاف العملاء المحتملين، البحث، إدارة العملاء، والأدلة.
- `modules/team-admin-use-case.puml`: الفريق، الإعدادات، الإدارة، وسجلات التدقيق.
- `modules/billing-exports-use-case.puml`: الفوترة، الاشتراكات، الفواتير، الاستخدام، والتصدير.
- `modules/outreach-use-case.puml`: مسودات التواصل وتعديلها وإرسالها.
- `ai-use-case.puml`: تحليل AI، مساعد المبيعات، جلسات المحادثة، وإدارة قوالب AI.

## ملفات التسلسل

- `../sequences/login-sequence.puml`: تسلسل تسجيل الدخول.
- `../sequences/lead-discovery-sequence.puml`: تسلسل إنشاء وتشغيل وظيفة اكتشاف.
- `../sequences/ai-analysis-sequence.puml`: تسلسل توليد تحليل AI لعميل محتمل.
- `../sequences/assistant-chat-sequence.puml`: تسلسل محادثة مساعد المبيعات عبر SSE.
- `../sequences/outreach-sequence.puml`: تسلسل إنشاء مسودة تواصل.
- `../sequences/billing-export-sequence.puml`: تسلسل تصدير العملاء المحتملين مع حدود الفوترة.

## ملاحظات الدقة

- الأدوار الفعلية من الكود: `account_owner`, `admin`, `manager`, `member`.
- تم حصر actors في المخططات على أدوار النظام المصادق عليها فقط، بدون actors عامة مثل زائر أو مستخدم مصادق عام.
- أي حالة تحمل `INFERRED` تعني أنها مبنية على route أو UI موجود، لكن تفاصيلها الداخلية ليست موثقة بوضوح كعملية backend مستقلة.
- لا توجد أدوار مثل Doctor أو Patient أو Customer في الكود الذي تم فحصه.
