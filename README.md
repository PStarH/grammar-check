# Grammar Check API（前端接入文档）

> 面向前端工程师：如何在 Web / Node / SSR 中稳定接入语法检查服务。

## 1. 服务定位

这个服务接收 **HTML 字符串**，自动提取可见文本并返回语法问题列表。

- Endpoint: `POST /v1/grammar/check`
- Health: `GET /health`
- Content-Type: `application/json`

---

## 2. 前端最常用接入方式

### 2.1 健康检查

```bash
curl http://localhost:8000/health
```

示例响应：

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 2.2 语法检查（最小请求）

```bash
curl -X POST http://localhost:8000/v1/grammar/check \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<p>I has a apple.</p>",
    "language": "en-US"
  }'
```

---

## 3. 请求参数（前端视角）

```ts
type GrammarCheckRequest = {
  requestId?: string;
  contentType?: "text/html"; // 默认 text/html
  language?: string;           // 默认 en-US
  html: string;                // 必填，HTML 字符串
  options?: {
    skipTags?: string[];       // 默认 ["script","style","code","pre"]
    mode?: "best_quality" | "hybrid" | "fast";
    useAI?: boolean;           // 默认 true
    returnCorrectedHtml?: boolean; // 当前一般返回 null
    maxSuggestions?: number;   // 1~100，默认 5
  };
};
```

### mode 选择建议

- `best_quality`: 质量优先（LLM）
- `hybrid`: LLM 优先，失败回退非 AI
- `fast`: 非 AI 路径（LanguageTool 优先，必要时 basic_rules）

---

## 4. 响应结构（前端可直接消费）

```ts
type GrammarIssue = {
  type: "grammar" | "spelling" | "style";
  severity: "error" | "warning" | "info";
  message: string;
  shortMessage: string;
  plainRange: { start: number; end: number }; // 对应 plainText 的偏移
  context: string;
  suggestions: string[];
  replacement: string | null;
  confidence: number; // 0~1
};

type GrammarCheckResponse = {
  requestId: string | null;
  detectedLanguage: string;
  plainText: string;
  issues: GrammarIssue[];
  stats: {
    latencyMs: number;
    engine: "llm" | "hybrid" | "languagetool" | "basic_rules" | "fallback";
  };
  correctedHtml: string | null;
};
```

---

## 5. 浏览器端调用示例（fetch）

```ts
export async function checkGrammar(html: string) {
  const res = await fetch("/v1/grammar/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      requestId: crypto.randomUUID(),
      language: "en-US",
      html,
      options: {
        mode: "hybrid",
        useAI: true,
        maxSuggestions: 5,
      },
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail || `Grammar API failed: ${res.status}`);
  }

  return (await res.json()) as GrammarCheckResponse;
}
```

---

## 6. UI 渲染建议

1. 使用 `plainText + plainRange` 在纯文本层做高亮。
2. 仅对 `severity === "error"` 默认高亮，`warning/info` 折叠显示。
3. 若 `suggestions.length > 0`，给一键替换按钮。
4. 展示 `stats.engine` 和 `stats.latencyMs`，便于排查环境问题。

---

## 7. 错误码与前端处理策略

- `200`: 成功（可能 issues 为空）
- `422`: 请求参数不合法（比如 `maxSuggestions` 超出 1~100）
- `503`: 当前模式所需引擎不可用（例如请求 AI 但没配置 LLM）
- `500`: 服务内部错误

建议：
- 422：在表单层阻止并提示用户修正参数。
- 503：提示“服务降级”，允许用户切换 `useAI=false` 或 `mode=fast`。
- 500：可重试 + 上报日志（带 `requestId`）。

---

## 8. 生产环境建议（给前端联调）

- 每次请求带 `requestId`（前端生成 UUID）。
- 做 8~15s 请求超时控制。
- 对同一段文本做防抖（300~500ms）。
- 大文本分段提交，避免一次发送过长 HTML。
- 记录 `requestId + engine + latencyMs` 到前端埋点。

---

## 9. 本地启动（供前端联调）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

可用后访问：
- `http://localhost:8000/health`
- `http://localhost:8000/docs`（OpenAPI）

