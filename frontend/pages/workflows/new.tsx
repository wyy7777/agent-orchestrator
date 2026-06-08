import React, { useState } from "react";
import { Typography, Form, Input, Button, Card, message, Space } from "antd";
import { useRouter } from "next/router";
import { workflowApi } from "@/lib/api";
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const { Title } = Typography;
const { TextArea } = Input;

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
  const router = useRouter();

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

      <Card style={{ marginBottom: 24 }}>
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

      <Card title="YAML 定义" style={{ marginBottom: 24 }}>
        <div style={{ border: "1px solid #d9d9d9", borderRadius: 8, overflow: "hidden" }}>
          <MonacoEditor
            height="400px"
            language="yaml"
            value={yaml}
            onChange={(v) => setYaml(v || "")}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
            }}
          />
        </div>
      </Card>

      <Space>
        <Button type="primary" loading={saving} onClick={handleSave}>
          创建工作流
        </Button>
        <Button onClick={() => router.push("/workflows")}>取消</Button>
      </Space>
    </div>
  );
}
