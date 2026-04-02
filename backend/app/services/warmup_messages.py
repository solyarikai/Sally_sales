"""
Warmup message bank for Telegram account warm-up conversations.

Structure:
  QUESTIONS — categorized openers (account A sends to buddy B)
  ANSWERS   — universal responses (buddy B replies to any question)

Design rule: ANY combination of question + answer must be logically
coherent as a natural chat exchange between acquaintances.

Languages: Russian + English (mixed naturally, as real users do).
"""

# ── QUESTIONS ────────────────────────────────────────────────────────
# ~120 openers across 8 categories.  Each category has 14-16 items.

QUESTIONS: dict[str, list[str]] = {
    # 1. Greetings / how are you
    "greetings": [
        "Привет, как дела?",
        "Здарова! Как жизнь?",
        "Привет! Как прошёл день?",
        "Hey, what's up?",
        "Hi! How's it going?",
        "Привет! Давно не общались",
        "Как твои дела сегодня?",
        "Привет) Что нового?",
        "Hello! How are you doing?",
        "Hey there! What's new?",
        "Ку! Как ты?",
        "Приветик, как настроение?",
        "Здорово! Как сам?",
        "Yo! How's everything?",
        "Привет! Всё норм у тебя?",
    ],

    # 2. Weather / weekend plans
    "weather_weekend": [
        "Какие планы на выходные?",
        "Как погода у вас?",
        "Any plans for the weekend?",
        "Классная погода сегодня, не находишь?",
        "Что делаешь в субботу?",
        "Как выходные прошли?",
        "Куда-нибудь собираешься на выходных?",
        "Погода огонь, гулять не идёшь?",
        "What are you up to this weekend?",
        "Как тебе сегодняшняя погода?",
        "Планируешь куда-то выбраться?",
        "Nice weather today, right?",
        "Есть планы на вечер?",
        "Чем занимаешься в свободное время?",
        "How was your weekend?",
    ],

    # 3. Work questions (general)
    "work": [
        "Как работа, всё хорошо?",
        "Много работы сегодня?",
        "How's work going?",
        "Busy day today?",
        "Как там проект продвигается?",
        "Работа не замучила?",
        "Загружен сегодня?",
        "How's the project going?",
        "Как на работе дела?",
        "Всё успеваешь по задачам?",
        "Work going well?",
        "Не перерабатываешь?",
        "Много дел на этой неделе?",
        "Как рабочая неделя?",
        "Getting a lot done today?",
    ],

    # 4. Clarifying / follow-up questions
    "clarifying": [
        "Слушай, ты видел новость?",
        "Помнишь, мы обсуждали?",
        "А ты уже пробовал?",
        "Did you see that article?",
        "Ты в курсе последних новостей?",
        "Помнишь то, о чём говорили?",
        "Have you tried that yet?",
        "Слышал что-нибудь новое?",
        "А что в итоге решили?",
        "Did you figure it out?",
        "Ну что, получилось?",
        "Any updates on that?",
        "Как там ситуация?",
        "Ты разобрался в итоге?",
        "А что думаешь по этому поводу?",
    ],

    # 5. Requests / suggestions
    "requests": [
        "Можешь глянуть одну штуку?",
        "У тебя есть минутка?",
        "Не подскажешь кое-что?",
        "Can you help me with something?",
        "Got a minute?",
        "Можешь посоветовать?",
        "Хотел спросить у тебя кое-что",
        "Нужен твой совет",
        "Could you take a look at something?",
        "Можно тебя спросить?",
        "Есть идея, хочу обсудить",
        "Mind if I ask you something?",
        "Давай обсудим одну тему?",
        "Хочу поделиться мыслью",
        "Can I get your opinion on something?",
    ],

    # 6. News reactions
    "news": [
        "Видел, что сегодня произошло?",
        "Читал новости сегодня?",
        "Did you see what happened?",
        "Офигеть, ты видел?",
        "Ты слышал про это?",
        "Have you heard the news?",
        "Что думаешь про последние новости?",
        "Прикинь, что сегодня узнал",
        "Can you believe what happened?",
        "Ты уже в курсе?",
        "Новость дня видел?",
        "What do you think about the news?",
        "Не поверишь, что я узнал",
        "Сегодня такое было...",
        "Guess what I just found out",
    ],

    # 7. Evening / week plans
    "plans": [
        "Что планируешь на вечер?",
        "Есть планы на эту неделю?",
        "What are you doing tonight?",
        "Чем будешь заниматься?",
        "Куда-нибудь пойдём?",
        "Any plans for the week?",
        "Хочешь куда-нибудь сходить?",
        "Что делаешь завтра?",
        "Want to hang out sometime?",
        "На следующей неделе свободен?",
        "Давай как-нибудь встретимся",
        "Are you free tomorrow?",
        "Есть настроение куда-то выбраться?",
        "Может пересечёмся на неделе?",
        "Let's catch up soon!",
    ],

    # 8. Recommendations (movie / restaurant / book)
    "recommendations": [
        "Есть что посмотреть хорошее?",
        "Можешь что-то посоветовать почитать?",
        "Any good movie recommendations?",
        "Что нового посмотрел?",
        "Слышал про какие-нибудь хорошие книги?",
        "Что-нибудь интересное смотрел?",
        "Подскажи хороший сериал",
        "Any good shows to watch?",
        "Знаешь хорошее место поесть?",
        "Read any good books lately?",
        "Что сейчас смотришь?",
        "Можешь посоветовать ресторан?",
        "What are you watching these days?",
        "Есть что послушать интересного?",
        "Know any good podcasts?",
    ],
}


# ── ANSWERS ──────────────────────────────────────────────────────────
# ~105 universal responses across 7 categories.  Each works as a reply
# to ANY question from the bank above.

ANSWERS: dict[str, list[str]] = {
    # 1. Positive answers
    "positive": [
        "Всё отлично, спасибо!",
        "Да, всё супер!",
        "Отлично, настроение хорошее)",
        "Great, thanks for asking!",
        "All good here!",
        "Прекрасно, не жалуюсь",
        "Всё хорошо, спасибо что спросил",
        "Лучше не бывает!",
        "Doing great, actually!",
        "Всё классно, вообще кайф",
        "Pretty good, can't complain!",
        "Замечательно! Настрой боевой",
        "Really well, thanks!",
        "Просто огонь, всё по плану",
        "Couldn't be better!",
    ],

    # 2. Neutral answers
    "neutral": [
        "Да, вроде норм",
        "Ну так, потихоньку",
        "Нормально, без изменений",
        "Yeah, nothing special",
        "Как обычно, стабильно",
        "Всё по-старому",
        "Same as usual",
        "Ну такое, средненько",
        "Not bad, not great",
        "Потихоньку, без резких движений",
        "Да ладно, нормально всё",
        "It's okay, I guess",
        "Ровно, без сюрпризов",
        "Стабильно, как всегда",
        "Can't complain really",
    ],

    # 3. Clarifying questions in response
    "clarifying_back": [
        "А у тебя как?",
        "А сам как?",
        "А что случилось?",
        "What about you?",
        "How about yourself?",
        "А ты что думаешь?",
        "Серьёзно? Расскажи подробнее",
        "Really? Tell me more",
        "Ого, а что именно?",
        "О, интересно, а давно это?",
        "Wait, what happened?",
        "А с чего вдруг?",
        "В смысле? Поподробнее",
        "Oh, what do you mean?",
        "Хм, а почему спрашиваешь?",
    ],

    # 4. Agreement / approval
    "agreement": [
        "Согласен!",
        "Точно, верно подмечено",
        "Да, согласен на 100%",
        "Absolutely!",
        "Полностью поддерживаю",
        "Именно так!",
        "Totally agree!",
        "Ага, я тоже так думаю",
        "Верно, так и есть",
        "That's exactly right!",
        "Без вопросов, согласен",
        "Yep, that's what I think too",
        "Правильно говоришь",
        "100%! Поддерживаю",
        "Couldn't agree more!",
    ],

    # 5. Refusal / busy
    "busy": [
        "Сорри, сейчас занят немного",
        "Чуть позже напишу, ок?",
        "Пока не могу, давай потом",
        "Sorry, bit busy right now",
        "Can we talk later?",
        "Не сейчас, давай вечером?",
        "Сейчас в запаре, потом отвечу",
        "I'll get back to you",
        "Извини, занят по работе",
        "Давай чуть позже обсудим",
        "Let me check and get back to you",
        "Ща не могу, но скоро освобожусь",
        "Немного позже, ладно?",
        "Hold on, I'll reply soon",
        "Минутку, сейчас допишу и отвечу",
    ],

    # 6. Humorous / playful answers
    "humorous": [
        "Ха, ну ты даёшь)",
        "Ахах, смешно получается",
        "Не, ну это прикольно)",
        "Haha, that's funny",
        "Лол, серьёзно?)",
        "Ну ты жжёшь 😄",
        "Ahaha, classic",
        "Ой, не начинай 😂",
        "Ну это вообще топ)",
        "That cracked me up",
        "Прикол, конечно)",
        "LOL, didn't expect that",
        "Ахаха, ну красава",
        "Бро, это было смешно",
        "Ha, you're killing me",
    ],

    # 7. Short / terse answers
    "short": [
        "Ок",
        "Да",
        "Понял",
        "Ясно",
        "Ага",
        "Sure",
        "Yep",
        "Got it",
        "Ладно",
        "Хорошо",
        "Sounds good",
        "Окей",
        "Угу",
        "Makes sense",
        "Принял",
    ],
}


# ── Flat lists for quick random access ───────────────────────────────

ALL_QUESTIONS: list[str] = [q for qs in QUESTIONS.values() for q in qs]
ALL_ANSWERS: list[str] = [a for ans in ANSWERS.values() for a in ans]
