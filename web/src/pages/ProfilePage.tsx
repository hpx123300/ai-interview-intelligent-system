import { useEffect, useState } from "react";
import { RefreshCw, Save, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import type { JdAnalysis, Profile } from "../lib/types";
import { Badge, Button, Card, Field, Input, SectionTitle, Spinner, TextArea } from "../components/ui";

const EMPTY_PROJECT = { name: "", tech_stack: "", description: "", metrics: "", story: "" };

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getProfile().then(setProfile).catch(() => undefined);
  }, []);

  function patch(p: Partial<Profile>) {
    setProfile((prev) => (prev ? { ...prev, ...p } : prev));
  }

  async function save() {
    if (!profile) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.saveProfile(profile);
      setProfile(saved);
      setMessage("档案已保存：模拟面试将按你的目标岗位、JD 考察点与项目经历个性化出题。");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function analyzeJd() {
    if (!profile || !profile.jd_text.trim()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const analysis = await api.analyzeJd(profile.jd_text, profile);
      const saved = await api.saveProfile({ ...profile, jd_analysis: analysis });
      setProfile(saved);
      setMessage("JD 分析完成并已保存：面试将按岗位考察点出题。");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!profile) return <Spinner text="加载档案…" />;
  const jd = profile.jd_analysis || ({} as JdAnalysis);
  const projects = [...profile.projects, ...Array(Math.max(0, 3 - profile.projects.length)).fill(EMPTY_PROJECT)].slice(0, 3);

  return (
    <div className="max-w-3xl space-y-4">
      {error && (
        <div className="rounded-[10px] border border-bad/25 bg-[#fdf3f3] px-4 py-2.5 text-[12.5px] text-bad">{error}</div>
      )}
      {message && (
        <div className="rounded-[10px] border border-ok/25 bg-[#f0f9f2] px-4 py-2.5 text-[12.5px] text-ok">{message}</div>
      )}

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[15px] font-bold">个人档案</div>
            <p className="text-[12.5px] text-muted mt-1">
              填一次，模拟面试就会结合你的真实项目出深挖题，求职顾问也会给更贴合的规划建议。
            </p>
          </div>
          <Button variant="primary" onClick={save} disabled={busy}>
            <Save size={14} />
            保存档案
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
          <Field label="目标岗位">
            <Input
              value={profile.target_role}
              onChange={(e) => patch({ target_role: e.target.value })}
            />
          </Field>
          <Field label="目标方向">
            <Input
              value={profile.target_direction}
              onChange={(e) => patch({ target_direction: e.target.value })}
            />
          </Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
          <Field label="技能栈（逗号分隔）">
            <Input
              value={profile.skills.join("，")}
              onChange={(e) =>
                patch({ skills: e.target.value.split(/[，,]/).map((s) => s.trim()).filter(Boolean) })
              }
            />
          </Field>
          <Field label="薄弱点（逗号分隔）">
            <Input
              value={profile.weak_areas.join("，")}
              onChange={(e) =>
                patch({ weak_areas: e.target.value.split(/[，,]/).map((s) => s.trim()).filter(Boolean) })
              }
            />
          </Field>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[15px] font-bold">目标 JD 与简历</div>
            <p className="text-[12.5px] text-muted mt-1">
              粘贴岗位描述后点击分析，自动生成岗位画像与差距分析，模拟面试按 JD 考察点出题。
            </p>
          </div>
          <Button variant="secondary" onClick={analyzeJd} disabled={busy || !profile.jd_text.trim()}>
            <Sparkles size={14} />
            分析目标 JD
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          <Field label="目标岗位描述（JD）">
            <TextArea
              className="min-h-[110px]"
              value={profile.jd_text}
              onChange={(e) => patch({ jd_text: e.target.value })}
              placeholder="粘贴你想投的岗位 JD……"
            />
          </Field>
          <Field label="简历文本（可选）" hint="供自定义面试设计参考">
            <TextArea
              className="min-h-[90px]"
              value={profile.resume_text}
              onChange={(e) => patch({ resume_text: e.target.value })}
              placeholder="粘贴简历正文……"
            />
          </Field>
        </div>
        {jd.title && (
          <div className="mt-4 rounded-[11px] border border-line bg-[#fcfbf9] p-4">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone="accent">JD 画像</Badge>
              <span className="text-[13.5px] font-semibold">{jd.title}</span>
              {jd.company_name ? <span className="text-[11.5px] text-muted">{jd.company_name}</span> : null}
              {jd.seniority ? <span className="text-[11.5px] text-muted">{jd.seniority}</span> : null}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3 text-[12px] text-ink-soft">
              <div>
                <div className="text-faint mb-1">必须项</div>
                <div className="flex flex-wrap gap-1">
                  {(jd.must_have || []).map((s) => <Badge key={s}>{s}</Badge>)}
                </div>
              </div>
              <div>
                <div className="text-faint mb-1">加分项</div>
                <div className="flex flex-wrap gap-1">
                  {(jd.nice_to_have || []).map((s) => <Badge key={s}>{s}</Badge>)}
                </div>
              </div>
              <div>
                <div className="text-faint mb-1">技术栈</div>
                <div className="flex flex-wrap gap-1">
                  {(jd.tech_stack || []).map((s) => <Badge key={s}>{s}</Badge>)}
                </div>
              </div>
            </div>
            {jd.gap?.summary && (
              <div className="mt-3 text-[12.5px] text-ink-soft">
                <span className="text-faint">差距分析：</span>
                {jd.gap.summary}
                {jd.gap.probe_targets?.length ? (
                  <span className="block mt-1">
                    <span className="text-faint">应深挖验证：</span>
                    {jd.gap.probe_targets.join("、")}
                  </span>
                ) : null}
              </div>
            )}
          </div>
        )}
      </Card>

      <Card>
        <div className="text-[15px] font-bold">项目经历（最多 3 个）</div>
        <p className="text-[12.5px] text-muted mt-1">
          尽量写量化成果（F1、接口数、数据量），面试官最吃这一套。
        </p>
        {projects.map((p, i) => (
          <div key={i} className="mt-5">
            <div className="text-[12px] font-bold text-ink-soft mb-2">项目 {i + 1}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="项目名称">
                <Input
                  value={p.name}
                  onChange={(e) => patchProject(i, "name", e.target.value)}
                  placeholder="如：投满分 BERT 分类"
                />
              </Field>
              <Field label="技术栈">
                <Input
                  value={p.tech_stack}
                  onChange={(e) => patchProject(i, "tech_stack", e.target.value)}
                  placeholder="如：PyTorch / BERT / 蒸馏"
                />
              </Field>
            </div>
            <div className="mt-3">
              <Field label="一句话描述">
                <Input
                  value={p.description}
                  onChange={(e) => patchProject(i, "description", e.target.value)}
                  placeholder="项目做什么、你负责什么"
                />
              </Field>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              <Field label="量化成果">
                <Input
                  value={p.metrics}
                  onChange={(e) => patchProject(i, "metrics", e.target.value)}
                  placeholder="如：F1 0.92 / 18 万条数据"
                />
              </Field>
              <Field label="深挖点 / 故事">
                <Input
                  value={p.story}
                  onChange={(e) => patchProject(i, "story", e.target.value)}
                  placeholder="技术决策、踩坑或面试官会追问的点"
                />
              </Field>
            </div>
          </div>
        ))}
        <div className="flex justify-end mt-5">
          <Button variant="primary" onClick={save} disabled={busy}>
            <RefreshCw size={14} />
            保存档案
          </Button>
        </div>
      </Card>
    </div>
  );

  function patchProject(index: number, key: keyof typeof EMPTY_PROJECT, value: string) {
    if (!profile) return;
    const projects = profile.projects.slice();
    while (projects.length <= index) projects.push({ ...EMPTY_PROJECT });
    projects[index] = { ...projects[index], [key]: value };
    patch({ projects: projects.filter((p) => p.name.trim() || p.description.trim()) });
  }
}
