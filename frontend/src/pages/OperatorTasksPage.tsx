import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Calendar, CheckCircle, ExternalLink, RefreshCw } from 'lucide-react';
import { operatorTasksApi, type TaskContact, type OperatorTasksResponse } from '../api/operatorTasks';
import { useAppStore } from '../store/appStore';

const STATUS_LABELS: Record<string, string> = {
  to_be_sent: 'To Be Sent',
  sent: 'Sent',
  interested: 'Interested',
  not_interested: 'Not Interested',
  ooo: 'Out of Office',
  unsubscribed: 'Unsubscribed',
  negotiating_meeting: 'Negotiating Meeting',
  scheduled: 'Scheduled',
  meeting_held: 'Meeting Held',
  meeting_no_show: 'No Show',
  meeting_rescheduled: 'Rescheduled',
  qualified: 'Qualified',
  not_qualified: 'Not Qualified',
  // Legacy
  warm: 'Warm',
  replied: 'Replied',
  scheduling: 'Scheduling',
};

const CATEGORY_COLORS: Record<string, string> = {
  interested: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  meeting_request: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  question: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  not_interested: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  out_of_office: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  unsubscribe: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  other: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
};

type TabKey = 'replies' | 'align_meetings' | 'align_qualified';

const TABS: { key: TabKey; label: string; icon: typeof MessageSquare }[] = [
  { key: 'replies', label: 'Replies', icon: MessageSquare },
  { key: 'align_meetings', label: 'Align Meetings', icon: Calendar },
  { key: 'align_qualified', label: 'Align Qualified', icon: CheckCircle },
];

// Meeting status action buttons
const MEETING_ACTIONS = [
  { status: 'meeting_held', label: 'Meeting Held', color: 'bg-green-600 hover:bg-green-700' },
  { status: 'meeting_no_show', label: 'No Show', color: 'bg-yellow-600 hover:bg-yellow-700' },
  { status: 'meeting_rescheduled', label: 'Rescheduled', color: 'bg-blue-600 hover:bg-blue-700' },
];

const QUALIFIED_ACTIONS = [
  { status: 'qualified', label: 'Qualified', color: 'bg-green-600 hover:bg-green-700' },
  { status: 'not_qualified', label: 'Not Qualified', color: 'bg-red-600 hover:bg-red-700' },
];

function ContactCard({
  contact,
  tab,
  onTransition,
}: {
  contact: TaskContact;
  tab: TabKey;
  onTransition: (contactId: number, newStatus: string) => void;
}) {
  const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email;

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <a
              href={`/contacts/${contact.id}`}
              className="font-medium text-gray-900 dark:text-gray-100 hover:text-blue-600 truncate"
            >
              {name}
            </a>
            {contact.linkedin_url && (
              <a
                href={contact.linkedin_url.startsWith('http') ? contact.linkedin_url : `https://${contact.linkedin_url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:text-blue-700"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {contact.job_title && <span>{contact.job_title}</span>}
            {contact.job_title && contact.company_name && <span> at </span>}
            {contact.company_name && <span className="font-medium">{contact.company_name}</span>}
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {contact.email}
            {contact.last_reply_at && <span className="ml-2">replied {new Date(contact.last_reply_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>}
            {contact.campaign_name && <span className="ml-2">• {contact.campaign_name}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4 flex-shrink-0">
          <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
            {STATUS_LABELS[contact.status] || contact.status}
          </span>
        </div>
      </div>

      {/* Tab-specific content */}
      {tab === 'replies' && (
        <div className="mt-3">
          {contact.category && (
            <span className={`text-xs px-2 py-0.5 rounded ${CATEGORY_COLORS[contact.category] || CATEGORY_COLORS.other}`}>
              {contact.category}
            </span>
          )}
          {contact.last_message && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 line-clamp-2 italic">
              "{contact.last_message}"
            </p>
          )}
        </div>
      )}

      {tab === 'align_meetings' && (
        <div className="mt-3 flex gap-2">
          {MEETING_ACTIONS.map((action) => (
            <button
              key={action.status}
              onClick={() => onTransition(contact.id, action.status)}
              className={`text-xs px-3 py-1 rounded text-white ${action.color}`}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      {tab === 'align_qualified' && (
        <div className="mt-3 flex gap-2">
          {contact.days_since !== null && contact.days_since !== undefined && (
            <span className="text-xs text-gray-500 dark:text-gray-400 mr-2 self-center">
              {contact.days_since}d since meeting
            </span>
          )}
          {QUALIFIED_ACTIONS.map((action) => (
            <button
              key={action.status}
              onClick={() => onTransition(contact.id, action.status)}
              className={`text-xs px-3 py-1 rounded text-white ${action.color}`}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function OperatorTasksPage() {
  const [data, setData] = useState<OperatorTasksResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('replies');
  const [loading, setLoading] = useState(true);
  const [, setTransitioning] = useState<number | null>(null);
  const { currentProject } = useAppStore();

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const result = await operatorTasksApi.getTasks(currentProject?.id);
      setData(result);
    } catch (err) {
      console.error('Failed to load operator tasks:', err);
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id]);

  useEffect(() => {
    loadTasks();
    // Auto-refresh every 30s
    const interval = setInterval(loadTasks, 30_000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  const handleTransition = async (contactId: number, newStatus: string) => {
    setTransitioning(contactId);
    try {
      await operatorTasksApi.transitionStatus(contactId, newStatus);
      await loadTasks();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Transition failed');
    } finally {
      setTransitioning(null);
    }
  };

  const tabData = data ? data[activeTab] : null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Operator Tasks</h1>
        <button
          onClick={loadTasks}
          disabled={loading}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 mb-6">
        {TABS.map(({ key, label, icon: Icon }) => {
          const count = data ? data[key].count : 0;
          const isActive = activeTab === key;
          return (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
              {count > 0 && (
                <span
                  className={`text-xs px-1.5 py-0.5 rounded-full ${
                    key === 'replies' && count > 0
                      ? 'bg-red-500 text-white'
                      : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {loading && !data ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : tabData && tabData.contacts.length > 0 ? (
        <div className="space-y-3">
          {tabData.contacts.map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              tab={activeTab}
              onTransition={handleTransition}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400 dark:text-gray-500">
          No tasks in this tab
        </div>
      )}
    </div>
  );
}
