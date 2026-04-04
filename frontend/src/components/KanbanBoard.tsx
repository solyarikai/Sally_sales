import { useState, useCallback } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useDroppable } from '@dnd-kit/core';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { User, Building2, Briefcase, Clock } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import type { KanbanColumn, KanbanContact } from '../api';

// ─── Card ────────────────────────────────────────────────────────

function KanbanCard({
  contact,
  isDragging,
  onClick,
}: {
  contact: KanbanContact;
  isDragging?: boolean;
  onClick?: (contact: KanbanContact) => void;
}) {
  const { isDark } = useTheme();
  const t = themeColors(isDark);

  const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email || '—';
  const initials = contact.first_name?.[0]?.toUpperCase() || contact.email?.[0]?.toUpperCase() || '?';
  const lastActivity = contact.last_reply_at || contact.updated_at;
  const timeAgo = lastActivity ? formatTimeAgo(lastActivity) : null;

  return (
    <div
      onClick={() => onClick?.(contact)}
      className="rounded-lg px-3 py-2.5 cursor-pointer transition-all group"
      style={{
        background: isDark ? '#2d2d2d' : '#fff',
        border: `1px solid ${isDark ? '#3c3c3c' : '#e5e7eb'}`,
        boxShadow: isDragging ? '0 8px 25px rgba(0,0,0,0.15)' : '0 1px 2px rgba(0,0,0,0.04)',
        opacity: isDragging ? 0.9 : 1,
        transform: isDragging ? 'rotate(2deg)' : undefined,
      }}
    >
      <div className="flex items-start gap-2.5">
        {/* Avatar */}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-medium"
          style={{
            background: isDark ? '#3c3c3c' : '#f3f4f6',
            color: t.text3,
          }}
        >
          {initials}
        </div>

        <div className="flex-1 min-w-0">
          {/* Name */}
          <div className="text-[13px] font-medium truncate" style={{ color: t.text1 }}>
            {name}
          </div>

          {/* Company + Job */}
          {(contact.company_name || contact.job_title) && (
            <div className="flex items-center gap-1 mt-0.5">
              {contact.company_name && (
                <span className="text-[11px] truncate flex items-center gap-0.5" style={{ color: t.text3 }}>
                  <Building2 className="w-3 h-3 shrink-0" />
                  {contact.company_name}
                </span>
              )}
              {contact.company_name && contact.job_title && (
                <span className="text-[10px]" style={{ color: t.text5 }}>·</span>
              )}
              {contact.job_title && (
                <span className="text-[11px] truncate flex items-center gap-0.5" style={{ color: t.text4 }}>
                  <Briefcase className="w-3 h-3 shrink-0" />
                  {contact.job_title}
                </span>
              )}
            </div>
          )}

          {/* Tags row: segment + time */}
          <div className="flex items-center gap-1.5 mt-1.5">
            {contact.segment && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full"
                style={{
                  background: isDark ? '#3c3c3c' : '#f0f0f0',
                  color: t.text3,
                }}
              >
                {contact.segment}
              </span>
            )}
            {contact.project_name && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full"
                style={{
                  background: isDark ? '#1e3a5f' : '#dbeafe',
                  color: isDark ? '#93c5fd' : '#1d4ed8',
                }}
              >
                {contact.project_name}
              </span>
            )}
            {timeAgo && (
              <span className="text-[10px] flex items-center gap-0.5 ml-auto" style={{ color: t.text5 }}>
                <Clock className="w-3 h-3" />
                {timeAgo}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Sortable wrapper for drag
function SortableCard({
  contact,
  onClick,
}: {
  contact: KanbanContact;
  onClick?: (contact: KanbanContact) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `card-${contact.id}`,
    data: { type: 'card', contact },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <KanbanCard contact={contact} onClick={onClick} />
    </div>
  );
}

// ─── Column ──────────────────────────────────────────────────────

function KanbanColumnView({
  column,
  onCardClick,
}: {
  column: KanbanColumn;
  onCardClick?: (contact: KanbanContact) => void;
}) {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${column.key}`,
    data: { type: 'column', columnKey: column.key },
  });

  return (
    <div
      className="flex flex-col min-w-[280px] w-[280px] shrink-0"
      style={{ height: '100%' }}
    >
      {/* Column header */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-lg"
        style={{
          background: isDark ? '#252526' : '#f9fafb',
          borderBottom: `2px solid ${column.color}`,
        }}
      >
        <div
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ background: column.color }}
        />
        <span className="text-xs font-semibold" style={{ color: t.text1 }}>
          {column.label}
        </span>
        <span
          className="text-[11px] font-medium px-1.5 py-0.5 rounded-full ml-auto"
          style={{
            background: isDark ? '#3c3c3c' : '#e5e7eb',
            color: t.text3,
          }}
        >
          {column.count}
        </span>
      </div>

      {/* Cards area */}
      <div
        ref={setNodeRef}
        className="flex-1 overflow-y-auto space-y-1.5 p-1.5 rounded-b-lg transition-colors"
        style={{
          background: isOver
            ? (isDark ? '#2a2a35' : '#f0f4ff')
            : (isDark ? '#1e1e1e' : '#f3f4f6'),
          border: isOver
            ? `1px dashed ${column.color}`
            : `1px solid ${isDark ? '#2d2d2d' : '#e5e7eb'}`,
          borderTop: 'none',
        }}
      >
        {column.contacts.map(contact => (
          <SortableCard
            key={contact.id}
            contact={contact}
            onClick={onCardClick}
          />
        ))}
        {column.contacts.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <span className="text-[11px]" style={{ color: t.text5 }}>No contacts</span>
          </div>
        )}
        {column.count > column.contacts.length && (
          <div className="text-center py-1">
            <span className="text-[10px]" style={{ color: t.text5 }}>
              +{column.count - column.contacts.length} more
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Board ───────────────────────────────────────────────────────

// Column key -> default status for drag
const COLUMN_DEFAULT_STATUS: Record<string, string> = {
  new: 'new',
  contacted: 'sent',
  interested: 'replied',
  meeting: 'meeting_booked',
  closed_won: 'qualified',
  closed_lost: 'not_qualified',
};

export function KanbanBoard({
  columns,
  onStatusChange,
  onCardClick,
}: {
  columns: KanbanColumn[];
  onStatusChange: (contactId: number, newStatus: string, targetColumnKey: string) => void;
  onCardClick?: (contact: KanbanContact) => void;
}) {
  const [activeCard, setActiveCard] = useState<KanbanContact | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const { active } = event;
    const contact = active.data.current?.contact as KanbanContact | undefined;
    if (contact) setActiveCard(contact);
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCard(null);

    if (!over) return;

    const contact = active.data.current?.contact as KanbanContact | undefined;
    if (!contact) return;

    // Determine target column
    let targetColumnKey: string | null = null;
    if (over.data.current?.type === 'column') {
      targetColumnKey = over.data.current.columnKey;
    } else if (over.data.current?.type === 'card') {
      // Dropped on a card — find which column it belongs to
      const targetContact = over.data.current.contact as KanbanContact;
      const col = columns.find(c => c.contacts.some(ct => ct.id === targetContact.id));
      targetColumnKey = col?.key || null;
    }

    if (!targetColumnKey) return;

    // Check if moving to a different column
    const sourceCol = columns.find(c => c.contacts.some(ct => ct.id === contact.id));
    if (sourceCol?.key === targetColumnKey) return;

    const newStatus = COLUMN_DEFAULT_STATUS[targetColumnKey];
    if (newStatus) {
      onStatusChange(contact.id, newStatus, targetColumnKey);
    }
  }, [columns, onStatusChange]);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 h-full overflow-x-auto pb-2 px-3 pt-2">
        {columns.map(col => (
          <KanbanColumnView
            key={col.key}
            column={col}
            onCardClick={onCardClick}
          />
        ))}
      </div>

      <DragOverlay>
        {activeCard ? (
          <div className="w-[280px]">
            <KanbanCard contact={activeCard} isDragging />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 30) return `${diffDays}d`;
  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo`;
}
