import { useEffect, useState, useCallback } from 'react';
import { Plus, RefreshCw, Trash2, Download, Filter, X, Edit2, Check, PanelLeftClose, PanelLeft, FolderPlus, Folder, ChevronRight, ChevronDown, Database } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { datasetsApi, enrichmentApi, foldersApi } from '../api';
import { DataTable } from '../components/DataTable';
import { ImportModal } from '../components/ImportModal';
import { EnrichmentPanel } from '../components/EnrichmentPanel';
import { ExportModal } from '../components/ExportModal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { cn, formatNumber } from '../lib/utils';
import type { Dataset, EnrichmentJob, DataRow, Folder as FolderType } from '../types';

export function DatasetsPage() {
  const {
    datasets,
    setDatasets,
    currentDataset,
    setCurrentDataset,
    rows,
    setRows,
    selectedRowIds,
    selectAllRows,
    clearSelection,
    removeDataset,
    updateDataset,
  } = useAppStore();

  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [activeJobs, setActiveJobs] = useState<EnrichmentJob[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [filterColumn, setFilterColumn] = useState<string | null>(null);
  const [filterOperator, setFilterOperator] = useState<'contains' | 'not_contains' | 'equals' | 'not_equals' | 'empty' | 'not_empty'>('contains');
  const [filterValue, setFilterValue] = useState('');
  const [filteredRows, setFilteredRows] = useState<DataRow[]>([]);
  
  // Sidebar collapse state
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [startEnrichInCreateMode, setStartEnrichInCreateMode] = useState(false);
  const [editColumnName, setEditColumnName] = useState<string | null>(null);
  
  // Confirm dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });
  
  // API cost tracking
  const [totalCost, setTotalCost] = useState(0);
  
  const [allRowsLoaded, setAllRowsLoaded] = useState(false);
  const pageSize = 100; // Initial preview size

  // Folder state
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<number>>(new Set());
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFolderId, setEditingFolderId] = useState<number | null>(null);
  const [editingFolderName, setEditingFolderName] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('total_api_cost');
    if (saved) setTotalCost(parseFloat(saved));
  }, []);

  useEffect(() => {
    const handleCostUpdate = (e: CustomEvent) => {
      const newCost = e.detail.cost;
      setTotalCost(prev => {
        const updated = prev + newCost;
        localStorage.setItem('total_api_cost', updated.toString());
        return updated;
      });
    };
    window.addEventListener('api-cost-update' as any, handleCostUpdate);
    return () => window.removeEventListener('api-cost-update' as any, handleCostUpdate);
  }, []);

  useEffect(() => {
    loadDatasets();
    loadFolders();
  }, []);

  const loadFolders = async () => {
    try {
      const data = await foldersApi.list();
      setFolders(data);
    } catch (err) {
      console.error('Failed to load folders:', err);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await foldersApi.create(newFolderName.trim());
      setNewFolderName('');
      setCreatingFolder(false);
      loadFolders();
    } catch (err) {
      console.error('Failed to create folder:', err);
    }
  };

  const handleRenameFolder = async (folderId: number) => {
    if (!editingFolderName.trim()) return;
    try {
      await foldersApi.update(folderId, { name: editingFolderName.trim() });
      setEditingFolderId(null);
      loadFolders();
    } catch (err) {
      console.error('Failed to rename folder:', err);
    }
  };

  const handleDeleteFolder = async (folderId: number) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Folder',
      message: 'Are you sure you want to delete this folder? Datasets inside will be moved to root.',
      onConfirm: async () => {
        try {
          await foldersApi.delete(folderId);
          loadFolders();
          loadDatasets();
        } catch (err) {
          console.error('Failed to delete folder:', err);
        }
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      },
    });
  };

  const handleMoveToFolder = async (datasetId: number, folderId: number | null) => {
    try {
      await datasetsApi.update(datasetId, { folder_id: folderId || 0 });
      loadDatasets();
    } catch (err) {
      console.error('Failed to move dataset:', err);
    }
  };

  const toggleFolder = (folderId: number) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (currentDataset) {
      loadRows(currentDataset.id, false);
      loadJobs(currentDataset.id);
      setEditName(currentDataset.name);
      setAllRowsLoaded(false);
    }
  }, [currentDataset]);

  useEffect(() => {
    if (filterColumn) {
      const filtered = rows.filter(row => {
        const rawValue = row.data[filterColumn] ?? row.enriched_data[filterColumn] ?? '';
        const value = String(rawValue).toLowerCase();
        const searchValue = filterValue.toLowerCase();
        
        switch (filterOperator) {
          case 'contains':
            return value.includes(searchValue);
          case 'not_contains':
            return !value.includes(searchValue);
          case 'equals':
            return value === searchValue;
          case 'not_equals':
            return value !== searchValue;
          case 'empty':
            return value === '' || rawValue === null || rawValue === undefined;
          case 'not_empty':
            return value !== '' && rawValue !== null && rawValue !== undefined;
          default:
            return true;
        }
      });
      setFilteredRows(filtered);
    } else {
      setFilteredRows(rows);
    }
  }, [rows, filterColumn, filterValue, filterOperator]);

  const loadDatasets = async () => {
    try {
      const data = await datasetsApi.list();
      setDatasets(data.datasets);
    } catch (err) {
      console.error('Failed to load datasets:', err);
    }
  };

  const loadRows = async (datasetId: number, loadAll: boolean = false) => {
    setIsLoading(true);
    try {
      const limit = loadAll ? 10000 : pageSize;
      const data = await datasetsApi.getRows(datasetId, 1, limit);
      setRows(data.rows);
      setTotalRows(data.total);
      setAllRowsLoaded(loadAll || data.rows.length >= data.total);
    } catch (err) {
      console.error('Failed to load rows:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAllRows = async () => {
    if (currentDataset) {
      await loadRows(currentDataset.id, true);
    }
  };

  const loadJobs = async (datasetId: number) => {
    try {
      const jobs = await enrichmentApi.listJobs(datasetId);
      setActiveJobs(jobs.filter(j => j.status === 'processing'));
    } catch (err) {
      console.error('Failed to load jobs:', err);
    }
  };

  const handleRefresh = useCallback(() => {
    if (currentDataset) {
      loadRows(currentDataset.id, allRowsLoaded);
      loadJobs(currentDataset.id);
    }
  }, [currentDataset, allRowsLoaded]);

  const handleRenameColumn = async (oldName: string, newName: string) => {
    if (!currentDataset) return;
    try {
      await datasetsApi.renameColumn(currentDataset.id, oldName, newName);
      // Update local dataset columns
      const updatedColumns = currentDataset.columns.map(c => c === oldName ? newName : c);
      updateDataset({ ...currentDataset, columns: updatedColumns });
      // Reload rows to reflect the renamed column
      await loadRows(currentDataset.id, allRowsLoaded);
    } catch (err) {
      console.error('Failed to rename column:', err);
    }
  };

  const handleDeleteColumn = async (columnName: string, isEnriched: boolean) => {
    if (!currentDataset) return;
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Column',
      message: `Are you sure you want to delete "${columnName}"? This will remove all data in this column.`,
      onConfirm: async () => {
        try {
          await datasetsApi.deleteColumn(currentDataset.id, columnName, isEnriched);
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
          await loadRows(currentDataset.id, allRowsLoaded);
        } catch (err) {
          console.error('Failed to delete column:', err);
        }
      },
    });
  };

  const handleEditEnrichedColumn = (columnName: string) => {
    // Open enrichment panel with the column's prompt pre-filled
    setRightSidebarOpen(true);
    setEditColumnName(columnName);
    // Clear edit mode after a short delay to allow component to capture the value
    setTimeout(() => setEditColumnName(null), 100);
  };

  const handleDelete = (dataset: Dataset) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Dataset',
      message: `Are you sure you want to delete "${dataset.name}"? This action cannot be undone.`,
      onConfirm: async () => {
        try {
          await datasetsApi.delete(dataset.id);
          removeDataset(dataset.id);
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
        } catch (err) {
          console.error('Failed to delete dataset:', err);
        }
      },
    });
  };

  const handleRename = async () => {
    if (!currentDataset || !editName.trim()) return;
    try {
      await datasetsApi.rename(currentDataset.id, editName.trim());
      updateDataset({ ...currentDataset, name: editName.trim() });
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to rename dataset:', err);
    }
  };

  const handleDeleteSelectedRows = () => {
    if (selectedRowIds.size === 0) return;
    
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Rows',
      message: `Are you sure you want to delete ${selectedRowIds.size} selected rows? This action cannot be undone.`,
      onConfirm: async () => {
        try {
          await datasetsApi.deleteRows(currentDataset!.id, Array.from(selectedRowIds));
          clearSelection();
          handleRefresh();
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
        } catch (err) {
          console.error('Failed to delete rows:', err);
        }
      },
    });
  };


  const allColumns = currentDataset ? [
    ...currentDataset.columns,
    ...Object.keys(rows[0]?.enriched_data || {})
  ] : [];

  return (
    <div className="h-full flex">
      {/* Dataset list sidebar - Collapsible */}
      <div className={cn(
        "h-full border-r border-neutral-200 flex flex-col bg-white transition-all duration-300 flex-shrink-0",
        leftSidebarOpen ? "w-60" : "w-12"
      )}>
        {leftSidebarOpen ? (
          <>
            <div className="p-3 border-b border-neutral-200 flex items-center gap-2">
              <button
                onClick={() => setIsImportOpen(true)}
                className="btn btn-primary flex-1 text-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Import</span>
              </button>
              <button
                onClick={() => setCreatingFolder(true)}
                className="btn btn-ghost btn-icon"
                title="New folder"
              >
                <FolderPlus className="w-4 h-4" />
              </button>
              <button
                onClick={() => setLeftSidebarOpen(false)}
                className="btn btn-ghost btn-icon"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-2">
              {/* New folder input */}
              {creatingFolder && (
                <div className="mb-2 flex items-center gap-1">
                  <input
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="Folder name"
                    className="input input-sm flex-1"
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                  />
                  <button onClick={handleCreateFolder} className="btn btn-icon btn-sm btn-primary">
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => { setCreatingFolder(false); setNewFolderName(''); }} className="btn btn-icon btn-sm btn-secondary">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Folders */}
              {folders.map((folder) => {
                const folderDatasets = datasets.filter(d => d.folder_id === folder.id);
                const isExpanded = expandedFolders.has(folder.id);
                
                return (
                  <div key={folder.id} className="mb-1">
                    <div 
                      className="group flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-neutral-100 cursor-pointer"
                      onClick={() => toggleFolder(folder.id)}
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3.5 h-3.5 text-neutral-400" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-neutral-400" />
                      )}
                      <Folder className="w-4 h-4 text-neutral-500" />
                      {editingFolderId === folder.id ? (
                        <input
                          type="text"
                          value={editingFolderName}
                          onChange={(e) => setEditingFolderName(e.target.value)}
                          className="input input-sm flex-1 text-xs"
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            e.stopPropagation();
                            if (e.key === 'Enter') handleRenameFolder(folder.id);
                            if (e.key === 'Escape') setEditingFolderId(null);
                          }}
                          onBlur={() => handleRenameFolder(folder.id)}
                        />
                      ) : (
                        <span 
                          className="text-sm font-medium flex-1 truncate"
                          onDoubleClick={(e) => {
                            e.stopPropagation();
                            setEditingFolderId(folder.id);
                            setEditingFolderName(folder.name);
                          }}
                        >
                          {folder.name}
                        </span>
                      )}
                      <span className="text-xs text-neutral-400">{folderDatasets.length}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id); }}
                        className="p-1 opacity-0 group-hover:opacity-100 hover:bg-neutral-200 rounded"
                      >
                        <Trash2 className="w-3 h-3 text-neutral-500" />
                      </button>
                    </div>
                    
                    {isExpanded && folderDatasets.length > 0 && (
                      <div className="ml-5 space-y-0.5">
                        {folderDatasets.map((dataset) => (
                          <div
                            key={dataset.id}
                            onClick={() => setCurrentDataset(dataset)}
                            className={cn(
                              'group flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer transition-all',
                              currentDataset?.id === dataset.id
                                ? 'bg-black text-white'
                                : 'text-neutral-700 hover:bg-neutral-100'
                            )}
                          >
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium truncate">{dataset.name}</p>
                              <p className={cn("text-xs", currentDataset?.id === dataset.id ? "text-neutral-400" : "text-neutral-500")}>
                                {formatNumber(dataset.row_count)} rows
                              </p>
                            </div>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleMoveToFolder(dataset.id, null); }}
                              className={cn("p-1 opacity-0 group-hover:opacity-100 transition-all rounded", currentDataset?.id === dataset.id ? "hover:bg-white/20" : "hover:bg-neutral-200")}
                              title="Move to root"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Root datasets (no folder) */}
              {datasets.filter(d => !d.folder_id).length === 0 && folders.length === 0 ? (
                <div className="text-center py-8">
                  <Folder className="w-8 h-8 text-neutral-300 mx-auto mb-2" />
                  <p className="text-xs text-neutral-500">No datasets</p>
                </div>
              ) : (
                <div className="space-y-0.5 mt-1">
                  {datasets.filter(d => !d.folder_id).map((dataset) => (
                    <div
                      key={dataset.id}
                      onClick={() => setCurrentDataset(dataset)}
                      className={cn(
                        'group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all',
                        currentDataset?.id === dataset.id
                          ? 'bg-black text-white'
                          : 'text-neutral-700 hover:bg-neutral-100'
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{dataset.name}</p>
                        <p className={cn("text-xs", currentDataset?.id === dataset.id ? "text-neutral-400" : "text-neutral-500")}>
                          {formatNumber(dataset.row_count)} rows
                        </p>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                        {folders.length > 0 && (
                          <select
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => handleMoveToFolder(dataset.id, parseInt(e.target.value))}
                            className="text-xs bg-neutral-100 rounded px-1 py-0.5 border-0"
                            defaultValue=""
                          >
                            <option value="" disabled>Move to...</option>
                            {folders.map(f => (
                              <option key={f.id} value={f.id}>{f.name}</option>
                            ))}
                          </select>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDelete(dataset); }}
                          className={cn("p-1 rounded-lg", currentDataset?.id === dataset.id ? "hover:bg-white/20" : "hover:bg-neutral-200")}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center py-3 gap-2 h-full">
            <button
              onClick={() => setLeftSidebarOpen(true)}
              className="btn btn-ghost btn-icon"
              title="Expand sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setIsImportOpen(true)}
              className="btn btn-ghost btn-icon"
              title="Import data"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#fafafa]">
        {currentDataset ? (
          <>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 bg-white border-b border-neutral-200">
              <div className="flex items-center gap-4">
                {isEditing ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="input input-sm w-48"
                      autoFocus
                    />
                    <button onClick={handleRename} className="btn btn-icon btn-sm btn-primary">
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => setIsEditing(false)} className="btn btn-icon btn-sm btn-secondary">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div 
                    className="group flex items-center gap-2 cursor-pointer"
                    onClick={() => setIsEditing(true)}
                  >
                    <h2 className="text-base font-semibold text-neutral-900">{currentDataset.name}</h2>
                    <Edit2 className="w-3.5 h-3.5 text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <span className="text-xs text-neutral-500">
                    {formatNumber(totalRows)} rows · {currentDataset.columns.length} columns · ${totalCost.toFixed(4)}
                  </span>
                  {activeJobs.length > 0 && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                      {activeJobs.length} processing
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Selection controls */}
                {selectedRowIds.size > 0 && (
                  <>
                    <span className="text-xs font-medium text-neutral-700">{selectedRowIds.size} selected</span>
                    <button
                      onClick={clearSelection}
                      className="text-xs text-neutral-500 hover:text-neutral-900 transition-colors"
                    >
                      Clear
                    </button>
                    <button
                      onClick={handleDeleteSelectedRows}
                      className="btn btn-danger btn-sm"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                    <div className="w-px h-6 bg-neutral-200" />
                  </>
                )}
                <button
                  onClick={() => { 
                    setRightSidebarOpen(true); 
                    setStartEnrichInCreateMode(true);
                    setTimeout(() => setStartEnrichInCreateMode(false), 100);
                  }}
                  className="btn btn-primary btn-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Column</span>
                </button>
                <button
                  onClick={() => setIsExportOpen(true)}
                  className="btn btn-secondary btn-sm"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export</span>
                </button>
                <button
                  onClick={handleRefresh}
                  disabled={isLoading}
                  className="btn btn-ghost btn-icon btn-sm"
                >
                  <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
                </button>
              </div>
            </div>

            {/* Filter bar */}
            <div className="flex items-center justify-between px-5 py-2.5 bg-white border-b border-neutral-200">
              {/* Filter */}
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-neutral-400" />
                <select
                  value={filterColumn || ''}
                  onChange={(e) => setFilterColumn(e.target.value || null)}
                  className="input input-sm select w-32"
                >
                  <option value="">No filter</option>
                  {allColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                {filterColumn && (
                  <>
                    <select
                      value={filterOperator}
                      onChange={(e) => setFilterOperator(e.target.value as any)}
                      className="input input-sm select w-32"
                    >
                      <option value="contains">Contains</option>
                      <option value="not_contains">Doesn't contain</option>
                      <option value="equals">Equals</option>
                      <option value="not_equals">Not equals</option>
                      <option value="empty">Is empty</option>
                      <option value="not_empty">Is not empty</option>
                    </select>
                    {!['empty', 'not_empty'].includes(filterOperator) && (
                      <input
                        type="text"
                        value={filterValue}
                        onChange={(e) => setFilterValue(e.target.value)}
                        placeholder="Filter value..."
                        className="input input-sm w-40"
                      />
                    )}
                    <button
                      onClick={() => { setFilterColumn(null); setFilterValue(''); setFilterOperator('contains'); }}
                      className="btn btn-ghost btn-icon btn-sm"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-xs text-neutral-500">
                      {filteredRows.length} matches
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 flex overflow-hidden">
              {/* Table */}
              <div className="flex-1 flex flex-col overflow-hidden p-4">
                <div className="flex-1 overflow-hidden card">
                  <DataTable
                    data={filterColumn && (filterValue || ['empty', 'not_empty'].includes(filterOperator)) ? filteredRows : rows}
                    columns={currentDataset.columns}
                    onRenameColumn={handleRenameColumn}
                    onDeleteColumn={handleDeleteColumn}
                    onEditEnrichedColumn={handleEditEnrichedColumn}
                  />
                </div>

                {/* Load all button */}
                {!allRowsLoaded && totalRows > rows.length && (
                  <div className="flex items-center justify-center py-3">
                    <button
                      onClick={loadAllRows}
                      disabled={isLoading}
                      className="px-4 py-2 text-sm font-medium text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {isLoading ? 'Loading...' : `Load all ${formatNumber(totalRows)} rows`}
                    </button>
                  </div>
                )}
              </div>

              {/* Enrichment panel - Sticky */}
              {rightSidebarOpen && (
                <div className="w-96 border-l border-neutral-200 bg-white flex-shrink-0 sticky top-0 h-full overflow-hidden">
                  <EnrichmentPanel
                    datasetId={currentDataset.id}
                    columns={allColumns}
                    onJobStarted={handleRefresh}
                    onColumnCreated={handleRefresh}
                    startInCreateMode={startEnrichInCreateMode}
                    editColumnName={editColumnName}
                    onClose={() => setRightSidebarOpen(false)}
                  />
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Database className="w-16 h-16 text-neutral-200 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-neutral-700 mb-1">
                No dataset selected
              </h3>
              <p className="text-sm text-neutral-500 mb-6">
                Select a dataset or import a new one
              </p>
              <button
                onClick={() => setIsImportOpen(true)}
                className="btn btn-primary"
              >
                <Plus className="w-4 h-4" />
                Import Data
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} />
      
      {currentDataset && (
        <ExportModal 
          isOpen={isExportOpen} 
          onClose={() => setIsExportOpen(false)}
          dataset={currentDataset}
          selectedRowIds={selectedRowIds}
          onExportComplete={handleRefresh}
        />
      )}
      
      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        variant="danger"
        confirmText="Delete"
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
}
