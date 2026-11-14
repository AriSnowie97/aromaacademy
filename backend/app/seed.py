from datetime import timedelta
import uuid

from sqlalchemy.orm import Session

from .aroma_service import reindex_lesson_kb
from .config import get_settings
from .models import (
    AromaClip,
    Consent,
    Course,
    Lesson,
    LessonVersion,
    ModuleTest,
    Step,
    Subscription,
    Tariff,
    User,
    utcnow,
)


settings = get_settings()

MODULES_SPEC = [
    (1, "Ефірна олія (основи)", 7, "learn", "basic", False, "Як влаштовані ефірні олії, чим вони відрізняються від жирних і як потрапляють в організм."),
    (2, "Якість ефірних олій", 8, "learn", "basic", False, "Стандарт чистоти CPTG, етапи перевірки кожної партії та правила зберігання флаконів."),
    (3, "Безпека", 10, "learn", "basic", True, "Обов'язковий модуль: розведення, фототоксичність, чутливі зони, діти та червоні прапори."),
    (4, "Способи застосування", 8, "learn", "standard", False, "Інгаляція, дифузори, нанесення на шкіру, базові олії та створення власних сумішей."),
    (5, "Базова аптечка", 10, "learn", "standard", False, "Ключові олії на щодень: лаванда, лимон, м'ята, чайне дерево, ладан та базові суміші."),
    (6, "Емоції та аромати", 8, "learn", "standard", False, "Зв'язок нюхової системи з емоційним станом і ритуали підтримки через аромати."),
    (7, "Олії в системі велнесу", 9, "learn", "standard", False, "Піраміда велнесу, сон, рух, стрес-менеджмент і щоденні здорові звички."),
    (8, "Від користувача до рекомендатора", 8, "share", "personal", False, "Етика рекомендатора, межі відповідальності та коректна комунікація про олії."),
    (9, "Як говорити про олії", 9, "share", "personal", False, "Живі історії замість тиску, відповіді на типові заперечення та чесні пояснення."),
    (10, "Зустрічі та класи", 10, "share", "personal", False, "Структура ароматного класу, підготовка семплів і проведення першої зустрічі."),
    (11, "Супровід клієнта", 9, "share", "personal", False, "Перші 30 днів з набором, персональний фоллоу-ап і безпечне ведення новачка."),
    (12, "Ароматне ком'юніті", 9, "share", "personal", False, "Довгострокова підтримка спільноти, командні ритуали та навчання партнерів."),
]

MODULE_4_TITLES = [
    "Три шляхи до організму",
    "Вдихання без приладів",
    "Дифузори",
    "Нанесення на шкіру",
    "Базові олії",
    "Косметика, ванна, спреї і дім",
    "Як скласти власну суміш",
    "Підсумок і практичне завдання",
]

AROMA_CLIPS_SPEC = [
    (1, "1. Ефірні олії: основи", 11, "1.1"),
    (2, "2. Стандарт CPTG (коротко)", 8, "2.5"),
    (3, "3. Правила безпеки", 11, "3.1"),
    (4, "4. Індивідуальний підхід", 10, "уточнити"),
    (5, "5. З чого почати", 10, "5.1"),
    (6, "6. Олії у повсякденному житті", 9, "5.6"),
    (7, "7. Основні способи використання", 11, "4.1–4.3"),
    (8, "8. Дозування і крапельний підхід", 10, "3.2"),
    (9, "9. Леткість і давня традиція", 9, "1.5"),
    (10, "10. Чому олії такі особливі", 12, "1.1"),
    (11, "11. CPTG: як перевіряють кожну краплю", 16, "2.4"),
    (12, "12. Коли аромат неприємний", 9, "6.3"),
    (13, "13. Вісім поширених помилок", 14, "уточнити"),
    (14, "14. З чим звертаються до олій", 6, "уточнити"),
]


def _default_lesson_title(mod_num: int, idx: int, total: int) -> str:
    if mod_num == 4 and idx <= len(MODULE_4_TITLES):
        return MODULE_4_TITLES[idx - 1]
    if idx == total:
        if mod_num == 8:
            return "Кодекс рекомендатора, підсумок і завдання"
        return "Підсумок і практичне завдання"
    if mod_num == 1 and idx == 1:
        return "Що таке ефірна олія"
    if mod_num == 3 and idx == 1:
        return "Базові правила безпеки з першої краплі"
    if mod_num == 5 and idx == 1:
        return "З чого почати знайомство з базовою аптечкою"
    return f"Урок {mod_num}.{idx}"


def _build_rich_lesson_1_1_steps(lesson_id: str) -> list[dict]:
    return [
        {
            "order": 1,
            "type": "card",
            "is_key": False,
            "source_ref": "План Наталії Котелянської · Модуль 1, Відео 1.1",
            "payload": {
                "title": "Природний захист рослин у кожній краплі",
                "body": (
                    "Ефірна олія — це висококонцентрована летка ароматична сполука, яку рослина "
                    "виробляє для захисту, відновлення та приваблення запилювачів. "
                    "На відміну від жирних рослинних олій (оливкової чи кокосової), ефірна олія "
                    "не залишає жирного сліду й швидко випаровується."
                ),
                "clip_id": "clip_1",
                "badge": "Картка знання · Відео 1.1",
            },
        },
        {
            "order": 2,
            "type": "card",
            "is_key": False,
            "source_ref": "План Наталії Котелянської · Модуль 1, Відео 1.1",
            "payload": {
                "title": "Чому концентрація має значення",
                "body": (
                    "В одній краплі ефірної олії м'яти перцевої міститься еквівалент десятків чашок "
                    "м'ятного чаю за вмістом ароматичних молекул. Саме тому в ароматерапії працює "
                    "принцип «менше — краще»: починаємо з 1 краплі та прислухаємося до реакції."
                ),
                "badge": "Картка знання",
            },
        },
        {
            "order": 3,
            "type": "choice",
            "is_key": False,
            "source_ref": "Модуль 1, Відео 1.1",
            "payload": {
                "question": "Чим ефірна олія принципово відрізняється від жирної (базової) олії?",
                "options": [
                    "Вона містить леткі ароматичні сполуки і не залишає жирного сліду",
                    "Її отримують виключно з насіння методом холодного віджиму",
                    "Вона не має запаху й не випаровується",
                    "Її використовують лише для смаження",
                ],
                "correct_index": 0,
                "explanation": "Ефірні олії складаються з летких ароматичних молекул і повністю випаровуються без жирного сліду.",
            },
        },
        {
            "order": 4,
            "type": "true_false",
            "is_key": False,
            "source_ref": "Модуль 1, Відео 1.1",
            "payload": {
                "statement": "Щоб отримати виразний ароматний ефект, потрібно одразу наносити 10–15 крапель олії.",
                "correct": False,
                "explanation": "Ефірні олії надзвичайно концентровані: зазвичай достатньо 1–2 крапель.",
            },
        },
        {
            "order": 5,
            "type": "match",
            "is_key": False,
            "source_ref": "Модуль 1, Відео 1.1",
            "payload": {
                "prompt": "Зіставте поняття та його роль:",
                "pairs": [
                    {"left": "Ефірна олія", "right": "Леткі ароматичні сполуки рослини"},
                    {"left": "Базова (жирна) олія", "right": "Розведення та комфортне нанесення на шкіру"},
                    {"left": "1 крапля", "right": "Безпечний старт для знайомства з ароматом"},
                ],
                "explanation": "Жирна базова олія допомагає м'яко наносити концентровану ефірну олію на шкіру.",
            },
        },
        {
            "order": 6,
            "type": "flashcard",
            "is_key": False,
            "source_ref": "Модуль 1, Відео 1.1",
            "payload": {
                "front": "Чому рослина синтезує ефірні олії?",
                "back": "Для власного захисту від шкідників, відновлення тканин і приваблення запилювачів.",
            },
        },
    ]


def _build_rich_lesson_3_1_steps(lesson_id: str) -> list[dict]:
    return [
        {
            "order": 1,
            "type": "card",
            "is_key": False,
            "source_ref": "План Наталії Котелянської · Модуль 3, Відео 3.1",
            "payload": {
                "title": "Золоте правило: розведення та чутливі зони",
                "body": (
                    "Ефірні олії ніколи не капають безпосередньо в очі, у вушний канал або на відкриті "
                    "слизові оболонки. При нанесенні на шкіру використовуйте базову олію (наприклад, "
                    "фракційну кокосову чи мигдальну). Якщо олія випадково потрапила в очі — промивайте "
                    "жирною базовою олією, а НЕ водою!"
                ),
                "clip_id": "clip_3",
                "badge": "Безпека · Відео 3.1",
            },
        },
        {
            "order": 2,
            "type": "card",
            "is_key": False,
            "source_ref": "План Наталії Котелянської · Модуль 3, Відео 3.1",
            "payload": {
                "title": "Фототоксичність цитрусових та «гарячі» олії",
                "body": (
                    "Холоднопресовані цитрусові олії (лимон, лайм, бергамот, грейпфрут) підвищують "
                    "чутливість шкіри до ультрафіолету: не наносьте їх на відкриті ділянки перед виходом "
                    "на сонце протягом 12 годин. «Гарячі» олії (орегано, кориця, гвоздика, чебрець) "
                    "потребують сильного розведення перед контактом зі шкірою."
                ),
                "badge": "Картка безпеки",
            },
        },
        {
            "order": 3,
            "type": "choice",
            "is_key": True,
            "source_ref": "Модуль 3, Відео 3.1 (Ключове правило безпеки)",
            "payload": {
                "question": "Що робити, якщо ефірна олія випадково потрапила на слизову ока?",
                "options": [
                    "Промити ватним диском із жирною базовою олією (наприклад, кокосовою чи оливковою)",
                    "Швидко промити холодною проточною водою",
                    "Закрити очі й почекати, поки випарується",
                    "Додати краплю лаванди для заспокоєння",
                ],
                "correct_index": 0,
                "explanation": "Ефірні олії не розчиняються у воді — вода лише посилить печіння; розчинити їх може лише жирна базова олія.",
            },
        },
        {
            "order": 4,
            "type": "true_false",
            "is_key": True,
            "source_ref": "Модуль 3, Відео 3.1 (Ключове правило безпеки)",
            "payload": {
                "statement": "Цитрусові олії можна сміливо наносити на відкриті ділянки шкіри за 15 хвилин до засмаги на пляжі.",
                "correct": False,
                "explanation": "Більшість цитрусових олій фототоксичні — після нанесення на відкриту шкіру слід уникати прямого сонця мінімум 12 годин.",
            },
        },
        {
            "order": 5,
            "type": "order",
            "is_key": False,
            "source_ref": "Модуль 3, Відео 3.1",
            "payload": {
                "prompt": "Розташуйте кроки першого нанесення нової олії на шкіру в правильному порядку:",
                "items": [
                    "Розвести 1 краплю ефірної олії у базовій олії",
                    "Нанести невелику кількість на ліктьовий згин (патч-тест)",
                    "Спостерігати за реакцією шкіри",
                    "Використовувати аромат у щоденній рутині за відсутності подразнення",
                ],
                "explanation": "Патч-тест у розведенні — найкращий спосіб переконатися у комфорті для вашої шкіри.",
            },
        },
        {
            "order": 6,
            "type": "open",
            "is_key": False,
            "source_ref": "Модуль 3, Відео 3.1",
            "payload": {
                "question": "Опишіть своїми словами, чому тримати базову олію поруч із флаконами важливо навіть тоді, коли ви користуєтеся лише дифузором?",
                "sample_answer": "Базова олія потрібна як перша допомога при випадковому потраплянні ефірної олії на шкіру чи поблизу очей, а також для безпечного розведення при переході до нашкірного нанесення.",
                "key_points": [
                    "перша допомога при потраплянні на шкіру або очі",
                    "ефірна олія розчиняється у жирній олії, а не у воді",
                    "розведення зменшує ризик подразнення",
                ],
                "max_length": 400,
            },
        },
    ]


def _build_rich_lesson_5_1_steps(lesson_id: str) -> list[dict]:
    return [
        {
            "order": 1,
            "type": "card",
            "is_key": False,
            "source_ref": "План Наталії Котелянської · Модуль 5, Відео 5.1",
            "payload": {
                "title": "Трійця для старту: Лаванда, Лимон, М'ята",
                "body": (
                    "Більшість новачків починають із базової трійці: Лаванда — для вечірнього затишку, "
                    "Лимон — для свіжості й чистоти простору, М'ята перцева — для бадьорості та "
                    "концентрації вдень. Кожен аромат розкривається по-різному залежно від часу доби."
                ),
                "clip_id": "clip_5",
                "badge": "Базова аптечка · Відео 5.1",
            },
        },
        {
            "order": 2,
            "type": "choice",
            "is_key": False,
            "source_ref": "Модуль 5, Відео 5.1",
            "payload": {
                "question": "Яку олію з базової трійці найчастіше обирають для вечірнього розслаблюючого ритуалу?",
                "options": [
                    "Лаванду",
                    "Орегано",
                    "Чорний перець",
                    "Лимон перед самим сном на шкіру під сонцем",
                ],
                "correct_index": 0,
                "explanation": "Лаванда традиційно супроводжує вечірні ритуали затишку та спокою.",
            },
        },
        {
            "order": 3,
            "type": "flashcard",
            "is_key": False,
            "source_ref": "Модуль 5, Відео 5.1",
            "payload": {
                "front": "Які три олії входять до класичного стартового тріо?",
                "back": "Лаванда (вечірній спокій), Лимон (свіжість і чистота), М'ята перцева (бадьорість і фокус).",
            },
        },
        {
            "order": 4,
            "type": "true_false",
            "is_key": False,
            "source_ref": "Модуль 5, Відео 5.1",
            "payload": {
                "statement": "Для старту обов'язково купити всі 50 олій одразу, інакше ароматерапія не працює.",
                "correct": False,
                "explanation": "Достатньо 3–5 базових олій, щоб сформувати комфортні щоденні ритуали без перевантаження.",
            },
        },
    ]


def seed_initial_data(db: Session) -> None:
    if db.query(Tariff).count() > 0:
        return

    # 1. Tariffs
    tariffs = [
        Tariff(
            id="basic",
            name="Базовий",
            description="Модулі 1–3: основи, якість CPTG і обов'язкова безпека + Арома з денним лімітом.",
            price_uah=490,
            aroma_daily_limit=10,
            access_courses=[1, 2, 3],
            rank=1,
            is_active=True,
        ),
        Tariff(
            id="standard",
            name="Стандарт",
            description="Усі 7 модулів рівня «Вчитися», безлімітна Арома, міні-тести та інтервальні картки.",
            price_uah=1290,
            aroma_daily_limit=None,
            access_courses=[1, 2, 3, 4, 5, 6, 7],
            rank=2,
            is_active=True,
        ),
        Tariff(
            id="personal",
            name="Персональний",
            description="Усі 12 модулів («Вчитися» + «Ділитися»), Арома + особистий супровід і розбір випадків Наталією.",
            price_uah=2990,
            aroma_daily_limit=None,
            access_courses=list(range(1, 13)),
            rank=3,
            is_active=True,
        ),
    ]
    db.add_all(tariffs)
    db.flush()

    # 2. Demo Users
    now = utcnow()
    demo_users = [
        ("u_basic", "student-basic@aroma.ua", "Олена (Базовий)", "student", "basic"),
        ("u_standard", "student-standard@aroma.ua", "Марія (Стандарт)", "student", "standard"),
        ("u_personal", "student-personal@aroma.ua", "Софія (Персональний)", "student", "personal"),
        ("u_natalia", "natalia@aroma.ua", "Наталія Котелянська", "admin", "personal"),
        ("u_arina", "arina@aroma.ua", "Аріна (Суперадмін)", "superadmin", "personal"),
    ]
    for uid, email, name, role, tariff_id in demo_users:
        user = User(
            id=uid,
            email=email,
            name=name,
            role=role,
            language="uk",
            streak_days=3 if role == "student" else 0,
            last_active_at=now,
        )
        db.add(user)
    db.flush()

    for uid, email, name, role, tariff_id in demo_users:
        db.add(
            Consent(
                id=f"cons_{uid}",
                user_id=uid,
                type="personal_data",
                version=settings.consent_version,
            )
        )
        if role == "student":
            db.add(
                Subscription(
                    id=f"sub_{uid}",
                    user_id=uid,
                    tariff_id=tariff_id,
                    status="active",
                    period_start=now,
                    period_end=now + timedelta(days=30),
                    provider_ref=f"seed_{tariff_id}",
                )
            )

    # 3. 12 Courses & 105 Video Lessons
    rich_lessons: list[Lesson] = []
    for mod_num, title, video_count, level, min_tariff, is_mandatory, desc in MODULES_SPEC:
        course_id = f"course_{mod_num}"
        course = Course(
            id=course_id,
            title=title,
            description=desc,
            order=mod_num,
            level=level,
            min_tariff=min_tariff,
            status="published",
            is_mandatory=is_mandatory,
        )
        db.add(course)
        db.flush()

        lesson_ids_for_test: list[str] = []
        for idx in range(1, video_count + 1):
            code = f"{mod_num}.{idx}"
            lesson_id = f"lesson_{mod_num}_{idx}"
            is_rich = code in ("1.1", "3.1", "5.1")
            lesson = Lesson(
                id=lesson_id,
                course_id=course_id,
                code=code,
                title=_default_lesson_title(mod_num, idx, video_count),
                goal=f"Зрозуміти ключову ідею відео {code} та закріпити її короткими кроками.",
                theses=[
                    f"Ключова теза уроку {code} за планом Наталії Котелянської",
                    "Практичне правило застосування без перевантаження",
                ],
                for_frame=f"План відео {code} (3–6 хв) + Арома-фрагменти.",
                final_thought="Маленький впевнений крок щодня важливіший за теорію без практики.",
                source_ref=f"План Наталії Котелянської · Модуль {mod_num}, Відео {code}",
                order=idx,
                status="published" if is_rich else "draft",
                version=1,
                ai_assisted_checked=True,
            )
            db.add(lesson)
            db.flush()

            if code == "1.1":
                step_defs = _build_rich_lesson_1_1_steps(lesson_id)
            elif code == "3.1":
                step_defs = _build_rich_lesson_3_1_steps(lesson_id)
            elif code == "5.1":
                step_defs = _build_rich_lesson_5_1_steps(lesson_id)
            else:
                step_defs = [
                    {
                        "order": 1,
                        "type": "card",
                        "is_key": False,
                        "source_ref": lesson.source_ref,
                        "payload": {
                            "title": lesson.title,
                            "body": f"Чернетка картки знання для відео {code}. Наталія може доповнити її або імпортувати план із Markdown в адмін-панелі.",
                            "badge": f"Відео {code}",
                        },
                    }
                ]

            for s in step_defs:
                step_id = f"step_{lesson_id}_{s['order']}"
                db.add(
                    Step(
                        id=step_id,
                        lesson_id=lesson_id,
                        order=s["order"],
                        type=s["type"],
                        payload=s["payload"],
                        source_ref=s["source_ref"],
                        is_key=s["is_key"],
                    )
                )
                if s["type"] in ("choice", "true_false"):
                    lesson_ids_for_test.append(step_id)

            if is_rich:
                rich_lessons.append(lesson)
                db.add(
                    LessonVersion(
                        id=f"lver_{lesson_id}_1",
                        lesson_id=lesson_id,
                        version=1,
                        snapshot_json={
                            "title": lesson.title,
                            "goal": lesson.goal,
                            "theses": lesson.theses,
                            "final_thought": lesson.final_thought,
                            "status": lesson.status,
                        },
                        created_by="u_natalia",
                    )
                )

        db.add(
            ModuleTest(
                id=f"mtest_{course_id}",
                course_id=course_id,
                step_ids=lesson_ids_for_test,
                pass_score=75,
            )
        )

    # 4. 14 Aroma Clips from Section 2.1
    # Check if user already placed a video in media/videos/
    video_files = sorted(
        [
            p.name
            for p in (settings.media_dir / "videos").iterdir()
            if p.is_file() and p.suffix.lower() in (".mp4", ".webm", ".mov")
        ]
    )
    for order, clip_title, frag_count, ref in AROMA_CLIPS_SPEC:
        lesson_id = None
        if ref == "1.1" and order == 1:
            lesson_id = "lesson_1_1"
        elif ref == "3.1":
            lesson_id = "lesson_3_1"
        elif ref == "5.1":
            lesson_id = "lesson_5_1"
        elif ref == "2.5":
            lesson_id = "lesson_2_5"

        matched_video = None
        for vf in video_files:
            if vf.startswith(f"{order}.") or vf.startswith(f"clip_{order}") or (order == 1 and len(video_files) == 1):
                matched_video = f"/media/videos/{vf}"
                break

        fragments = [
            {"order": i, "text": f"Фрагмент {i} (~8 с) до ролика «{clip_title}»."}
            for i in range(1, frag_count + 1)
        ]
        db.add(
            AromaClip(
                id=f"clip_{order}",
                lesson_id=lesson_id,
                order=order,
                title=clip_title,
                suggested_lesson_ref=ref,
                fragments_count=frag_count,
                fragments_json=fragments,
                video_url=matched_video,
                script_text=f"Плюшева Арома розповідає тему «{clip_title}» ({frag_count} фрагментів по ~8 сек).",
            )
        )

    db.commit()

    # 5. Build initial RAG KB chunks for published lessons
    for lesson in rich_lessons:
        db.refresh(lesson)
        reindex_lesson_kb(db, lesson)
