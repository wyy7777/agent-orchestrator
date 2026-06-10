import React, { useState, useEffect, useRef, useCallback } from "react";
import { Typography, Form, Input, Button, Card, message, Space, Tag, Tooltip, Select, Collapse, Divider, List } from "antd";
import { useRouter } from "next/router";
import { workflowApi } from "@/lib/api";
import {
  CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined,
  SnippetsOutlined, QuestionCircleOutlined, ThunderboltOutlined,
} from "@ant-design/icons";
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

/** 步骤类型代码片段 */
const STEP_SNIPPETS: Record<string, { label: string; snippet: string; desc: string }> = {
  analyze: {
    label: "🔍 Analyze",
    snippet: `  - name: \${1:analyze}
    type: analyze
    timeout: 120
    config:
      provider: deepseek
    prompt_template: |
      \${2:请分析以下代码问题}`,
    desc: "AI 分析输入，输出结构化结果",
  },
  execute: {
    label: "⚡ Execute",
    snippet: `  - name: \${1:execute}
    type: execute
    timeout: 300
    config:
      provider: deepseek
    prompt_template: |
      \${2:根据分析结果执行修复}`,
    desc: "根据分析结果执行操作",
  },
  review: {
    label: "👀 Review",
    snippet: `  - name: \${1:review}
    type: review
    timeout: 120
    config:
      provider: deepseek
    prompt_template: |
      \${2:审查代码改动质量}`,
    desc: "AI 审查执行结果",
  },
  approval: {
    label: "✋ Approval",
    snippet: `  - name: \${1:approval}
    type: approval
    timeout: 3600`,
    desc: "人工审批门控",
  },
  merge: {
    label: "🔀 Merge",
    snippet: `  - name: \${1:create_pr}
    type: merge
    timeout: 60`,
    desc: "合并结果（创建 PR）",
  },
  condition: {
    label: "🔀 Condition",
    snippet: `  - name: \${1:check}
    type: condition
    condition: "{results.\${2:step}.score} > 80"
    else:
      - name: \${3:alternative}
        type: execute
        config:
          provider: deepseek`,
    desc: "条件分支",
  },
  loop: {
    label: "🔄 Loop",
    snippet: `  - name: \${1:loop_step}
    type: loop
    config:
      items_key: "\${2:items}"
      max_iterations: 10
    steps:
      - name: \${3:process}
        type: execute
        config:
          provider: deepseek`,
    desc: "循环执行子步骤",
  },
  subtask: {
    label: "📋 Subtask",
    snippet: `  - name: \${1:subtask}
    type: subtask
    config:
      child_workflow_id: "\${2:workflow_id}"`,
    desc: "调用子工作流",
  },
};

const EXAMPLE_YAML = `name: GitHub Issue Auto Fix
description: 自动分析 GitHub Issue，生成修复方案

steps:
  - name: analyze
    type: analyze
    timeout: 120
    config:
      provider: deepseek

  - name: review_plan
    type: approval
    timeout: 3600

  - name: execute
    type: execute
    timeout: 300
    config:
      provider: deepseek

  - name: review_code
    type: review
    timeout: 120
    config:
      provider: deepseek

  - name: final_approval
    type: approval
    timeout: 3600

  - name: create_pr
    type: merge
    timeout: 60
`;

export default function NewWorkflowPage() {
  const [form] = Form.useForm();
  const [yaml, setYaml] = useState(EXAMPLE_YAML);
  const [saving, setSaving] = useState(false);
  const [validationStatus, setValidationStatus] = useState<"idle" | "validating" | "valid" | "invalid">("idle");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Array<{ name: string; description: string; yaml_definition: string }>>([]);
  const [showSnippets, setShowSnippets] = useState(true);
  const router = useRouter();
  const validateTimerRef = useRef<NodeJS.Timeout | null>(null);
  const editorRef = useRef<any>(null);

  // 加载模板
  useEffect(() => {
    workflowApi.templates().then(setTemplates).catch(() => {});
  }, []);

  // 实时 YAML 校验（防抖 500ms）
  const validateYaml = useCallback(async (content: string) => {
    if (!content.trim()) {
      setValidationStatus("idle");
      setValidationError(null);
      return;
    }
    setValidationStatus("validating");
    try {
      const result = await workflowApi.validate(content);
      if (result.valid) {
        setValidationStatus("valid");
        setValidationError(null);
      } else {
        setValidationStatus("invalid");
        setValidationError(result.error);
      }
    } catch {
      setValidationStatus("idle");
    }
  }, []);

  const handleYamlChange = useCallback((value: string) => {
    setYaml(value);
    if (validateTimerRef.current) clearTimeout(validateTimerRef.current);
    validateTimerRef.current = setTimeout(() => validateYaml(value), 500);
  }, [validateYaml]);

  useEffect(() => {
    return () => {
      if (validateTimerRef.current) clearTimeout(validateTimerRef.current);
    };
  }, []);

  // 插入代码片段到编辑器
  const insertSnippet = useCallback((snippet: string) => {
    if (editorRef.current) {
      const editor = editorRef.current;
      const selection = editor.getSelection();
      const id = { major: 1, minor: 1 };
      const op = { identifier: id, range: selection, text: snippet, forceMoveMarkers: true };
      editor.executeEdits("snippet", [op]);
      editor.focus();
    } else {
      // 如果编辑器未加载，追加到末尾
      setYaml((prev) => prev + "\n" + snippet);
    }
  }, []);

  // 从模板加载
  const loadTemplate = useCallback((template: { name: string; yaml_definition: string }) => {
    form.setFieldsValue({ name: template.name });
    setYaml(template.yaml_definition);
    message.success(`已加载模板: ${template.name}`);
  }, [form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await workflowApi.create({
        name: values.name,
        description: values.description,
        yaml_definition: yaml,
      });
      message.success("工作流创建成功");
      router.push("/workflows");
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] }).errorFields) return;
      message.error((err as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Title level={3}>新建工作流</Title>

      <Card style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="工作流名称"
            rules={[{ required: true, message: "请输入工作流名称" }]}
          >
            <Input placeholder="例如：GitHub Issue 自动修复" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="可选：描述此工作流的用途" />
          </Form.Item>
        </Form>
      </Card>

      {/* 快速模板选择 */}
      {templates.length > 0 && (
        <Card title={<Space><ThunderboltOutlined /> 快速开始</Space>} size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            {templates.slice(0, 6).map((tpl, i) => (
              <Button key={i} size="small" onClick={() => loadTemplate(tpl)}>
                {tpl.name}
              </Button>
            ))}
          </Space>
        </Card>
      )}

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        {/* 步骤类型参考面板 */}
        <Card
          title={<Space><SnippetsOutlined /> 步骤类型</Space>}
          size="small"
          style={{ width: showSnippets ? 280 : 0, overflow: "hidden", transition: "width 0.3s" }}
          extra={
            <Button type="link" size="small" onClick={() => setShowSnippets(!showSnippets)}>
              {showSnippets ? "收起" : "展开"}
            </Button>
          }
        >
          {Object.entries(STEP_SNIPPETS).map(([type, { label, desc, snippet }]) => (
            <div
              key={type}
              style={{
                padding: "8px 12px",
                marginBottom: 4,
                borderRadius: 4,
                cursor: "pointer",
                background: "#fafafa",
                border: "1px solid #f0f0f0",
              }}
              onClick={() => insertSnippet(snippet)}
            >
              <div style={{ fontWeight: 500 }}>{label}</div>
              <div style={{ fontSize: 12, color: "#666" }}>{desc}</div>
            </div>
          ))}
        </Card>

        {/* YAML 编辑器 */}
        <Card
          title={
            <Space>
              <span>YAML 定义</span>
              {validationStatus === "validating" && <LoadingOutlined style={{ color: "#1677ff" }} />}
              {validationStatus === "valid" && (
                <Tooltip title="格式正确">
                  <CheckCircleOutlined style={{ color: "#52c41a" }} />
                </Tooltip>
              )}
              {validationStatus === "invalid" && (
                <Tooltip title={validationError}>
                  <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
                </Tooltip>
              )}
            </Space>
          }
          style={{ flex: 1 }}
        >
          {validationStatus === "invalid" && validationError && (
            <div style={{ marginBottom: 8, padding: "8px 12px", background: "#fff2f0", borderRadius: 4, color: "#ff4d4f" }}>
              ❌ {validationError}
            </div>
          )}
          <div style={{ border: `1px solid ${validationStatus === "invalid" ? "#ff4d4f" : "#d9d9d9"}`, borderRadius: 8, overflow: "hidden" }}>
            <MonacoEditor
              height="500px"
              language="yaml"
              value={yaml}
              onChange={(v) => handleYamlChange(v || "")}
              onMount={(editor) => { editorRef.current = editor; }}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                suggest: {
                  showSnippets: true,
                },
              }}
            />
          </div>
        </Card>
      </div>

      <Space>
        <Button
          type="primary"
          loading={saving}
          disabled={validationStatus === "invalid"}
          onClick={handleSave}
        >
          创建工作流
        </Button>
        <Button onClick={() => router.push("/workflows")}>取消</Button>
      </Space>
    </div>
  );
}
