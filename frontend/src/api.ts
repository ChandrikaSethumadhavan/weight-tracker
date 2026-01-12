import type {
  CicoForecastPoint,
  FoodPayload,
  FoodRecord,
  FastingStatus,
  Snapshot,
  WeightRecord,
  WorkoutPayload,
  WorkoutRecord,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSnapshot(date?: string) {
    const query = date ? `?entry_date=${date}` : "";
    return request<Snapshot>(`/api/snapshot${query}`);
  },
  getWeights(limit = 30) {
    return request<WeightRecord[]>(`/api/weights?limit=${limit}`);
  },
  saveWeight(payload: { entry_date: string; weight: number; mood?: string | null }) {
    return request<WeightRecord>("/api/weights", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteWeight(entryDate: string) {
    return request<void>(`/api/weights/${entryDate}`, { method: "DELETE" });
  },
  getFoods(entryDate: string) {
    return request<FoodRecord[]>(`/api/foods?entry_date=${entryDate}`);
  },
  getRecentFoods(limit = 30) {
    return request<FoodRecord[]>(`/api/foods/recent?limit=${limit}`);
  },
  createFood(payload: FoodPayload) {
    return request<FoodRecord>("/api/foods", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteFood(id: number) {
    return request<void>(`/api/foods/${id}`, { method: "DELETE" });
  },
  getWorkouts(entryDate: string) {
    return request<WorkoutRecord[]>(`/api/workouts?entry_date=${entryDate}`);
  },
  createWorkout(payload: WorkoutPayload) {
    return request<WorkoutRecord>("/api/workouts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteWorkout(id: number) {
    return request<void>(`/api/workouts/${id}`, { method: "DELETE" });
  },
  getForecast(days = 7) {
    return request<CicoForecastPoint[]>(`/api/cico/forecast?days=${days}`);
  },
  getFastingStatus() {
    return request<FastingStatus>("/api/fasting");
  },
  startFasting(startTime?: string) {
    return request<FastingStatus>("/api/fasting/start", {
      method: "POST",
      body: JSON.stringify(startTime ? { start_time: startTime } : {}),
    });
  },
  stopFasting(endTime?: string) {
    return request<FastingStatus>("/api/fasting/stop", {
      method: "POST",
      body: JSON.stringify(endTime ? { end_time: endTime } : {}),
    });
  },
};
