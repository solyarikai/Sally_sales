import { useState } from 'react';
import { Loader2, Check, X, Circle, Square, RotateCcw, Edit2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { useJobProgress, type JobProgress } from '../hooks/useJobProgress';
import type { EnrichmentJob } from '../types';

interface JobProgressCardProps {
  job: EnrichmentJob;
  onComplete?: () => void;
  onStop?: () => void;
  onEdit?: (job: EnrichmentJob) => void;
  onRerun?: (job: EnrichmentJob) => void;
}

export function JobProgressCard({ job, onComplete, onStop, onEdit, onRerun }: JobProgressCardProps) {
  const [localProgress, setLocalProgress] = useState<JobProgress | null>(null);
  const [isStopping, setIsStopping] = useState(false);

  const { progress } = useJobProgress(
    job.status === 'processing' ? job.id : null,
    {
      onProgress: (p) => setLocalProgress(p),
      onComplete: () => onComplete?.(),
    }
  );

  const handleStop = async () => {
    setIsStopping(true);
    onStop?.();
  };

  const currentProgress = localProgress || progress;
  const percentage = currentProgress?.percentage ?? 
    (job.total_rows > 0 ? (job.processed_rows / job.total_rows) * 100 : 0);
  
  const isRunning = job.status === 'processing';
  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';
  const canRerun = isCompleted || isFailed || isCancelled;

  return (
    <div className={cn(
      "rounded-lg p-3 text-sm border",
      isRunning && "border-blue-200 bg-blue-50/50",
      isCompleted && "border-emerald-100 bg-emerald-50/30",
      isFailed && "border-red-100 bg-red-50/30",
      isCancelled && "border-neutral-200 bg-neutral-50"
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          {isRunning && <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />}
          {isCompleted && <Check className="w-3 h-3 text-emerald-600" />}
          {isFailed && <X className="w-3 h-3 text-red-600" />}
          {isCancelled && <Square className="w-3 h-3 text-neutral-500" />}
          {!isRunning && !isCompleted && !isFailed && !isCancelled && (
            <Circle className="w-3 h-3 text-neutral-400" />
          )}
          
          <span className="font-medium text-neutral-900 text-xs">
            {job.output_column}
          </span>
        </div>
        
        <div className="flex items-center gap-1">
          {canRerun && onEdit && (
            <button
              onClick={() => onEdit(job)}
              className="p-1 hover:bg-neutral-100 rounded text-neutral-400 hover:text-neutral-600"
              title="Edit & run again"
            >
              <Edit2 className="w-3 h-3" />
            </button>
          )}
          {canRerun && onRerun && (
            <button
              onClick={() => onRerun(job)}
              className="p-1 hover:bg-neutral-100 rounded text-neutral-400 hover:text-neutral-600"
              title="Run again"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          )}
          {isRunning && onStop && (
            <button
              onClick={handleStop}
              disabled={isStopping}
              className="p-1 hover:bg-red-100 rounded text-red-500"
            >
              {isStopping ? <Loader2 className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
            </button>
          )}
        </div>
      </div>

      {/* Progress */}
      {isRunning && (
        <div className="space-y-1">
          <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-600 transition-all duration-300"
              style={{ width: `${percentage}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-blue-700">
            <span>{currentProgress?.processed ?? job.processed_rows}/{currentProgress?.total ?? job.total_rows}</span>
            <span>{Math.round(percentage)}%</span>
          </div>
        </div>
      )}

      {/* Completed */}
      {isCompleted && (
        <div className="text-xs text-emerald-700">
          {job.processed_rows} rows {job.failed_rows > 0 && <span className="text-red-600">({job.failed_rows} failed)</span>}
        </div>
      )}

      {/* Cancelled */}
      {isCancelled && <p className="text-xs text-neutral-500">{job.processed_rows}/{job.total_rows} rows</p>}

      {/* Failed */}
      {isFailed && job.error_message && (
        <p className="text-xs text-red-600 truncate">{job.error_message}</p>
      )}
    </div>
  );
}
