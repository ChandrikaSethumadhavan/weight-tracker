export interface Snapshot {
  entry_date: string;
  weight: number | null;
  mood: string | null;
  calories_in: number;
  calories_out: number;
  carbs_in: number;
  protein_in: number;
  fat_in: number;
  streak: number;
  deficit_goal: number;
  net: number;
  needs_more_burn: boolean;
  needs_less_food: boolean;
}

export interface WeightRecord {
  entry_date: string;
  weight: number;
  mood?: string | null;
}

export interface FoodRecord {
  id: number;
  entry_date: string;
  description: string;
  brand?: string | null;
  meal_type: string;
  calories: number;
  carbs: number;
  protein: number;
  fat: number;
  source: string;
}

export interface FoodPayload {
  entry_date: string;
  description: string;
  brand?: string | null;
  meal_type: string;
  calories?: number;
  carbs?: number;
  protein?: number;
  fat?: number;
  source?: string;
}

export interface WorkoutRecord {
  id: number;
  entry_date: string;
  category: string;
  description: string;
  calories_burned: number;
  duration_minutes: number | null;
}

export interface WorkoutPayload {
  entry_date: string;
  category: string;
  description: string;
  duration_minutes?: number;
  calories_burned?: number;
}

export interface SettingsResponse {
  target_calories: number;
  deficit_goal: number;
  reminder_time: string;
  reminder_enabled: boolean;
}

export interface CicoForecastPoint {
  entry_date: string;
  predicted_weight: number;
  daily_delta_kg: number;
  source: string;
}

export interface FastingHistoryEntry {
  id: number;
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

export interface FastingCalendarDay {
  entry_date: string;
  fasted: boolean;
  duration_minutes: number;
}

export interface FastingStatus {
  is_active: boolean;
  start_time: string | null;
  elapsed_minutes: number;
  remaining_minutes: number;
  exceeded_minutes: number;
  target_minutes: number;
  history: FastingHistoryEntry[];
  calendar_days: FastingCalendarDay[];
}
