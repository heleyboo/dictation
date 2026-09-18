import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { AppShell } from "@/components/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LessonCreatePage } from "@/features/admin/lesson-create-form";
import { AdminLessonsPage } from "@/features/admin/lesson-table";
import { SegmentReviewPage } from "@/features/admin/segment-review";
import { RequireAdmin, RequireAuth } from "@/features/auth/guards";
import { LoginPage } from "@/features/auth/login-page";
import { HomePage } from "@/routes/home";

const queryClient = new QueryClient();

const admin = (page: ReactElement) => (
  <RequireAuth>
    <RequireAdmin>{page}</RequireAdmin>
  </RequireAuth>
);

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/admin", element: admin(<AdminLessonsPage />) },
      { path: "/admin/lessons/new", element: admin(<LessonCreatePage />) },
      { path: "/admin/lessons/:lessonId", element: admin(<SegmentReviewPage />) },
    ],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
