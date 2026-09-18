import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { csrfHeaders, errorMessage, type Schemas } from "@/lib/api/client";
import { formatBytes } from "@/lib/format";
import { ADMIN_LESSONS_KEY, LEVELS, TOPICS } from "./lesson-options";

const MAX_AUDIO_BYTES = 30 * 1024 * 1024;
const MAX_TRANSCRIPT = 20_000;
const ACCEPT = ".mp3,.m4a,.wav,audio/mpeg,audio/mp4,audio/wav";

/** Upload form (AC-M2-01). Client checks give early feedback; the API validates the real bytes. */
export function LessonCreatePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [topic, setTopic] = useState("news");
  const [level, setLevel] = useState("beginner");
  const [audio, setAudio] = useState<File | null>(null);
  const [transcript, setTranscript] = useState("");
  const [license, setLicense] = useState("");
  const [touched, setTouched] = useState(false);

  const create = useMutation({
    mutationFn: async (form: FormData): Promise<Schemas["LessonDetail"]> => {
      // Multipart upload: plain fetch (openapi-fetch serialises JSON bodies).
      const res = await fetch("/api/v1/admin/lessons", {
        method: "POST",
        body: form,
        headers: csrfHeaders(),
        credentials: "same-origin",
      });
      const body = await res.json().catch(() => undefined);
      if (!res.ok) throw new Error(errorMessage(body, `Tải lên thất bại (HTTP ${res.status})`));
      return body as Schemas["LessonDetail"];
    },
    onSuccess: (lesson) => {
      qc.invalidateQueries({ queryKey: ADMIN_LESSONS_KEY });
      navigate(`/admin/lessons/${lesson.id}`);
    },
  });

  const audioError = audio && audio.size > MAX_AUDIO_BYTES ? "File vượt quá 30 MB" : null;
  const transcriptError = transcript.length > MAX_TRANSCRIPT ? "Transcript vượt quá 20 000 ký tự" : null;

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setTouched(true);
    if (!audio || audioError || transcriptError || !license.trim() || !transcript.trim()) return;
    const form = new FormData(e.currentTarget);
    form.set("topic", topic);
    form.set("level", level);
    form.set("audio", audio);
    create.mutate(form);
  };

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <Link to="/admin" className="text-sm text-ink-3 hover:underline">
        ← Bài học
      </Link>
      <h1 className="mt-2 mb-6 font-serif text-3xl text-ink">Thêm bài</h1>
      <form onSubmit={submit} className="grid gap-5" noValidate>
        <Field label="Tiêu đề" htmlFor="title">
          <Input id="title" name="title" required maxLength={200} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Chủ đề">
            <Select value={topic} onValueChange={setTopic}>
              <SelectTrigger aria-label="Chủ đề" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TOPICS.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Trình độ">
            <Select value={level} onValueChange={setLevel}>
              <SelectTrigger aria-label="Trình độ" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LEVELS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Tên nguồn" htmlFor="source_name">
            <Input id="source_name" name="source_name" required placeholder="VOA Learning English" />
          </Field>
          <Field label="URL nguồn" htmlFor="source_url">
            <Input id="source_url" name="source_url" type="url" placeholder="https://…" />
          </Field>
        </div>
        <Field
          label="Giấy phép (bắt buộc)"
          htmlFor="license"
          error={touched && !license.trim() ? "Phải ghi rõ giấy phép của nội dung" : null}
        >
          <Input
            id="license"
            name="license"
            required
            value={license}
            onChange={(e) => setLicense(e.target.value)}
            placeholder="Public domain — VOA"
            aria-invalid={touched && !license.trim()}
          />
        </Field>
        <Field
          label="Audio (mp3, m4a, wav · ≤ 30 MB · ≤ 15 phút)"
          htmlFor="audio"
          error={audioError ?? (touched && !audio ? "Chọn file audio" : null)}
        >
          <Input
            id="audio"
            type="file"
            accept={ACCEPT}
            required
            onChange={(e) => setAudio(e.target.files?.[0] ?? null)}
            aria-invalid={Boolean(audioError)}
          />
          {audio && (
            <p className="text-xs text-ink-3">
              {audio.name} · {formatBytes(audio.size)}
            </p>
          )}
        </Field>
        <Field
          label="Transcript (tiếng Anh, bắt buộc)"
          htmlFor="transcript"
          error={transcriptError ?? (touched && !transcript.trim() ? "Nhập transcript" : null)}
        >
          <Textarea
            id="transcript"
            name="transcript"
            required
            rows={10}
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            className="font-serif"
          />
          <p className="text-right font-mono text-xs text-ink-3">
            {transcript.length.toLocaleString("vi-VN")} / {MAX_TRANSCRIPT.toLocaleString("vi-VN")}
          </p>
        </Field>
        {create.isError && (
          <p role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
            {create.error.message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" asChild>
            <Link to="/admin">Huỷ</Link>
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Đang tải lên…" : "Tải lên & xử lý"}
          </Button>
        </div>
      </form>
    </main>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor?: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
