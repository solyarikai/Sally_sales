import { useParams, useNavigate } from 'react-router-dom';
import { MessageCircle, BookOpen, Inbox, BarChart2, Users } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { TelegramInboxPage } from './TelegramInboxPage';

type Tab = 'info' | 'inbox';

const TABS: { key: Tab; label: string; icon: typeof MessageCircle }[] = [
  { key: 'info', label: 'Info', icon: BookOpen },
  { key: 'inbox', label: 'Inbox', icon: Inbox },
];

const VALID_TABS = new Set<string>(TABS.map(t => t.key));

export function TelegramOutreachPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const { tab: tabParam } = useParams<{ tab?: string }>();

  const activeTab: Tab = VALID_TABS.has(tabParam || '') ? (tabParam as Tab) : 'info';

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg, color: t.text1 }}>
      {/* Header with tabs */}
      <div className="flex items-center gap-4 px-5 py-2.5 border-b" style={{ borderColor: t.divider }}>
        <div className="flex items-center gap-2 mr-2">
          <MessageCircle className="w-5 h-5" style={{ color: '#3b82f6' }} />
          <h1 className="text-[15px] font-semibold">Telegram Outreach</h1>
        </div>
        <nav className="flex items-center gap-0.5">
          {TABS.map(tab => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => navigate(`/telegram-outreach/${tab.key}`)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
                style={{
                  background: isActive ? (isDark ? '#37373d' : '#e8e8e8') : 'transparent',
                  color: isActive ? t.text1 : t.text4,
                }}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto min-h-0">
        {activeTab === 'info' && <InfoPanel isDark={isDark} t={t} />}
        {activeTab === 'inbox' && <TelegramInboxPage />}
      </div>
    </div>
  );
}

/* ── Info Panel ───────────────────────────────────────────────── */

function InfoPanel({ isDark, t }: { isDark: boolean; t: ReturnType<typeof themeColors> }) {
  return (
    <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">
      {/* Intro */}
      <Section title="Telegram Outreach" isDark={isDark} t={t}>
        <p>
          Система массовой рассылки и обработки ответов через Telegram DM.
          Работает через Telegram Desktop сессии (tdata), поддерживает до 100 аккаунтов одновременно.
          Входящие сообщения обрабатываются AI: классифицируются, генерируются черновики ответов, оператор получает уведомления.
        </p>
      </Section>

      {/* Account Management */}
      <Section title="1. Управление аккаунтами (tdata)" isDark={isDark} t={t} icon={Users}>
        <FuncBlock
          name="Upload tdata"
          isDark={isDark}
          desc="Импорт Telegram-аккаунтов из архива tdata (ZIP/RAR)."
          how={[
            'Загрузить ZIP/RAR с папкой tdata из Telegram Desktop или Kotatogram',
            'Система извлекает auth_key + dc_id из key_datas для каждого аккаунта',
            'Строит Telethon StringSession (base64: dc_id + ip + port + auth_key)',
            'Подключается к Telegram, получает user info (phone, username, first_name)',
            'Сохраняет StringSession в БД (таблица telegram_dm_accounts)',
            'Поддержка до 100 аккаунтов в одном архиве (Kotatogram multi-account)',
          ]}
          why="Не нужен код подтверждения или 2FA. tdata = готовая сессия. StringSession IS the account."
        />
        <FuncBlock
          name="Connect / Disconnect"
          isDark={isDark}
          desc="Управление подключением отдельных аккаунтов."
          how={[
            'Connect: создает TelegramClient из сохраненного StringSession, проверяет авторизацию',
            'Регистрирует real-time event handler для входящих DM',
            'Disconnect: закрывает TCP-соединение, убирает event handlers',
            'При ошибках (AuthKeyUnregistered, SessionRevoked) — статус меняется на "error"',
          ]}
          why="Позволяет временно отключить аккаунт без удаления сессии. При перезапуске сервера все active-аккаунты автоматически переподключаются (reconnect_all)."
        />
        <FuncBlock
          name="Привязка к проекту (project_id)"
          isDark={isDark}
          desc="Каждый аккаунт привязывается к проекту для корректной обработки ответов."
          how={[
            'PATCH /telegram-dm/accounts/{id}/ с project_id',
            'После привязки: входящие DM обрабатываются по knowledge/ICP/шаблонам этого проекта',
            'Без привязки к проекту аккаунт не участвует в polling и real-time обработке',
          ]}
          why="Разные проекты продают разные продукты. Аккаунт, привязанный к EasyStaff, генерирует ответы в контексте EasyStaff, а не Inxy."
        />
        <FuncBlock
          name="Delete account"
          isDark={isDark}
          desc="Полное удаление аккаунта из системы."
          how={[
            'Закрывает Telethon-соединение',
            'Удаляет запись из telegram_dm_accounts (StringSession уничтожается)',
            'ProcessedReply с telegram_account_id сохраняются (история не теряется)',
          ]}
          why="Если аккаунт забанен или сессия отозвана — удалить и загрузить новый tdata."
        />
      </Section>

      {/* Real-time Messages */}
      <Section title="2. Прием входящих сообщений" isDark={isDark} t={t} icon={Inbox}>
        <FuncBlock
          name="Real-time listeners (persistent TCP)"
          isDark={isDark}
          desc="Каждый подключенный аккаунт держит постоянное TCP-соединение с серверами Telegram."
          how={[
            'При connect_account() регистрируется @client.on(events.NewMessage(incoming=True))',
            'Telegram PUSH-ит новые сообщения через открытый сокет — доставка <1 секунды',
            'Фильтрация: только приватные DM (не группы/каналы), только текст (не медиа), не боты',
            'При получении: process_telegram_reply() → classify → draft → notify',
            'start_listening() запускает run_until_disconnected() для каждого клиента',
            'Auto-reconnect при дисконнекте с backoff 10с',
          ]}
          why="Мгновенная реакция на ответы лидов. Задержка <1с вместо 90с при polling."
        />
        <FuncBlock
          name="Polling (safety net, каждые 3 мин)"
          isDark={isDark}
          desc="Фоновый polling как страховка на случай пропущенных real-time событий."
          how={[
            'crm_scheduler вызывает poll_all_accounts() каждые 3 минуты',
            'Для каждого active-аккаунта с project_id: iter_dialogs() → проверка новых inbound',
            'Логика: если последнее сообщение в диалоге — inbound и новее last_processed_at → обработать',
            'Задержка 2с между аккаунтами для избежания rate limits (FloodWait)',
            'После обхода обновляет last_processed_at курсор',
            'Дубли отсекаются через message_hash (MD5 от body[:500].lower())',
          ]}
          why="Real-time может пропустить сообщения при рестарте контейнера или разрыве соединения. Polling подбирает пропущенное."
        />
      </Section>

      {/* Reply Processing Pipeline */}
      <Section title="3. Обработка ответов (AI Pipeline)" isDark={isDark} t={t} icon={MessageCircle}>
        <FuncBlock
          name="process_telegram_reply()"
          isDark={isDark}
          desc="Полный пайплайн обработки одного входящего DM. Аналог process_getsales_reply()."
          how={[
            '1. Фильтрация: пропуск emoji-only и пустых сообщений',
            '2. Dedup: MD5-хеш от текста[:500] — если ProcessedReply с таким hash+peer_id уже есть → skip',
            '3. Project lookup: загрузка настроек проекта, knowledge entries, ICP, шаблонов',
            '4. Classify: GPT классифицирует ответ (interested, meeting_request, question, not_interested, etc.)',
            '5. Knowledge injection: knowledge entries + reference examples добавляются в prompt',
            '6. Calendly slots: для meeting/interested категорий инжектируются слоты',
            '7. Draft generation: GPT генерирует черновик (короткий, 2-3 предложения, без подписи)',
            '8. Language detect: определение языка + перевод если не EN/RU',
            '9. Create ProcessedReply: source="telegram", channel="telegram", telegram_peer_id, telegram_account_id',
          ]}
          why="Единая pipeline для всех каналов. Telegram-ответы попадают в тот же ReplyQueue что и email/LinkedIn."
        />
        <FuncBlock
          name="Классификация (категории)"
          isDark={isDark}
          desc="AI определяет намерение лида по тексту сообщения."
          how={[
            'interested — лид проявил интерес',
            'meeting_request — хочет назначить встречу',
            'question — задает вопрос о продукте/услуге',
            'not_interested — отказ',
            'out_of_office — автоответ "не в офисе"',
            'do_not_contact — просьба не писать больше',
            'referral — перенаправляет на другого человека',
            'Используется project-specific classification_prompt если задан',
          ]}
          why="Приоритизация ответов. interested/meeting_request — срочные, not_interested — auto-dismiss."
        />
        <FuncBlock
          name="Генерация черновика"
          isDark={isDark}
          desc="GPT генерирует ответ на основе контекста проекта и категории."
          how={[
            'Учитывает: knowledge base проекта, ICP, sender identity (имя/должность/компания)',
            'Стиль: короткий (2-3 предложения), разговорный, без email-подписи',
            'Без em-dashes (—), только запятые и точки',
            'Для meeting/interested — добавляет Calendly слоты',
            'Reference examples: успешные ответы из learning log вставляются как примеры',
          ]}
          why="Оператор видит готовый черновик и может отправить одним кликом, а не писать с нуля."
        />
      </Section>

      {/* Notifications */}
      <Section title="4. Уведомления" isDark={isDark} t={t}>
        <FuncBlock
          name="send_telegram_dm_notification()"
          isDark={isDark}
          desc="Уведомление оператора в Telegram о новом входящем DM."
          how={[
            'Отправляется ПОСЛЕ commit (чтобы избежать ghost-уведомлений при rollback)',
            'Формат: от кого (@username), из какого аккаунта, категория, текст',
            'Deep link: /?reply_id={id}&project={slug} для перехода в ReplyQueue',
            'Аналог notify_linkedin_reply() но с @username вместо email',
          ]}
          why="Оператор мгновенно узнает о новом ответе и может обработать его из ReplyQueue."
        />
      </Section>

      {/* Inbox UI */}
      <Section title="5. Inbox (ручной просмотр)" isDark={isDark} t={t}>
        <FuncBlock
          name="Telegram Inbox (вкладка Inbox)"
          isDark={isDark}
          desc="Трехпанельный UI для прямого просмотра и отправки DM."
          how={[
            'Левая панель: список аккаунтов с индикаторами статуса (green/red)',
            'Средняя панель: список диалогов (conversations) выбранного аккаунта',
            'Правая панель: история сообщений + поле ввода для ответа',
            'Upload tdata: кнопка загрузки ZIP/RAR архива прямо из интерфейса',
            'Действия с аккаунтами: connect/disconnect/delete',
          ]}
          why="MVP-инструмент для прямого общения. Основной workflow через ReplyQueue (автоматический), но Inbox нужен для ручного просмотра всех диалогов."
        />
      </Section>

      {/* Outreach Stats */}
      <Section title="6. Статистика Outreach" isDark={isDark} t={t} icon={BarChart2}>
        <FuncBlock
          name="OutreachStats (ручной ввод для Telegram)"
          isDark={isDark}
          desc="Трекинг plan vs fact по каналам и сегментам."
          how={[
            'Для Telegram и WhatsApp — ручной ввод (is_manual=1)',
            'Для Email/LinkedIn — автосинхронизация из SmartLead/GetSales',
            'Метрики: plan_contacts, contacts_sent, replies_count, positive_replies, meetings_scheduled/completed',
            'Rates: reply_rate, accept_rate, positive_rate, meeting_rate (авто-расчет)',
            'Период: daily/weekly/monthly, с группировкой по сегментам',
          ]}
          why="Единый дашборд для сравнения эффективности всех каналов. Telegram stats вводятся вручную т.к. нет единого API для подсчета отправленных."
        />
      </Section>

      {/* Identity & Dedup */}
      <Section title="7. Идентификация и дедупликация" isDark={isDark} t={t}>
        <FuncBlock
          name="3-way Identity (COALESCE)"
          isDark={isDark}
          desc="Telegram-контакты идентифицируются по telegram_peer_id."
          how={[
            'Цепочка: COALESCE(lead_email, getsales_lead_uuid, telegram_peer_id)',
            'Email лиды → по email, LinkedIn → по GetSales UUID, Telegram → по peer_id',
            'Один человек может иметь записи во всех трех каналах (разные ProcessedReply)',
            'Нет фейковых email или placeholder-ов. Если email нет — lead_email = NULL',
          ]}
          why="Корректная группировка ответов от одного контакта через разные каналы."
        />
        <FuncBlock
          name="Dedup (content hash)"
          isDark={isDark}
          desc="Предотвращение дублирования при одновременной работе real-time + polling."
          how={[
            'MD5(body[:500].lower()) — контент-хеш на каждое сообщение',
            'Unique constraint: (telegram_peer_id, message_hash) — uq_reply_dedup',
            'При race condition (real-time и polling одновременно) — IntegrityError ловится молча',
            'last_processed_at курсор отсекает старые сообщения при polling',
          ]}
          why="Гарантия: один ответ = один ProcessedReply, даже при параллельной обработке."
        />
      </Section>

      {/* Error Handling */}
      <Section title="8. Обработка ошибок" isDark={isDark} t={t}>
        <FuncBlock
          name="FloodWait"
          isDark={isDark}
          desc="Telegram rate limit — временная блокировка API-вызовов."
          how={[
            'Если FloodWait < 60с — ждем и повторяем',
            'Если > 60с — пропускаем аккаунт в этом цикле',
            'Polling staggered: 2с задержка между аккаунтами',
          ]}
          why="Telegram блокирует аккаунты при слишком частых запросах. Staggering и backoff предотвращают баны."
        />
        <FuncBlock
          name="Session errors"
          isDark={isDark}
          desc="Необратимые ошибки авторизации."
          how={[
            'AuthKeyUnregisteredError — сессия не найдена на серверах Telegram',
            'SessionRevokedError — сессия отозвана пользователем',
            'UserDeactivatedBanError — аккаунт забанен',
            'Статус меняется на "error", аккаунт отключается',
            'Решение: удалить аккаунт и загрузить свежий tdata',
          ]}
          why="Сессии могут протухнуть. Система корректно обрабатывает это без крашей."
        />
      </Section>

      {/* Architecture */}
      <Section title="9. Архитектура" isDark={isDark} t={t}>
        <div className="space-y-3">
          <div className="text-[13px] leading-relaxed" style={{ color: t.text2 }}>
            <strong style={{ color: t.text1 }}>Ключевые файлы:</strong>
          </div>
          <table className="w-full text-[13px]" style={{ color: t.text2 }}>
            <tbody>
              {[
                ['backend/app/services/telegram_dm_service.py', 'Telethon multi-client manager, real-time listeners, polling'],
                ['backend/app/services/reply_processor.py', 'process_telegram_reply() — classify + draft pipeline'],
                ['backend/app/api/telegram_dm.py', 'REST API: upload-tdata, connect, dialogs, messages, send'],
                ['backend/app/models/telegram_dm.py', 'TelegramDMAccount model (StringSession, project_id, status)'],
                ['backend/app/models/reply.py', 'ProcessedReply (telegram_peer_id, telegram_account_id)'],
                ['backend/app/services/crm_scheduler.py', 'Polling loop (каждые 3 мин)'],
                ['backend/app/services/notification_service.py', 'Telegram notifications для оператора'],
                ['frontend/src/pages/TelegramInboxPage.tsx', 'Inbox UI (3 панели: аккаунты, диалоги, сообщения)'],
                ['frontend/src/api/telegram.ts', 'API-клиент для фронтенда'],
              ].map(([file, desc]) => (
                <tr key={file} className="border-b" style={{ borderColor: t.divider }}>
                  <td className="py-1.5 pr-4 font-mono text-[12px] whitespace-nowrap" style={{ color: '#3b82f6' }}>{file}</td>
                  <td className="py-1.5" style={{ color: t.text3 }}>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Flow Diagram */}
      <Section title="10. Полный Flow" isDark={isDark} t={t}>
        <div className="font-mono text-[12px] leading-6 whitespace-pre-wrap" style={{ color: t.text3, background: isDark ? '#1a1a1a' : '#f8f8f8', padding: '16px', borderRadius: '8px' }}>
{`Загрузка tdata (ZIP/RAR)
  → Извлечение auth_key + dc_id
  → Создание StringSession
  → Подключение к Telegram
  → Привязка к проекту

Входящее DM (real-time <1с / polling 3мин)
  → Фильтрация (только private, только текст, не боты)
  → Dedup (MD5 hash)
  → process_telegram_reply()
    → Classify (GPT: категория + confidence)
    → Load project knowledge + ICP + templates
    → Generate draft (GPT: 2-3 предложения)
    → Detect language + translate
    → Create ProcessedReply (source=telegram)
  → Commit
  → Send notification → оператор

Оператор
  → Видит ответ в ReplyQueue (Tasks → Replies)
  → Badge "Telegram" на карточке
  → Редактирует черновик → Send
  → Сообщение уходит через Telethon DM`}
        </div>
      </Section>
    </div>
  );
}

/* ── Reusable components ──────────────────────────────────────── */

function Section({
  title,
  children,
  t,
  icon: Icon,
}: {
  title: string;
  children: React.ReactNode;
  isDark?: boolean;
  t: ReturnType<typeof themeColors>;
  icon?: typeof MessageCircle;
}) {
  return (
    <div
      className="rounded-lg border p-5"
      style={{ background: t.cardBg, borderColor: t.cardBorder }}
    >
      <h2 className="text-[15px] font-semibold mb-3 flex items-center gap-2" style={{ color: t.text1 }}>
        {Icon && <Icon className="w-4 h-4" style={{ color: '#3b82f6' }} />}
        {title}
      </h2>
      <div className="space-y-4">
        {children}
      </div>
    </div>
  );
}

function FuncBlock({
  name,
  desc,
  how,
  why,
  isDark,
}: {
  name: string;
  desc: string;
  how: string[];
  why: string;
  isDark: boolean;
}) {
  return (
    <div
      className="rounded-md border p-4"
      style={{
        borderColor: isDark ? '#333' : '#e5e5e5',
        background: isDark ? '#1e1e1e' : '#fafafa',
      }}
    >
      <h3 className="text-[14px] font-semibold mb-1" style={{ color: isDark ? '#e0e0e0' : '#222' }}>
        {name}
      </h3>
      <p className="text-[13px] mb-2" style={{ color: isDark ? '#969696' : '#666' }}>
        {desc}
      </p>
      <div className="text-[13px] mb-2" style={{ color: isDark ? '#b0b0b0' : '#444' }}>
        <div className="font-medium mb-1" style={{ color: isDark ? '#d4d4d4' : '#333' }}>Как работает:</div>
        <ul className="list-disc list-inside space-y-0.5 ml-1">
          {how.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="text-[12px] italic" style={{ color: isDark ? '#858585' : '#888' }}>
        {why}
      </div>
    </div>
  );
}
