import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Zap, Users, MessageSquare, Building2, FolderOpen, 
  Clock, TrendingUp, Plus, ArrowRight, RefreshCw,
  Moon, Sun, Mail, CheckCircle2, XCircle, AlertCircle,
  Calendar, Activity
} from 'lucide-react';
import { dashboardApi, type DashboardResponse, type ActivityItem } from '../api';
import { cn, formatNumber } from '../lib/utils';

// Dark mode hook
function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) return saved === 'true';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    localStorage.setItem('darkMode', String(isDark));
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  return [isDark, setIsDark] as const;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [isDark, setIsDark] = useDarkMode();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await dashboardApi.getStats();
      setData(response);
    } catch (err: any) {
      console.error('Failed to load dashboard:', err);
      setError(err.userMessage || 'Failed to load dashboard data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    // Refresh every 60 seconds
    const interval = setInterval(loadDashboard, 60000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading && !data) {
    return (
      <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900 flex items-center justify-center">
        <div className="flex items-center gap-2 text-neutral-500 dark:text-neutral-400">
          <RefreshCw className="w-5 h-5 animate-spin" />
          Loading dashboard...
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-neutral-600 dark:text-neutral-400 mb-4">{error}</p>
          <button onClick={loadDashboard} className="btn btn-primary">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const stats = data?.stats;

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
                <span className="text-white font-bold text-lg">L</span>
              </div>
              <div>
                <h1 className="text-lg font-bold text-neutral-900 dark:text-white">LeadGen Dashboard</h1>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">Reply Automation Hub</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={loadDashboard}
                disabled={isLoading}
                className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-500 dark:text-neutral-400"
                title="Refresh"
              >
                <RefreshCw className={cn("w-5 h-5", isLoading && "animate-spin")} />
              </button>
              <button
                onClick={() => setIsDark(!isDark)}
                className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-500 dark:text-neutral-400"
                title={isDark ? 'Light mode' : 'Dark mode'}
              >
                {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Quick Actions */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <QuickAction
              icon={<Plus className="w-5 h-5" />}
              label="New Automation"
              onClick={() => navigate('/replies')}
              color="violet"
            />
            <QuickAction
              icon={<Users className="w-5 h-5" />}
              label="View Contacts"
              onClick={() => navigate('/contacts')}
              color="blue"
            />
            <QuickAction
              icon={<MessageSquare className="w-5 h-5" />}
              label="View Replies"
              onClick={() => navigate('/replies')}
              color="emerald"
            />
            <QuickAction
              icon={<Building2 className="w-5 h-5" />}
              label="Companies"
              onClick={() => navigate('/')}
              color="amber"
            />
          </div>
        </div>

        {/* Main Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Automations Card */}
          <StatCard
            title="Automations"
            icon={<Zap className="w-5 h-5" />}
            iconBg="bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400"
            onClick={() => navigate('/replies')}
          >
            <div className="text-3xl font-bold text-neutral-900 dark:text-white mb-1">
              {formatNumber(stats?.automations.total || 0)}
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                {stats?.automations.active || 0} active
              </span>
              <span className="flex items-center gap-1 text-neutral-400">
                <span className="w-2 h-2 rounded-full bg-neutral-300 dark:bg-neutral-600" />
                {stats?.automations.paused || 0} paused
              </span>
            </div>
          </StatCard>

          {/* Replies Card */}
          <StatCard
            title="Replies"
            icon={<Mail className="w-5 h-5" />}
            iconBg="bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
            onClick={() => navigate('/replies')}
          >
            <div className="text-3xl font-bold text-neutral-900 dark:text-white mb-1">
              {formatNumber(stats?.replies.total || 0)}
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Calendar className="w-3 h-3" />
                {stats?.replies.today || 0} today
              </span>
              <span className="text-neutral-400">
                {stats?.replies.this_week || 0} this week
              </span>
            </div>
          </StatCard>

          {/* Contacts Card */}
          <StatCard
            title="Contacts"
            icon={<Users className="w-5 h-5" />}
            iconBg="bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
            onClick={() => navigate('/contacts')}
          >
            <div className="text-3xl font-bold text-neutral-900 dark:text-white mb-1">
              {formatNumber(stats?.contacts.total || 0)}
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-emerald-600 dark:text-emerald-400">
                {stats?.contacts.qualified || 0} qualified
              </span>
              <span className="text-neutral-400">
                {stats?.contacts.replied || 0} replied
              </span>
            </div>
          </StatCard>

          {/* Pending Actions Card */}
          <StatCard
            title="Pending"
            icon={<Clock className="w-5 h-5" />}
            iconBg="bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400"
            onClick={() => navigate('/replies')}
          >
            <div className="text-3xl font-bold text-neutral-900 dark:text-white mb-1">
              {formatNumber(stats?.replies.pending || 0)}
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-3 h-3" />
                {stats?.replies.approved || 0} approved
              </span>
              <span className="flex items-center gap-1 text-neutral-400">
                <XCircle className="w-3 h-3" />
                {stats?.replies.dismissed || 0}
              </span>
            </div>
          </StatCard>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Reply Categories */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-neutral-700 p-6">
              <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-violet-500" />
                Reply Categories
              </h3>
              
              {stats?.replies.by_category && Object.keys(stats.replies.by_category).length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(stats.replies.by_category)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6)
                    .map(([category, count]) => {
                      const percentage = stats.replies.total > 0 
                        ? Math.round((count / stats.replies.total) * 100) 
                        : 0;
                      const categoryInfo = getCategoryInfo(category);
                      
                      return (
                        <div key={category} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-2">
                              <span>{categoryInfo.emoji}</span>
                              <span className="text-neutral-700 dark:text-neutral-300">{categoryInfo.label}</span>
                            </span>
                            <span className="text-neutral-500 dark:text-neutral-400">{formatNumber(count)}</span>
                          </div>
                          <div className="h-2 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
                            <div 
                              className={cn("h-full rounded-full transition-all", categoryInfo.color)}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              ) : (
                <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No replies yet</p>
                </div>
              )}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-neutral-700 p-6">
              <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-500" />
                Recent Activity
              </h3>
              
              {data?.recent_activity && data.recent_activity.length > 0 ? (
                <div className="space-y-3">
                  {data.recent_activity.map((item) => (
                    <ActivityRow 
                      key={item.id} 
                      item={item} 
                      onClick={() => item.link && navigate(item.link)}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                  <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No recent activity</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Reply Statistics Summary */}
        <div className="bg-white dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-neutral-700 p-6 mt-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-neutral-900 dark:text-white flex items-center gap-2">
              <Mail className="w-5 h-5 text-violet-500" />
              Reply Statistics
            </h3>
            <button
              onClick={() => navigate('/replies')}
              className="text-sm text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </button>
          </div>
          
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl text-center">
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {formatNumber(stats?.replies.by_category?.interested || 0)}
              </div>
              <div className="text-xs text-emerald-700 dark:text-emerald-300 mt-1">Interested</div>
            </div>
            <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {formatNumber(stats?.replies.by_category?.meeting_request || 0)}
              </div>
              <div className="text-xs text-blue-700 dark:text-blue-300 mt-1">Meetings</div>
            </div>
            <div className="p-3 bg-cyan-50 dark:bg-cyan-900/20 rounded-xl text-center">
              <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">
                {formatNumber(stats?.replies.by_category?.question || 0)}
              </div>
              <div className="text-xs text-cyan-700 dark:text-cyan-300 mt-1">Questions</div>
            </div>
            <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-center">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                {formatNumber(stats?.replies.by_category?.not_interested || 0)}
              </div>
              <div className="text-xs text-red-700 dark:text-red-300 mt-1">Not Interested</div>
            </div>
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl text-center">
              <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                {formatNumber(stats?.replies.by_category?.out_of_office || 0)}
              </div>
              <div className="text-xs text-amber-700 dark:text-amber-300 mt-1">Out of Office</div>
            </div>
            <div className="p-3 bg-neutral-100 dark:bg-neutral-700 rounded-xl text-center">
              <div className="text-2xl font-bold text-neutral-600 dark:text-neutral-300">
                {formatNumber((stats?.replies.by_category?.unsubscribe || 0) + (stats?.replies.by_category?.wrong_person || 0) + (stats?.replies.by_category?.other || 0))}
              </div>
              <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">Other</div>
            </div>
          </div>
          
          {/* Approval Status Row */}
          <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-700">
            <div className="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl">
              <Clock className="w-5 h-5 text-amber-500" />
              <div>
                <div className="text-lg font-semibold text-neutral-900 dark:text-white">{formatNumber(stats?.replies.pending || 0)}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Pending Review</div>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              <div>
                <div className="text-lg font-semibold text-neutral-900 dark:text-white">{formatNumber(stats?.replies.approved || 0)}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Approved</div>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-neutral-100 dark:bg-neutral-700 rounded-xl">
              <XCircle className="w-5 h-5 text-neutral-400" />
              <div>
                <div className="text-lg font-semibold text-neutral-900 dark:text-white">{formatNumber(stats?.replies.dismissed || 0)}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">Dismissed</div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Stats Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
          <MiniStat 
            label="Companies" 
            value={stats?.companies_count || 0} 
            icon={<Building2 className="w-4 h-4" />}
          />
          <MiniStat 
            label="Projects" 
            value={stats?.projects_count || 0} 
            icon={<FolderOpen className="w-4 h-4" />}
          />
          <MiniStat 
            label="Leads" 
            value={stats?.contacts.leads || 0} 
            icon={<Users className="w-4 h-4" />}
          />
          <MiniStat 
            label="Contacted" 
            value={stats?.contacts.contacted || 0} 
            icon={<Mail className="w-4 h-4" />}
          />
        </div>
      </main>
    </div>
  );
}

// Helper Components

interface QuickActionProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  color: 'violet' | 'blue' | 'emerald' | 'amber';
}

function QuickAction({ icon, label, onClick, color }: QuickActionProps) {
  const colorClasses = {
    violet: 'bg-violet-500 hover:bg-violet-600 shadow-violet-500/25',
    blue: 'bg-blue-500 hover:bg-blue-600 shadow-blue-500/25',
    emerald: 'bg-emerald-500 hover:bg-emerald-600 shadow-emerald-500/25',
    amber: 'bg-amber-500 hover:bg-amber-600 shadow-amber-500/25',
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center justify-center gap-2 p-4 rounded-xl text-white font-medium shadow-lg transition-all hover:scale-105",
        colorClasses[color]
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

interface StatCardProps {
  title: string;
  icon: React.ReactNode;
  iconBg: string;
  children: React.ReactNode;
  onClick?: () => void;
}

function StatCard({ title, icon, iconBg, children, onClick }: StatCardProps) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "bg-white dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-neutral-700 p-6 transition-all",
        onClick && "cursor-pointer hover:shadow-lg hover:border-neutral-300 dark:hover:border-neutral-600"
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-neutral-500 dark:text-neutral-400">{title}</span>
        <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", iconBg)}>
          {icon}
        </div>
      </div>
      {children}
      {onClick && (
        <div className="mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-700">
          <span className="text-sm text-violet-600 dark:text-violet-400 flex items-center gap-1 group-hover:gap-2 transition-all">
            View details <ArrowRight className="w-4 h-4" />
          </span>
        </div>
      )}
    </div>
  );
}

interface ActivityRowProps {
  item: ActivityItem;
  onClick?: () => void;
}

function ActivityRow({ item, onClick }: ActivityRowProps) {
  const typeColors = {
    reply: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400',
    automation: 'bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400',
    contact: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
  };

  const bgColor = typeColors[item.type as keyof typeof typeColors] || 'bg-neutral-100 dark:bg-neutral-700';

  return (
    <div 
      onClick={onClick}
      className={cn(
        "flex items-start gap-3 p-3 rounded-xl transition-colors",
        onClick && "cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-700/50"
      )}
    >
      <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-lg", bgColor)}>
        {item.icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">{item.title}</p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">{item.description}</p>
      </div>
      <div className="text-xs text-neutral-400 dark:text-neutral-500 flex-shrink-0">
        {formatTimeAgo(item.timestamp)}
      </div>
    </div>
  );
}

interface MiniStatProps {
  label: string;
  value: number;
  icon: React.ReactNode;
}

function MiniStat({ label, value, icon }: MiniStatProps) {
  return (
    <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4 flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-neutral-100 dark:bg-neutral-700 flex items-center justify-center text-neutral-500 dark:text-neutral-400">
        {icon}
      </div>
      <div>
        <div className="text-lg font-semibold text-neutral-900 dark:text-white">{formatNumber(value)}</div>
        <div className="text-xs text-neutral-500 dark:text-neutral-400">{label}</div>
      </div>
    </div>
  );
}

// Helper functions

function getCategoryInfo(category: string) {
  const categories: Record<string, { label: string; emoji: string; color: string }> = {
    interested: { label: 'Interested', emoji: '🟢', color: 'bg-emerald-500' },
    meeting_request: { label: 'Meeting', emoji: '📅', color: 'bg-blue-500' },
    not_interested: { label: 'Not Interested', emoji: '🔴', color: 'bg-red-500' },
    out_of_office: { label: 'Out of Office', emoji: '🏖️', color: 'bg-amber-500' },
    wrong_person: { label: 'Wrong Person', emoji: '🔄', color: 'bg-purple-500' },
    unsubscribe: { label: 'Unsubscribe', emoji: '🚫', color: 'bg-neutral-500' },
    question: { label: 'Question', emoji: '❓', color: 'bg-cyan-500' },
    other: { label: 'Other', emoji: '📧', color: 'bg-neutral-400' },
  };
  
  return categories[category] || { label: category, emoji: '📧', color: 'bg-neutral-400' };
}

function formatTimeAgo(timestamp: string) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default DashboardPage;
