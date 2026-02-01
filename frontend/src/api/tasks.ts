import { api } from './client';

export interface SubTask {
  text: string;
  completed: boolean;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  priority: string;
  status: string;
  subtasks: SubTask[];
}

export interface TasksResponse {
  tasks: Task[];
  total: number;
  completed: number;
  pending: number;
  total_subtasks: number;
  completed_subtasks: number;
}

export const tasksApi = {
  async getTasks(): Promise<TasksResponse> {
    const response = await api.get('/tasks');
    return response.data;
  },
};
