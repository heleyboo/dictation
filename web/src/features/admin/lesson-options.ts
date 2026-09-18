/** Lesson topic/level choices shown in admin screens (labels in Vietnamese). */

export const TOPICS = [
  { value: "talk", label: "Thuyết trình" },
  { value: "news", label: "Bản tin" },
  { value: "interview", label: "Phỏng vấn" },
  { value: "conversation", label: "Hội thoại" },
] as const;

export const LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
] as const;

export const ADMIN_LESSONS_KEY = ["admin", "lessons"] as const;
