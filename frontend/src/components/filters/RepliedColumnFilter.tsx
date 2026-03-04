import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

const OPTIONS = [
  { key: 'replied',    label: 'Replied',          dot: 'bg-green-500' },
  { key: 'no_reply',   label: 'Not Replied',      dot: 'bg-neutral-400' },
  { key: 'followup',   label: 'Needs Follow-up',  dot: 'bg-orange-500' },
] as const;

export const RepliedColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { repliedFilter, setRepliedFilter, followupFilter, setFollowupFilter, resetPage } = useContactsFilter();
  const { isDark } = useTheme();

  const activeKey = followupFilter === true ? 'followup' : repliedFilter === true ? 'replied' : repliedFilter === false ? 'no_reply' : null;

  useImperativeHandle(ref, () => ({
    isFilterActive: () => repliedFilter !== null || followupFilter === true,
    getModel: () => (activeKey ? { value: activeKey } : null),
    setModel: (model: { value: string } | null) => {
      if (!model) {
        setRepliedFilter(null);
        setFollowupFilter(null);
      } else if (model.value === 'replied') {
        setRepliedFilter(true);
        setFollowupFilter(null);
      } else if (model.value === 'no_reply') {
        setRepliedFilter(false);
        setFollowupFilter(null);
      } else if (model.value === 'followup') {
        setRepliedFilter(null);
        setFollowupFilter(true);
      }
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => {
    props.filterChangedCallback();
  }, [repliedFilter, followupFilter]);

  const handleSelect = (key: string) => {
    if (activeKey === key) {
      setRepliedFilter(null);
      setFollowupFilter(null);
    } else if (key === 'replied') {
      setRepliedFilter(true);
      setFollowupFilter(null);
    } else if (key === 'no_reply') {
      setRepliedFilter(false);
      setFollowupFilter(null);
    } else if (key === 'followup') {
      setRepliedFilter(null);
      setFollowupFilter(true);
    }
    resetPage();
  };

  return (
    <div className={cn("p-3 min-w-[160px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>REPLIED</span>
        {activeKey && (
          <button
            onClick={() => { setRepliedFilter(null); setFollowupFilter(null); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {OPTIONS.map(({ key, label, dot }) => {
          const isActive = activeKey === key;
          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? (isDark ? "bg-green-900/40 text-green-300 border-green-700" : "bg-green-100 text-green-700 border-green-300")
                  : (isDark ? "bg-neutral-700 text-neutral-300 border-neutral-600 hover:border-neutral-400" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className={cn("w-2 h-2 rounded-full shrink-0", dot)} />
              <span className="flex-1">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});

RepliedColumnFilter.displayName = 'RepliedColumnFilter';
