import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { usePipelineFilter } from './PipelineFilterContext';
import { cn } from '../../lib/utils';
import { Target, XCircle, Layers } from 'lucide-react';

const OPTIONS = [
  { key: 'all' as const, label: 'All', icon: Layers },
  { key: 'targets' as const, label: 'Targets', icon: Target },
  { key: 'non-targets' as const, label: 'Non-targets', icon: XCircle },
];

export const PipelineTargetColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { targetFilter, setTargetFilter, resetPage } = usePipelineFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => targetFilter !== 'all',
    getModel: () => (targetFilter !== 'all' ? { value: targetFilter } : null),
    setModel: (model: { value: 'all' | 'targets' | 'non-targets' } | null) => {
      setTargetFilter(model?.value || 'all');
    },
    doesFilterPass: () => true, // Server-side filtering
  }));

  return (
    <div className="p-3 min-w-[160px]">
      <span className="text-xs font-medium text-neutral-500 mb-2 block">TARGET</span>
      <div className="flex flex-col gap-1">
        {OPTIONS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setTargetFilter(key); resetPage(); }}
            className={cn(
              "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
              targetFilter === key
                ? "bg-indigo-50 text-indigo-700 border-indigo-300"
                : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
});

PipelineTargetColumnFilter.displayName = 'PipelineTargetColumnFilter';
