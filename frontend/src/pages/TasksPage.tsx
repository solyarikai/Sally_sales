import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, ChevronDown, ChevronRight, ListTodo, Loader2, RefreshCw, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { tasksApi, type TasksResponse } from '../api';

const priorityColors: Record<string, string> = {
  immediate: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
  high: 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800',
  medium: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800',
  low: 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600',
};

export function TasksPage() {
  const [data, setData] = useState<TasksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<'all' | 'pending' | 'completed'>('all');

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await tasksApi.getTasks();
      setData(response);
    } catch (err: any) {
      console.error('Failed to load tasks:', err);
      setError(err.userMessage || 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
    // Auto-refresh every 30 seconds to keep tasks in sync
    const interval = setInterval(loadTasks, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggleTask = (taskId: number) => {
    setExpandedTasks(prev => {
      const newSet = new Set(prev);
      if (newSet.has(taskId)) {
        newSet.delete(taskId);
      } else {
        newSet.add(taskId);
      }
      return newSet;
    });
  };

  const tasks = data?.tasks || [];
  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true;
    if (filter === 'pending') return task.status !== 'completed';
    if (filter === 'completed') return task.status === 'completed';
    return true;
  });

  const completedCount = data?.completed || 0;
  const pendingCount = data?.pending || 0;
  const totalSubtasks = data?.total_subtasks || 0;
  const completedSubtasks = data?.completed_subtasks || 0;
  const progressPercent = totalSubtasks > 0 ? Math.round((completedSubtasks / totalSubtasks) * 100) : 0;

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <div className="flex items-center gap-2 text-neutral-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading tasks...</span>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <p className="text-neutral-600 dark:text-neutral-400 mb-4">{error}</p>
        <button onClick={loadTasks} className="btn btn-primary">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <ListTodo className="w-8 h-8 text-neutral-700 dark:text-neutral-300" />
            <h1 className="text-2xl font-bold text-neutral-900 dark:text-white">Project Tasks</h1>
          </div>
          <button
            onClick={loadTasks}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-500 dark:text-neutral-400"
            title="Refresh tasks"
          >
            <RefreshCw className={cn("w-5 h-5", loading && "animate-spin")} />
          </button>
        </div>
        <p className="text-neutral-600 dark:text-neutral-400">
          Track progress on all project tasks (synced from <code className="text-xs bg-neutral-100 dark:bg-neutral-800 px-1 rounded">state/tasks.md</code>)
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4">
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">{tasks.length}</div>
          <div className="text-sm text-neutral-500 dark:text-neutral-400">Total Tasks</div>
        </div>
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{completedCount}</div>
          <div className="text-sm text-neutral-500 dark:text-neutral-400">Completed</div>
        </div>
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{pendingCount}</div>
          <div className="text-sm text-neutral-500 dark:text-neutral-400">Remaining</div>
        </div>
        <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {completedSubtasks}/{totalSubtasks}
          </div>
          <div className="text-sm text-neutral-500 dark:text-neutral-400">Subtasks Done</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Overall Progress</span>
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            {progressPercent}%
          </span>
        </div>
        <div className="h-3 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-4">
        {(['all', 'pending', 'completed'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              filter === f
                ? 'bg-black dark:bg-white text-white dark:text-black'
                : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
            )}
          >
            {f === 'all' && `All (${tasks.length})`}
            {f === 'pending' && `Pending (${pendingCount})`}
            {f === 'completed' && `Completed (${completedCount})`}
          </button>
        ))}
      </div>

      {/* Tasks list */}
      <div className="space-y-3">
        {filteredTasks.map(task => {
          const isExpanded = expandedTasks.has(task.id);
          const completedSubtaskCount = task.subtasks.filter(s => s.completed).length;
          const statusIcon = task.status === 'completed' 
            ? <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
            : task.status === 'in-progress'
            ? <Circle className="w-5 h-5 text-yellow-500 flex-shrink-0" />
            : <Circle className="w-5 h-5 text-neutral-300 dark:text-neutral-600 flex-shrink-0" />;
          
          return (
            <div
              key={task.id}
              className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 overflow-hidden"
            >
              {/* Task header */}
              <button
                onClick={() => toggleTask(task.id)}
                className="w-full p-4 flex items-center gap-3 hover:bg-neutral-50 dark:hover:bg-neutral-750 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="w-5 h-5 text-neutral-400 flex-shrink-0" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-neutral-400 flex-shrink-0" />
                )}
                
                {statusIcon}

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={cn(
                      'font-medium',
                      task.status === 'completed' 
                        ? 'text-neutral-500 dark:text-neutral-400 line-through' 
                        : 'text-neutral-900 dark:text-white'
                    )}>
                      Task {task.id}: {task.title}
                    </span>
                    <span className={cn(
                      'text-xs px-2 py-0.5 rounded-full border',
                      priorityColors[task.priority] || priorityColors.medium
                    )}>
                      {task.priority}
                    </span>
                    {task.status === 'in-progress' && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800">
                        in progress
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-0.5">{task.description}</p>
                </div>

                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                    {completedSubtaskCount}/{task.subtasks.length}
                  </div>
                  <div className="text-xs text-neutral-400 dark:text-neutral-500">subtasks</div>
                </div>
              </button>

              {/* Subtasks */}
              {isExpanded && task.subtasks.length > 0 && (
                <div className="border-t border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-850 p-4">
                  <div className="space-y-2">
                    {task.subtasks.map((subtask, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3 p-2 rounded-lg hover:bg-white dark:hover:bg-neutral-800 transition-colors"
                      >
                        {subtask.completed ? (
                          <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <Circle className="w-4 h-4 text-neutral-300 dark:text-neutral-600 mt-0.5 flex-shrink-0" />
                        )}
                        <span className={cn(
                          'text-sm',
                          subtask.completed 
                            ? 'text-neutral-500 dark:text-neutral-400 line-through' 
                            : 'text-neutral-700 dark:text-neutral-300'
                        )}>
                          {subtask.text}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filteredTasks.length === 0 && (
        <div className="text-center py-12 text-neutral-500 dark:text-neutral-400">
          <ListTodo className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No tasks found</p>
        </div>
      )}
    </div>
  );
}
