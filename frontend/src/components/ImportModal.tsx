import { useState, useCallback } from 'react';
import { Upload, Link2, X, Loader2, FileSpreadsheet } from 'lucide-react';
import { cn } from '../lib/utils';
import { datasetsApi } from '../api';
import { useAppStore } from '../store/appStore';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type ImportMethod = 'csv' | 'google_sheets';

export function ImportModal({ isOpen, onClose }: ImportModalProps) {
  const [method, setMethod] = useState<ImportMethod>('csv');
  const [name, setName] = useState('');
  const [googleUrl, setGoogleUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const { addDataset, setCurrentDataset } = useAppStore();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      if (!name) {
        setName(selectedFile.name.replace('.csv', ''));
      }
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile);
      if (!name) {
        setName(droppedFile.name.replace('.csv', ''));
      }
      setMethod('csv');
      setError(null);
    } else if (droppedFile) {
      setError('Please upload a CSV file');
    }
  }, [name]);

  const handleImport = async () => {
    setError(null);
    setIsLoading(true);

    try {
      let dataset;
      if (method === 'csv' && file) {
        dataset = await datasetsApi.uploadCsv(file, name || undefined);
      } else if (method === 'google_sheets' && googleUrl) {
        dataset = await datasetsApi.importGoogleSheets(googleUrl, name || undefined);
      } else {
        throw new Error('Please provide the required input');
      }

      addDataset(dataset);
      setCurrentDataset(dataset);
      onClose();
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Import failed');
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setName('');
    setGoogleUrl('');
    setFile(null);
    setError(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative modal-content w-full max-w-md p-6 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-neutral-900">Import Data</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            <X className="w-4 h-4 text-neutral-500" />
          </button>
        </div>

        {/* Method selector */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMethod('csv')}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-medium transition-all',
              method === 'csv'
                ? 'bg-black text-white'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            )}
          >
            <Upload className="w-4 h-4" />
            <span>Upload CSV</span>
          </button>
          <button
            onClick={() => setMethod('google_sheets')}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-medium transition-all',
              method === 'google_sheets'
                ? 'bg-black text-white'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            )}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Google Sheets</span>
          </button>
        </div>

        {/* Form */}
        <div className="space-y-5">
          {/* Name */}
          <div>
            <label className="label">Dataset name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Lead List"
              className="input"
            />
          </div>

          {/* CSV Upload */}
          {method === 'csv' && (
            <div>
              <label className="label">CSV File</label>
              <div
                onDragOver={handleDragOver}
                onDragEnter={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  'border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer',
                  isDragging
                    ? 'border-black bg-neutral-100 scale-[1.02]'
                    : file
                      ? 'border-black bg-neutral-50'
                      : 'border-neutral-300 hover:border-neutral-400'
                )}
              >
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                  id="csv-upload"
                />
                <label htmlFor="csv-upload" className="cursor-pointer">
                  {isDragging ? (
                    <div className="flex flex-col items-center">
                      <Upload className="w-10 h-10 text-black mb-3" />
                      <span className="text-sm font-medium text-neutral-900">Drop file here</span>
                    </div>
                  ) : file ? (
                    <div className="flex flex-col items-center">
                      <FileSpreadsheet className="w-10 h-10 text-black mb-3" />
                      <span className="text-sm font-medium text-neutral-900">{file.name}</span>
                      <span className="text-xs text-neutral-500 mt-1">Click to change</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <Upload className="w-10 h-10 text-neutral-300 mb-3" />
                      <span className="text-sm text-neutral-600">Click or drag to upload</span>
                      <span className="text-xs text-neutral-400 mt-1">CSV files up to 50MB</span>
                    </div>
                  )}
                </label>
              </div>
            </div>
          )}

          {/* Google Sheets URL */}
          {method === 'google_sheets' && (
            <div>
              <label className="label">Google Sheets URL</label>
              <div className="relative">
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                <input
                  type="url"
                  value={googleUrl}
                  onChange={(e) => setGoogleUrl(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  className="input pl-10"
                />
              </div>
              <p className="mt-2 text-xs text-neutral-500">
                Make sure the sheet is publicly accessible (Anyone with the link can view)
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="btn btn-secondary flex-1"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              onClick={handleImport}
              disabled={isLoading || (method === 'csv' ? !file : !googleUrl)}
              className="btn btn-primary flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Importing...</span>
                </>
              ) : (
                <span>Import Data</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
