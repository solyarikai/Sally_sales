import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Dataset, DataRow, PromptTemplate, EnrichmentJob, OpenAISettings, User, Environment, EnvironmentWithStats, Company, CompanyWithStats } from '../types';

interface AppState {
  // User, Environment & Company (multi-tenant hierarchy)
  currentUser: User | null;
  environments: EnvironmentWithStats[];
  currentEnvironment: Environment | null;
  companies: CompanyWithStats[];
  currentCompany: Company | null;
  setCurrentUser: (user: User | null) => void;
  setEnvironments: (environments: EnvironmentWithStats[]) => void;
  setCurrentEnvironment: (environment: Environment | null) => void;
  addEnvironment: (environment: EnvironmentWithStats) => void;
  updateEnvironment: (environment: Environment) => void;
  removeEnvironment: (id: number) => void;
  setCompanies: (companies: CompanyWithStats[]) => void;
  setCurrentCompany: (company: Company | null) => void;
  addCompany: (company: CompanyWithStats) => void;
  updateCompany: (company: Company) => void;
  removeCompany: (id: number) => void;

  // Datasets
  datasets: Dataset[];
  currentDataset: Dataset | null;
  setDatasets: (datasets: Dataset[]) => void;
  setCurrentDataset: (dataset: Dataset | null) => void;
  addDataset: (dataset: Dataset) => void;
  updateDataset: (dataset: Dataset) => void;
  removeDataset: (id: number) => void;

  // Rows
  rows: DataRow[];
  selectedRowIds: Set<number>;
  setRows: (rows: DataRow[]) => void;
  updateRow: (id: number, data: Partial<DataRow>) => void;
  toggleRowSelection: (id: number) => void;
  selectAllRows: () => void;
  clearSelection: () => void;
  selectFirstN: (n: number) => void;

  // Templates
  templates: PromptTemplate[];
  setTemplates: (templates: PromptTemplate[]) => void;
  addTemplate: (template: PromptTemplate) => void;

  // Jobs
  activeJobs: EnrichmentJob[];
  setActiveJobs: (jobs: EnrichmentJob[]) => void;
  updateJob: (job: EnrichmentJob) => void;

  // Settings
  openaiSettings: OpenAISettings | null;
  setOpenAISettings: (settings: OpenAISettings) => void;

  // UI State
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
  
  // Reset company-scoped data when switching companies
  resetCompanyData: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // User, Environment & Company
      currentUser: null,
      environments: [],
      currentEnvironment: null,
      companies: [],
      currentCompany: null,
      setCurrentUser: (user) => set({ currentUser: user }),
      setEnvironments: (environments) => set({ environments }),
      setCurrentEnvironment: (environment) => set({ currentEnvironment: environment }),
      addEnvironment: (environment) => set((state) => ({
        environments: [environment, ...state.environments]
      })),
      updateEnvironment: (environment) => set((state) => ({
        environments: state.environments.map((e) => (e.id === environment.id ? { ...e, ...environment } : e)),
        currentEnvironment: state.currentEnvironment?.id === environment.id ? environment : state.currentEnvironment,
      })),
      removeEnvironment: (id) => set((state) => ({
        environments: state.environments.filter((e) => e.id !== id),
        currentEnvironment: state.currentEnvironment?.id === id ? null : state.currentEnvironment,
      })),
      setCompanies: (companies) => set({ companies }),
      setCurrentCompany: (company) => set({ currentCompany: company }),
      addCompany: (company) => set((state) => ({ 
        companies: [company, ...state.companies] 
      })),
      updateCompany: (company) => set((state) => ({
        companies: state.companies.map((c) => (c.id === company.id ? { ...c, ...company } : c)),
        currentCompany: state.currentCompany?.id === company.id ? company : state.currentCompany,
      })),
      removeCompany: (id) => set((state) => ({
        companies: state.companies.filter((c) => c.id !== id),
        currentCompany: state.currentCompany?.id === id ? null : state.currentCompany,
      })),

      // Datasets
      datasets: [],
      currentDataset: null,
      setDatasets: (datasets) => set({ datasets }),
      setCurrentDataset: (dataset) => set({ currentDataset: dataset, selectedRowIds: new Set() }),
      addDataset: (dataset) => set((state) => ({ datasets: [dataset, ...state.datasets] })),
      updateDataset: (dataset) => set((state) => ({
        datasets: state.datasets.map((d) => (d.id === dataset.id ? dataset : d)),
        currentDataset: state.currentDataset?.id === dataset.id ? dataset : state.currentDataset,
      })),
      removeDataset: (id) => set((state) => ({
        datasets: state.datasets.filter((d) => d.id !== id),
        currentDataset: state.currentDataset?.id === id ? null : state.currentDataset,
      })),

      // Rows
      rows: [],
      selectedRowIds: new Set(),
      setRows: (rows) => set({ rows }),
      updateRow: (id, data) => set((state) => ({
        rows: state.rows.map((r) => (r.id === id ? { ...r, ...data } : r)),
      })),
      toggleRowSelection: (id) => set((state) => {
        const newSelection = new Set(state.selectedRowIds);
        if (newSelection.has(id)) {
          newSelection.delete(id);
        } else {
          newSelection.add(id);
        }
        return { selectedRowIds: newSelection };
      }),
      selectAllRows: () => set((state) => ({
        selectedRowIds: new Set(state.rows.map((r) => r.id)),
      })),
      clearSelection: () => set({ selectedRowIds: new Set() }),
      selectFirstN: (n) => set((state) => ({
        selectedRowIds: new Set(state.rows.slice(0, n).map((r) => r.id)),
      })),

      // Templates
      templates: [],
      setTemplates: (templates) => set({ templates }),
      addTemplate: (template) => set((state) => ({ templates: [...state.templates, template] })),

      // Jobs
      activeJobs: [],
      setActiveJobs: (jobs) => set({ activeJobs: jobs }),
      updateJob: (job) => set((state) => ({
        activeJobs: state.activeJobs.map((j) => (j.id === job.id ? job : j)),
      })),

      // Settings
      openaiSettings: null,
      setOpenAISettings: (settings) => set({ openaiSettings: settings }),

      // UI State
      isLoading: false,
      setLoading: (loading) => set({ isLoading: loading }),
      
      // Reset company-scoped data
      resetCompanyData: () => set({
        datasets: [],
        currentDataset: null,
        rows: [],
        selectedRowIds: new Set(),
        activeJobs: [],
      }),
    }),
    {
      name: 'leadgen-storage',
      partialize: (state) => ({
        // Only persist these fields
        currentEnvironment: state.currentEnvironment,
        currentCompany: state.currentCompany,
      }),
    }
  )
);
