import { useRef, useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Row,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Check, Circle, Loader2, X, Sparkles, Trash2, Edit2, Globe } from 'lucide-react';
import type { DataRow } from '../types';
import { cn, truncate } from '../lib/utils';

// Helper to check if column contains domains/websites
const isWebsiteColumn = (colName: string) => {
  const lowerName = colName.toLowerCase();
  return lowerName.includes('website') || 
         lowerName.includes('domain') || 
         lowerName.includes('url') ||
         lowerName === 'site';
};

// Helper to get domain from URL/website
const getDomain = (url: string): string => {
  if (!url || url === '--') return '';
  try {
    // Remove protocol if present
    let domain = url.replace(/^https?:\/\//, '').replace(/^www\./, '');
    // Remove path
    domain = domain.split('/')[0];
    return domain;
  } catch {
    return url;
  }
};

// Helper to get favicon path
const getFaviconPath = (website: string, projectName: string = 'maincard'): string => {
  const domain = getDomain(website);
  if (!domain) return '';
  
  // Generate filename (same logic as Python script)
  const safeDomain = domain.replace(/[^\w\-.]/g, '_').substring(0, 50);
  const hash = Array.from(domain).reduce((s, c) => Math.imul(31, s) + c.charCodeAt(0) | 0, 0);
  const hashStr = Math.abs(hash).toString(16).substring(0, 8);
  
  return `/favicons/${projectName}/${safeDomain}_${hashStr}.png`;
};

interface DataTableProps {
  data: DataRow[];
  columns: string[];
  onRenameColumn?: (oldName: string, newName: string) => void;
  onDeleteColumn?: (columnName: string, isEnriched: boolean) => void;
  onEditEnrichedColumn?: (columnName: string) => void;
}

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <Check className="w-3 h-3 text-emerald-600" />;
    case 'processing':
      return <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />;
    case 'failed':
      return <X className="w-3 h-3 text-red-600" />;
    default:
      return <Circle className="w-3 h-3 text-neutral-300" />;
  }
};

export function DataTable({ data, columns, onRenameColumn, onDeleteColumn, onEditEnrichedColumn }: DataTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [expandedCell, setExpandedCell] = useState<{ text: string; rect: DOMRect } | null>(null);
  const [editingColumn, setEditingColumn] = useState<string | null>(null);
  const [columnName, setColumnName] = useState('');

  const handleColumnDoubleClick = (col: string) => {
    setEditingColumn(col);
    setColumnName(col);
  };

  const handleColumnRename = () => {
    if (editingColumn && columnName.trim() && columnName !== editingColumn) {
      onRenameColumn?.(editingColumn, columnName.trim());
    }
    setEditingColumn(null);
  };

  const handleCellClick = (e: React.MouseEvent, text: string) => {
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setExpandedCell({ text, rect });
  };

  const enrichedColumns = useMemo(() => {
    const cols = new Set<string>();
    data.forEach((row) => {
      Object.keys(row.enriched_data || {}).forEach((key) => cols.add(key));
    });
    return Array.from(cols);
  }, [data]);

  const tableColumns = useMemo<ColumnDef<DataRow>[]>(() => {
    const cols: ColumnDef<DataRow>[] = [
      {
        id: 'status',
        header: '',
        cell: ({ row }) => <StatusIcon status={row.original.enrichment_status} />,
        size: 28,
      },
      {
        id: 'index',
        header: '#',
        cell: ({ row }) => <span className="text-neutral-400 font-mono text-xs">{row.original.row_index + 1}</span>,
        size: 36,
      },
    ];

    columns.forEach((col) => {
      cols.push({
        id: `data_${col}`,
        header: () => (
          editingColumn === col ? (
            <input
              type="text"
              value={columnName}
              onChange={(e) => setColumnName(e.target.value)}
              onBlur={handleColumnRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleColumnRename();
                if (e.key === 'Escape') setEditingColumn(null);
              }}
              autoFocus
              className="w-full px-1 py-0.5 text-xs bg-white border border-blue-400 rounded focus:outline-none"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span 
              className="cursor-pointer hover:text-neutral-700"
              onDoubleClick={() => handleColumnDoubleClick(col)}
            >
              {col}
            </span>
          )
        ),
        cell: ({ row }) => {
          const text = String(row.original.data[col] || '');
          const isWebsite = isWebsiteColumn(col);
          const faviconPath = isWebsite ? getFaviconPath(text) : '';
          
          return (
            <div
              className="text-neutral-700 cursor-pointer select-none hover:bg-neutral-100 rounded px-1 -mx-1 flex items-center gap-2"
              onClick={(e) => handleCellClick(e, text)}
            >
              {isWebsite && text && text !== '--' && (
                <img 
                  src={faviconPath}
                  alt=""
                  className="w-4 h-4 rounded flex-shrink-0"
                  onError={(e) => {
                    // Fallback to globe icon if favicon fails to load
                    e.currentTarget.style.display = 'none';
                    const parent = e.currentTarget.parentElement;
                    if (parent && !parent.querySelector('.fallback-icon')) {
                      const icon = document.createElement('div');
                      icon.className = 'fallback-icon w-4 h-4 flex items-center justify-center text-neutral-400';
                      icon.innerHTML = '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>';
                      parent.insertBefore(icon, parent.firstChild);
                    }
                  }}
                />
              )}
              <span className="truncate">{truncate(text, 40)}</span>
            </div>
          );
        },
        size: 140,
      });
    });

    enrichedColumns.forEach((col) => {
      cols.push({
        id: `enriched_${col}`,
        header: () => (
          <div className="flex items-center gap-1 group/header">
            <Sparkles className="w-3 h-3 text-orange-500" />
            <span>{col}</span>
            <div className="flex items-center gap-0.5 ml-auto opacity-0 group-hover/header:opacity-100 transition-opacity">
              {onEditEnrichedColumn && (
                <button
                  onClick={(e) => { e.stopPropagation(); onEditEnrichedColumn(col); }}
                  className="p-0.5 hover:bg-neutral-200 rounded"
                  title="Edit prompt"
                >
                  <Edit2 className="w-3 h-3 text-neutral-400" />
                </button>
              )}
              {onDeleteColumn && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteColumn(col, true); }}
                  className="p-0.5 hover:bg-red-100 rounded"
                  title="Delete column"
                >
                  <Trash2 className="w-3 h-3 text-red-500" />
                </button>
              )}
            </div>
          </div>
        ),
        cell: ({ row }) => {
          const text = String(row.original.enriched_data[col] || '');
          return (
            <div
              className="text-neutral-900 font-medium cursor-pointer select-none hover:bg-orange-50 rounded px-1 -mx-1"
              onClick={(e) => handleCellClick(e, text)}
            >
              {truncate(text, 50)}
            </div>
          );
        },
        size: 180,
      });
    });

    return cols;
  }, [columns, enrichedColumns, data, editingColumn, columnName]);

  const table = useReactTable({
    data,
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
  });

  const { rows: tableRows } = table.getRowModel();

  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 20,
  });

  const virtualRows = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const paddingBottom = virtualRows.length > 0 ? totalSize - (virtualRows[virtualRows.length - 1]?.end ?? 0) : 0;

  // Pinned columns width (status + index)
  const pinnedWidth = 28 + 36;

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-64 text-neutral-400 text-sm">No data</div>;
  }

  return (
    <>
      <div ref={parentRef} className="h-full overflow-auto border border-neutral-200 rounded-lg bg-white">
        <div className="relative" style={{ minWidth: pinnedWidth + columns.length * 140 + enrichedColumns.length * 180 }}>
          {/* Header */}
          <div className="sticky top-0 z-20 flex bg-neutral-50 border-b border-neutral-200">
            {/* Pinned header */}
            <div className="sticky left-0 z-30 flex bg-neutral-50 border-r border-neutral-200">
              {table.getHeaderGroups()[0]?.headers.slice(0, 2).map((header) => (
                <div
                  key={header.id}
                  className="flex items-center px-1 py-2 text-xs font-medium text-neutral-500 uppercase"
                  style={{ width: header.getSize(), height: 36 }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </div>
              ))}
            </div>
            {/* Scrollable header */}
            <div className="flex">
              {table.getHeaderGroups()[0]?.headers.slice(2).map((header) => (
                <div
                  key={header.id}
                  className="px-2 py-2 text-xs font-medium text-neutral-500 uppercase whitespace-nowrap"
                  style={{ width: header.getSize(), minWidth: header.getSize() }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </div>
              ))}
            </div>
          </div>

          {/* Body */}
          <div style={{ height: totalSize }}>
            {paddingTop > 0 && <div style={{ height: paddingTop }} />}
            {virtualRows.map((virtualRow) => {
              const row = tableRows[virtualRow.index] as Row<DataRow>;
              return (
                <div
                  key={row.id}
                  className="flex border-b border-neutral-100 hover:bg-neutral-50"
                  style={{ height: 36 }}
                >
                  {/* Pinned cells */}
                  <div className="sticky left-0 z-10 flex bg-inherit border-r border-neutral-100">
                    {row.getVisibleCells().slice(0, 2).map((cell) => (
                      <div
                        key={cell.id}
                        className="px-1 py-1.5 flex items-center"
                        style={{ width: cell.column.getSize() }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </div>
                    ))}
                  </div>
                  {/* Scrollable cells */}
                  <div className="flex">
                    {row.getVisibleCells().slice(2).map((cell) => (
                      <div
                        key={cell.id}
                        className="px-2 py-1.5 flex items-center text-sm whitespace-nowrap overflow-hidden"
                        style={{ width: cell.column.getSize(), minWidth: cell.column.getSize() }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {paddingBottom > 0 && <div style={{ height: paddingBottom }} />}
          </div>
        </div>
      </div>

      {/* Cell expansion popup */}
      {expandedCell && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setExpandedCell(null)} />
          <div 
            className="fixed z-50 bg-white rounded-lg shadow-xl border border-neutral-200 max-w-md max-h-64 overflow-auto p-3"
            style={{
              top: Math.min(expandedCell.rect.top, window.innerHeight - 280),
              left: Math.min(expandedCell.rect.left, window.innerWidth - 420),
            }}
          >
            <p className="text-sm whitespace-pre-wrap text-neutral-800">{expandedCell.text}</p>
          </div>
        </>
      )}
    </>
  );
}
