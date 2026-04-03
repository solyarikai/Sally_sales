import { useState, useEffect } from 'react';
import {
  MessageSquare, Users, Target, BarChart3, TrendingUp, Cpu,
  FileText, Settings, Search, Loader2, Sparkles, ChevronDown,
  ChevronRight, CheckCircle2, AlertTriangle, Clock,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { chatIntelApi, type ChatMessage, type ChatInsight, type ChatCluster, type ChatStats } from '../../api/chatIntel';

const CLUSTER_ICONS: Record<string, any> = {
  'file-text': FileText,
  'settings': Settings,
  'users': Users,
  'target': Target,
  'bar-chart': BarChart3,
  'cpu': Cpu,
  'trending-up': TrendingUp,
};

const CLUSTER_COLORS: Record<string, string> = {
  contract_legal: 'bg-amber-50 text-amber-700 border-amber-200',
  onboarding: 'bg-blue-50 text-blue-700 border-blue-200',
  lead_ops: 'bg-green-50 text-green-700 border-green-200',
  segments: 'bg-purple-50 text-purple-700 border-purple-200',
  reporting: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  infrastructure: 'bg-red-50 text-red-700 border-red-200',
  scaling: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

function InsightCard({ insight, cluster }: { insight: ChatInsight; cluster?: ChatCluster }) {
  const [expanded, setExpanded] = useState(true);
  const Icon = cluster ? CLUSTER_ICONS[cluster.icon] || MessageSquare : MessageSquare;
  const colorClass = CLUSTER_COLORS[insight.topic] || 'bg-neutral-50 text-neutral-700 border-neutral-200';

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-neutral-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
          <div className={cn('p-1.5 rounded-lg border', colorClass)}>
            <Icon className="w-4 h-4" />
          </div>
          <span className="font-semibold text-neutral-900">{cluster?.name || insight.topic}</span>
        </div>
        {insight.action_items && insight.action_items.length > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
            {insight.action_items.length} actions
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-neutral-100 px-5 py-4 space-y-4">
          {/* Summary */}
          <p className="text-sm text-neutral-700 leading-relaxed">{insight.summary}</p>

          {/* Key Points */}
          {insight.key_points && insight.key_points.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Key Observations</h4>
              <ul className="space-y-1.5">
                {insight.key_points.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-neutral-600">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action Items */}
          {insight.action_items && insight.action_items.length > 0 && (
            <div className="bg-orange-50 rounded-lg p-3 border border-orange-100">
              <h4 className="text-xs font-semibold text-orange-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Action Items
              </h4>
              <ul className="space-y-1.5">
                {insight.action_items.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-orange-800 font-medium">
                    <span className="text-orange-500 mt-0.5">→</span>
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insight.created_at && (
            <div className="flex items-center gap-1 text-[10px] text-neutral-400">
              <Clock className="w-3 h-3" />
              Analyzed {new Date(insight.created_at).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MessageRow({ msg }: { msg: ChatMessage }) {
  const colorClass = msg.cluster ? CLUSTER_COLORS[msg.cluster] : '';
  return (
    <div className="flex items-start gap-3 py-2 px-3 hover:bg-neutral-50 rounded-lg text-sm">
      <div className="w-24 shrink-0">
        <div className="font-medium text-neutral-800 truncate text-xs">{msg.sender_name}</div>
        <div className="text-[10px] text-neutral-400">
          {new Date(msg.sent_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          {' '}
          {new Date(msg.sent_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      <div className="flex-1 text-neutral-700 break-words">{msg.text || `[${msg.message_type}]`}</div>
      {msg.cluster && (
        <span className={cn('text-[10px] px-1.5 py-0.5 rounded border shrink-0', colorClass)}>
          {msg.cluster.replace('_', ' ')}
        </span>
      )}
    </div>
  );
}

type View = 'insights' | 'messages';

export function ChatIntelPanel({ projectId }: { projectId: number }) {
  const [view, setView] = useState<View>('insights');
  const [stats, setStats] = useState<ChatStats | null>(null);
  const [insights, setInsights] = useState<ChatInsight[]>([]);
  const [clusters, setClusters] = useState<ChatCluster[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [search, setSearch] = useState('');
  const [activeCluster, setActiveCluster] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [projectId]);

  async function loadData() {
    setLoading(true);
    try {
      const [statsData, insightsData] = await Promise.all([
        chatIntelApi.getStats(projectId),
        chatIntelApi.getInsights(projectId),
      ]);
      setStats(statsData);
      setInsights(insightsData.insights || []);
      setClusters(insightsData.clusters || []);
    } catch (e) {
      console.error('Failed to load chat intel:', e);
    } finally {
      setLoading(false);
    }
  }

  async function loadMessages() {
    try {
      const data = await chatIntelApi.getMessages(projectId, {
        limit: 200,
        cluster: activeCluster || undefined,
        search: search || undefined,
      });
      setMessages(data.messages || []);
      if (data.clusters) setClusters(data.clusters);
    } catch (e) {
      console.error('Failed to load messages:', e);
    }
  }

  useEffect(() => {
    if (view === 'messages') loadMessages();
  }, [view, activeCluster, search]);

  async function runAnalysis() {
    setAnalyzing(true);
    try {
      const result = await chatIntelApi.analyze(projectId);
      if (result.error) {
        alert(result.error);
      } else {
        // Reload insights
        const insightsData = await chatIntelApi.getInsights(projectId);
        setInsights(insightsData.insights || []);
      }
    } catch (e: any) {
      alert('Analysis failed: ' + (e.message || e));
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-neutral-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading chat intelligence...
      </div>
    );
  }

  if (!stats || stats.total === 0) {
    return (
      <div className="text-center py-16 text-neutral-400">
        <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No chat messages found for this project.</p>
        <p className="text-xs mt-1">Add @SallyBDMBot to the client's Telegram group to start monitoring.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <MessageSquare className="w-4 h-4 text-neutral-400" />
            <span className="font-semibold text-neutral-900">{stats.total.toLocaleString()}</span>
            <span className="text-neutral-500">messages</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Users className="w-4 h-4 text-neutral-400" />
            <span className="font-semibold text-neutral-900">{stats.by_sender.length}</span>
            <span className="text-neutral-500">participants</span>
          </div>
          {stats.date_range && (
            <div className="text-xs text-neutral-400">
              {new Date(stats.date_range.first).toLocaleDateString()} — {new Date(stats.date_range.last).toLocaleDateString()}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-neutral-100">
            <button
              onClick={() => setView('insights')}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                view === 'insights' ? 'bg-white shadow-sm text-neutral-900' : 'text-neutral-500'
              )}
            >
              Insights
            </button>
            <button
              onClick={() => setView('messages')}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                view === 'messages' ? 'bg-white shadow-sm text-neutral-900' : 'text-neutral-500'
              )}
            >
              Messages
            </button>
          </div>

          <button
            onClick={runAnalysis}
            disabled={analyzing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {analyzing ? 'Analyzing...' : 'Analyze with Gemini'}
          </button>
        </div>
      </div>

      {/* Participants bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {stats.by_sender.slice(0, 6).map(s => (
          <span key={s.name} className="text-xs px-2 py-1 rounded-full bg-neutral-100 text-neutral-600">
            {s.name} <span className="text-neutral-400">({s.count})</span>
          </span>
        ))}
      </div>

      {/* INSIGHTS VIEW */}
      {view === 'insights' && (
        <div className="space-y-3">
          {insights.length === 0 ? (
            <div className="text-center py-12 text-neutral-400">
              <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No insights yet. Click "Analyze with Gemini" to generate cluster insights.</p>
            </div>
          ) : (
            // Group by topic, show latest per topic
            (() => {
              const latestByTopic = new Map<string, ChatInsight>();
              for (const i of insights) {
                if (!latestByTopic.has(i.topic)) latestByTopic.set(i.topic, i);
              }
              return Array.from(latestByTopic.values()).map(insight => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  cluster={clusters.find(c => c.id === insight.topic)}
                />
              ));
            })()
          )}
        </div>
      )}

      {/* MESSAGES VIEW */}
      {view === 'messages' && (
        <div className="space-y-3">
          {/* Filters */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Search messages..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && loadMessages()}
                className="w-full pl-9 pr-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              />
            </div>
            <select
              value={activeCluster || ''}
              onChange={e => setActiveCluster(e.target.value || null)}
              className="text-sm border border-neutral-200 rounded-lg px-3 py-2 focus:outline-none"
            >
              <option value="">All clusters</option>
              {clusters.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Messages list */}
          <div className="bg-white rounded-xl border border-neutral-200 divide-y divide-neutral-100 max-h-[600px] overflow-y-auto">
            {messages.length === 0 ? (
              <div className="text-center py-8 text-neutral-400 text-sm">No messages found</div>
            ) : (
              messages.map(msg => <MessageRow key={msg.id} msg={msg} />)
            )}
          </div>
        </div>
      )}
    </div>
  );
}
