import { useState, useEffect } from 'react';
import { X, Download, FileSpreadsheet, Mail, Loader2, Check, Copy, Send, RefreshCw, Tag, Database } from 'lucide-react';
import { cn } from '../lib/utils';
import { exportApi, type ExportRequest } from '../api/export';
import { integrationsApi } from '../api/integrations';
import { datasetsApi } from '../api/datasets';
import type { Dataset } from '../types';
import { FieldMappingModal } from './FieldMappingModal';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  dataset: Dataset;
  selectedRowIds: Set<number>;
  onExportComplete?: () => void;
}

type ExportFormat = 'csv' | 'instantly' | 'smartlead' | 'google_sheets';
type InstantlyMode = 'csv' | 'direct';

interface Campaign {
  id: string;
  name: string;
  status?: string;
}

const formats = [
  { id: 'csv' as ExportFormat, name: 'CSV', desc: 'Standard format', icon: FileSpreadsheet, image: null },
  { id: 'instantly' as ExportFormat, name: 'Instantly', desc: 'Email outreach', icon: Mail, image: '/instantly.png' },
  { id: 'smartlead' as ExportFormat, name: 'Smartlead', desc: 'Cold outreach', icon: Mail, image: '/smartlead.png' },
  { id: 'google_sheets' as ExportFormat, name: 'Clipboard', desc: 'Copy to sheets', icon: Copy, image: null },
];

export function ExportModal({ isOpen, onClose, dataset, selectedRowIds, onExportComplete }: ExportModalProps) {
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [isExporting, setIsExporting] = useState(false);
  const [exportSelected, setExportSelected] = useState(false);
  
  const [emailColumn, setEmailColumn] = useState('');
  const [firstNameColumn, setFirstNameColumn] = useState('');
  const [lastNameColumn, setLastNameColumn] = useState('');
  const [companyColumn, setCompanyColumn] = useState('');
  const [linkedinUrlColumn, setLinkedinUrlColumn] = useState('');
  const [messageColumn, setMessageColumn] = useState('');
  
  // Mark as exported
  const [markAsExported, setMarkAsExported] = useState(false);
  
  // Instantly direct send
  const [instantlyMode, setInstantlyMode] = useState<InstantlyMode>('direct');
  const [instantlyConnected, setInstantlyConnected] = useState(false);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  
  // Smartlead
  const [smartleadConnected, setSmartleadConnected] = useState(false);
  const [smartleadCampaigns, setSmartleadCampaigns] = useState<Campaign[]>([]);
  const [smartleadCampaign, setSmartleadCampaign] = useState('');
  
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Master DB flow
  const [showMasterDbPrompt, setShowMasterDbPrompt] = useState(false);
  const [showMappingModal, setShowMappingModal] = useState(false);
  const [exportedRowIds, setExportedRowIds] = useState<number[] | undefined>(undefined);
  const [instantlyCampaignForMapping, setInstantlyCampaignForMapping] = useState<{id: string, name: string} | undefined>(undefined);

  // Load Instantly settings when modal opens or format changes to Instantly
  useEffect(() => {
    if (isOpen && format === 'instantly') {
      loadInstantlySettings();
    }
  }, [isOpen, format]);

  // Load Smartlead settings
  useEffect(() => {
    if (isOpen && format === 'smartlead') {
      loadSmartleadSettings();
    }
  }, [isOpen, format]);

  const loadInstantlySettings = async () => {
    setLoadingCampaigns(true);
    try {
      const details = await integrationsApi.getInstantly();
      setInstantlyConnected(details.connected);
      setCampaigns(details.campaigns || []);
      if (details.campaigns?.length > 0) {
        setSelectedCampaign(details.campaigns[0].id);
      }
    } catch (err) {
      console.error('Failed to load Instantly settings:', err);
      setInstantlyConnected(false);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const refreshCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const campaigns = await integrationsApi.getInstantlyCampaigns();
      setCampaigns(campaigns);
    } catch (err) {
      console.error('Failed to refresh campaigns:', err);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const loadSmartleadSettings = async () => {
    setLoadingCampaigns(true);
    try {
      const details = await integrationsApi.getSmartlead();
      setSmartleadConnected(details.connected);
      setSmartleadCampaigns(details.campaigns || []);
      if (details.campaigns?.length > 0) {
        setSmartleadCampaign(details.campaigns[0].id);
      }
    } catch (err) {
      console.error('Failed to load Smartlead settings:', err);
      setSmartleadConnected(false);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const allColumns = [...dataset.columns];

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    setSuccess(null);

    try {
      if (format === 'google_sheets') {
        const result = await exportApi.exportToGoogleSheets(
          dataset.id,
          '',
          undefined,
          true,
          exportSelected && selectedRowIds.size > 0 ? Array.from(selectedRowIds) : undefined
        );
        
        const tsvData = result.data.map((row: any[]) => row.join('\t')).join('\n');
        await navigator.clipboard.writeText(tsvData);
        setSuccess(`Copied ${result.row_count} rows to clipboard!`);
        // Store exported row IDs for Master DB
        setExportedRowIds(exportSelected && selectedRowIds.size > 0 ? Array.from(selectedRowIds) : undefined);
        setShowMasterDbPrompt(true);
      } else if (format === 'instantly' && instantlyMode === 'direct') {
        // Direct send to Instantly via API
        if (!selectedCampaign) {
          setError('Please select a campaign');
          setIsExporting(false);
          return;
        }

        const result = await integrationsApi.sendLeadsToInstantly({
          campaign_id: selectedCampaign,
          dataset_id: dataset.id,
          row_ids: exportSelected && selectedRowIds.size > 0 
            ? Array.from(selectedRowIds) : undefined,
          email_column: emailColumn,
          first_name_column: firstNameColumn || undefined,
          last_name_column: lastNameColumn || undefined,
          company_column: companyColumn || undefined,
        });

        if (result.success) {
          // Mark rows as exported if option is enabled
          if (markAsExported && result.leads_sent > 0) {
            const rowIdsToMark = exportSelected && selectedRowIds.size > 0 
              ? Array.from(selectedRowIds) 
              : undefined;
            
            if (rowIdsToMark && rowIdsToMark.length > 0) {
              try {
                await datasetsApi.markRowsExported(
                  dataset.id,
                  rowIdsToMark,
                  'exported_to',
                  'instantly'
                );
                onExportComplete?.();
              } catch (e) {
                console.error('Failed to mark rows as exported:', e);
              }
            }
          }
          
          setSuccess(`Successfully sent ${result.leads_sent} leads to Instantly!`);
          // Store exported row IDs for Master DB
          setExportedRowIds(exportSelected && selectedRowIds.size > 0 ? Array.from(selectedRowIds) : undefined);
          // Store campaign info for marking in All Prospects
          const campaignInfo = campaigns.find(c => c.id === selectedCampaign);
          if (campaignInfo) {
            setInstantlyCampaignForMapping({ id: campaignInfo.id, name: campaignInfo.name });
          }
          setShowMasterDbPrompt(true);
          if (result.errors?.length > 0) {
            setError(`Warnings: ${result.errors.join(', ')}`);
          }
        } else {
          setError(result.errors?.join(', ') || 'Failed to send leads');
        }
      } else if (format === 'smartlead') {
        // Direct send to Smartlead via API
        if (!smartleadCampaign) {
          setError('Please select a campaign');
          setIsExporting(false);
          return;
        }

        const result = await integrationsApi.sendLeadsToSmartlead({
          campaign_id: smartleadCampaign,
          dataset_id: dataset.id,
          row_ids: exportSelected && selectedRowIds.size > 0 
            ? Array.from(selectedRowIds) : undefined,
          email_column: emailColumn,
          first_name_column: firstNameColumn || undefined,
          last_name_column: lastNameColumn || undefined,
          company_column: companyColumn || undefined,
        });

        if (result.success) {
          // Mark rows as exported
          if (markAsExported && result.leads_sent > 0) {
            const rowIdsToMark = exportSelected && selectedRowIds.size > 0 
              ? Array.from(selectedRowIds) 
              : undefined;
            
            if (rowIdsToMark && rowIdsToMark.length > 0) {
              try {
                await datasetsApi.markRowsExported(
                  dataset.id,
                  rowIdsToMark,
                  'exported_to',
                  'smartlead'
                );
                onExportComplete?.();
              } catch (e) {
                console.error('Failed to mark rows as exported:', e);
              }
            }
          }
          
          setSuccess(`Successfully sent ${result.leads_sent} leads to Smartlead!`);
          setExportedRowIds(exportSelected && selectedRowIds.size > 0 ? Array.from(selectedRowIds) : undefined);
          setShowMasterDbPrompt(true);
          if (result.errors?.length > 0) {
            setError(`Warnings: ${result.errors.join(', ')}`);
          }
        } else {
          setError(result.errors?.join(', ') || 'Failed to send leads');
        }
      } else {
        // CSV download
        const request: ExportRequest = {
          format: format as 'csv' | 'instantly' | 'smartlead',
          include_enriched: true,
          selected_row_ids: exportSelected && selectedRowIds.size > 0 
            ? Array.from(selectedRowIds) : undefined,
        };

        if (format === 'instantly') {
          request.email_column = emailColumn;
          request.first_name_column = firstNameColumn || undefined;
          request.last_name_column = lastNameColumn || undefined;
          request.company_column = companyColumn || undefined;
        } else if (format === 'smartlead') {
          request.linkedin_url_column = linkedinUrlColumn || undefined;
          request.first_name_column = firstNameColumn || undefined;
          request.last_name_column = lastNameColumn || undefined;
          request.company_column = companyColumn || undefined;
          request.email_column = emailColumn || undefined;
          request.message_column = messageColumn || undefined;
        }

        const blob = await exportApi.downloadCsv(dataset.id, request);
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${dataset.name}_${format}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        setSuccess('File downloaded successfully!');
        // Store exported row IDs for Master DB
        setExportedRowIds(exportSelected && selectedRowIds.size > 0 ? Array.from(selectedRowIds) : undefined);
        setShowMasterDbPrompt(true);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  if (!isOpen) return null;

  const rowCount = exportSelected && selectedRowIds.size > 0 ? selectedRowIds.size : dataset.row_count;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      <div className="relative modal-content w-full max-w-lg p-6 animate-slide-up max-h-[85vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">Export Data</h2>
            <p className="text-sm text-neutral-500">{rowCount.toLocaleString()} rows from {dataset.name}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-neutral-100 transition-colors">
            <X className="w-4 h-4 text-neutral-500" />
          </button>
        </div>

        {/* Format */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {formats.map((f) => (
            <button
              key={f.id}
              onClick={() => setFormat(f.id)}
              className={cn(
                'flex items-center gap-3 p-4 rounded-xl border-2 text-left transition-all',
                format === f.id 
                  ? 'border-black bg-neutral-50' 
                  : 'border-neutral-200 hover:border-neutral-300'
              )}
            >
              <div className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center overflow-hidden',
                format === f.id && !f.image ? 'bg-black' : !f.image ? 'bg-neutral-100' : ''
              )}>
                {f.image ? (
                  <img src={f.image} alt={f.name} className="w-10 h-10 object-cover rounded-xl" />
                ) : (
                  <f.icon className={cn(
                    'w-5 h-5',
                    format === f.id ? 'text-white' : 'text-neutral-500'
                  )} />
                )}
              </div>
              <div>
                <div className={cn(
                  'text-sm font-medium',
                  format === f.id ? 'text-neutral-900' : 'text-neutral-700'
                )}>{f.name}</div>
                <div className="text-xs text-neutral-500">{f.desc}</div>
              </div>
            </button>
          ))}
        </div>

        {/* Options */}
        <div className="space-y-3 mb-6">
          {selectedRowIds.size > 0 && (
            <label className="flex items-center gap-3 cursor-pointer">
              <div className={cn(
                'w-5 h-5 rounded-lg border-2 flex items-center justify-center transition-all',
                exportSelected ? 'bg-black border-black' : 'border-neutral-300'
              )}>
                {exportSelected && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={exportSelected}
                onChange={(e) => setExportSelected(e.target.checked)}
                className="sr-only"
              />
              <span className="text-sm text-neutral-700">Export selected only ({selectedRowIds.size} rows)</span>
            </label>
          )}

          {(format === 'instantly' || format === 'smartlead') && (
            <label className="flex items-center gap-3 cursor-pointer">
              <div className={cn(
                'w-5 h-5 rounded-lg border-2 flex items-center justify-center transition-all',
                markAsExported ? 'bg-emerald-500 border-emerald-500' : 'border-neutral-300'
              )}>
                {markAsExported && <Tag className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={markAsExported}
                onChange={(e) => setMarkAsExported(e.target.checked)}
                className="sr-only"
              />
              <span className="text-sm text-neutral-700">Mark rows as exported (creates column)</span>
            </label>
          )}
        </div>

        {/* Instantly-specific options */}
        {format === 'instantly' && (
          <div className="bg-neutral-50 rounded-xl p-4 mb-6 space-y-4">
            {/* Mode selection */}
            <div>
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Export Method</h3>
              <div className="flex gap-3">
                <button
                  onClick={() => setInstantlyMode('direct')}
                  disabled={!instantlyConnected}
                  className={cn(
                    'flex-1 p-3 rounded-xl border-2 text-left transition-all',
                    instantlyMode === 'direct' && instantlyConnected
                      ? 'border-black bg-white' 
                      : 'border-neutral-200',
                    !instantlyConnected && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    <span className="text-sm font-medium">Send Directly</span>
                  </div>
                  <p className="text-xs text-neutral-500 mt-1">Push leads to Instantly via API</p>
                </button>
                <button
                  onClick={() => setInstantlyMode('csv')}
                  className={cn(
                    'flex-1 p-3 rounded-xl border-2 text-left transition-all',
                    instantlyMode === 'csv'
                      ? 'border-black bg-white' 
                      : 'border-neutral-200'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    <span className="text-sm font-medium">Download CSV</span>
                  </div>
                  <p className="text-xs text-neutral-500 mt-1">Import manually to Instantly</p>
                </button>
              </div>
              {!instantlyConnected && (
                <p className="text-xs text-amber-600 mt-2">
                  Connect Instantly in Settings to send directly
                </p>
              )}
            </div>

            {/* Campaign selection for direct mode */}
            {instantlyMode === 'direct' && instantlyConnected && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">Campaign *</label>
                  <button
                    onClick={refreshCampaigns}
                    disabled={loadingCampaigns}
                    className="btn btn-ghost btn-sm"
                  >
                    <RefreshCw className={cn('w-3 h-3', loadingCampaigns && 'animate-spin')} />
                  </button>
                </div>
                {loadingCampaigns ? (
                  <div className="flex items-center gap-2 text-sm text-neutral-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading campaigns...
                  </div>
                ) : campaigns.length === 0 ? (
                  <p className="text-sm text-neutral-500">No campaigns found in Instantly</p>
                ) : (
                  <select 
                    value={selectedCampaign} 
                    onChange={(e) => setSelectedCampaign(e.target.value)} 
                    className="input select"
                  >
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} {c.status ? `(${c.status})` : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Column Mapping */}
            <div>
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Column Mapping</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Email *</label>
                  <select value={emailColumn} onChange={(e) => setEmailColumn(e.target.value)} className="input select">
                    <option value="">Select column...</option>
                    {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">First Name</label>
                  <select value={firstNameColumn} onChange={(e) => setFirstNameColumn(e.target.value)} className="input select">
                    <option value="">Select column...</option>
                    {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Last Name</label>
                  <select value={lastNameColumn} onChange={(e) => setLastNameColumn(e.target.value)} className="input select">
                    <option value="">Select column...</option>
                    {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Company</label>
                  <select value={companyColumn} onChange={(e) => setCompanyColumn(e.target.value)} className="input select">
                    <option value="">Select column...</option>
                    {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Smartlead campaign & column mappings */}
        {format === 'smartlead' && (
          <div className="bg-neutral-50 rounded-xl p-4 mb-6 space-y-4">
            {smartleadConnected ? (
              <>
                <div>
                  <label className="label">Smartlead Campaign *</label>
                  <select 
                    value={smartleadCampaign} 
                    onChange={(e) => setSmartleadCampaign(e.target.value)} 
                    className="input select"
                  >
                    <option value="">Select campaign...</option>
                    {smartleadCampaigns.map((campaign) => (
                      <option key={campaign.id} value={campaign.id}>
                        {campaign.name} {campaign.status ? `(${campaign.status})` : ''}
                      </option>
                    ))}
                  </select>
                </div>

                <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide pt-2">Column Mapping</h3>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Email *</label>
                    <select value={emailColumn} onChange={(e) => setEmailColumn(e.target.value)} className="input select">
                      <option value="">Select column...</option>
                      {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">First Name</label>
                    <select value={firstNameColumn} onChange={(e) => setFirstNameColumn(e.target.value)} className="input select">
                      <option value="">Select column...</option>
                      {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">Last Name</label>
                    <select value={lastNameColumn} onChange={(e) => setLastNameColumn(e.target.value)} className="input select">
                      <option value="">Select column...</option>
                      {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">Company</label>
                    <select value={companyColumn} onChange={(e) => setCompanyColumn(e.target.value)} className="input select">
                      <option value="">Select column...</option>
                      {allColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                    </select>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                <p className="text-sm text-amber-800 mb-2">Smartlead not connected</p>
                <p className="text-xs text-amber-600">Connect Smartlead in Settings to send leads directly to campaigns.</p>
              </div>
            )}
          </div>
        )}

        {/* Messages */}
        {success && !showMasterDbPrompt && (
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-center gap-2 mb-4">
            <Check className="w-4 h-4" />
            <span>{success}</span>
          </div>
        )}
        
        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm mb-4">
            {error}
          </div>
        )}

        {/* Master DB Prompt */}
        {showMasterDbPrompt && (
          <div className="p-4 rounded-xl bg-violet-50 border border-violet-200 mb-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center flex-shrink-0">
                <Database className="w-5 h-5 text-violet-600" />
              </div>
              <div className="flex-1">
                <h4 className="font-medium text-neutral-900 mb-1">Add to All Prospects?</h4>
                <p className="text-sm text-neutral-600 mb-3">
                  Save these prospects to your centralized database for tracking and deduplication across all campaigns.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setShowMasterDbPrompt(false);
                      setShowMappingModal(true);
                    }}
                    className="btn btn-sm bg-violet-600 hover:bg-violet-700 text-white"
                  >
                    <Database className="w-3.5 h-3.5" />
                    Yes, add prospects
                  </button>
                  <button
                    onClick={() => {
                      setShowMasterDbPrompt(false);
                    }}
                    className="btn btn-sm btn-secondary"
                  >
                    No thanks
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        {!showMasterDbPrompt && (
          <div className="flex gap-3">
            <button onClick={onClose} className="btn btn-secondary flex-1" disabled={isExporting}>
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={
                isExporting || 
                (format === 'instantly' && !emailColumn) ||
                (format === 'instantly' && instantlyMode === 'direct' && !selectedCampaign) ||
                (format === 'smartlead' && (!emailColumn || !smartleadCampaign))
              }
              className="btn btn-primary flex-1"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>
                    {format === 'instantly' && instantlyMode === 'direct' ? 'Sending...' : 
                     format === 'smartlead' ? 'Sending...' : 'Exporting...'}
                  </span>
                </>
              ) : (
                <>
                  {format === 'instantly' && instantlyMode === 'direct' ? (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Send to Instantly</span>
                    </>
                  ) : format === 'smartlead' ? (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Send to Smartlead</span>
                    </>
                  ) : format === 'google_sheets' ? (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>Copy to Clipboard</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      <span>Download</span>
                    </>
                  )}
                </>
              )}
            </button>
          </div>
        )}

        {showMasterDbPrompt && (
          <div className="flex gap-3">
            <button onClick={onClose} className="btn btn-secondary flex-1">
              Close
            </button>
          </div>
        )}
      </div>

      {/* Field Mapping Modal */}
      <FieldMappingModal
        isOpen={showMappingModal}
        onClose={() => {
          setShowMappingModal(false);
          setInstantlyCampaignForMapping(undefined);
          onClose();
        }}
        dataset={dataset}
        rowIds={exportedRowIds}
        instantlyCampaign={instantlyCampaignForMapping}
      />
    </div>
  );
}
