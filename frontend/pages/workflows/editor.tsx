import React, { useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";

const ReactFlow = dynamic(
  () => import("@xyflow/react").then((m) => m.ReactFlow),
  { ssr: false }
);
const Background = dynamic(
  () => import("@xyflow/react").then((m) => m.Background),
  { ssr: false }
);
const Controls = dynamic(
  () => import("@xyflow/react").then((m) => m.Controls),
  { ssr: false }
);
const MiniMap = dynamic(
  () => import("@xyflow/react").then((m) => m.MiniMap),
  { ssr: false }
);
import {
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Typography, Card, Button, Space, Modal, Form, Input, Select, message, Drawer, Tag, Descriptions,
} from "antd";
import {
  PlusOutlined, SaveOutlined, PlayCircleOutlined, DeleteOutlined, SettingOutlined,
} from "@ant-design/icons";

const { Title } = Typography;

type WorkflowEdge = Edge<{ animated?: boolean; style?: React.CSSProperties }>;

// 自定义节点样式
const nodeStyles: Record<string, { bg: string; border: string; icon: string }> = {
  analyze: { bg: "#e6f7ff", border: "#1890ff", icon: "🔍" },
  execute: { bg: "#f6ffed", border: "#52c41a", icon: "⚡" },
  review: { bg: "#fff7e6", border: "#faad14", icon: "📋" },
  approval: { bg: "#fff1f0", border: "#ff4d4f", icon: "✋" },
  merge: { bg: "#f9f0ff", border: "#722ed1", icon: "🔀" },
  subtask: { bg: "#e6fffb", border: "#13c2c2", icon: "📎" },
  loop: { bg: "#fff0f6", border: "#eb2f96", icon: "🔄" },
  plugin: { bg: "#f0f5ff", border: "#2f54eb", icon: "🔌" },
};

// 自定义节点组件
function WorkflowNode({ data }: { data: { label: string; type: string; config?: any } }) {
  const style = nodeStyles[data.type] || { bg: "#fafafa", border: "#d9d9d9", icon: "📦" };

  return (
    <div
      style={{
        padding: "12px 16px",
        borderRadius: 8,
        background: style.bg,
        border: `2px solid ${style.border}`,
        minWidth: 150,
        textAlign: "center",
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontSize: 20, marginBottom: 4 }}>{style.icon}</div>
      <div style={{ fontWeight: 600, fontSize: 14 }}>{data.label}</div>
      <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>{data.type}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  workflow: WorkflowNode,
};

const STEP_TYPES = [
  { value: "analyze", label: "分析 (Analyze)" },
  { value: "execute", label: "执行 (Execute)" },
  { value: "review", label: "审查 (Review)" },
  { value: "approval", label: "审批 (Approval)" },
  { value: "merge", label: "合并 (Merge)" },
  { value: "subtask", label: "子任务 (Subtask)" },
  { value: "loop", label: "循环 (Loop)" },
  { value: "plugin", label: "插件 (Plugin)" },
];

export default function WorkflowEditorPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [form] = Form.useForm();
  const [configForm] = Form.useForm();

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: "#1890ff" } }, eds));
    },
    [setEdges],
  );

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node);
    const config = (node.data.config as Record<string, any>) || {};
    configForm.setFieldsValue({
      name: node.data.label,
      type: node.data.type,
      ...config,
    });
    setConfigDrawerOpen(true);
  }, [configForm]);

  const handleAddNode = (values: { name: string; type: string }) => {
    const newNode: Node = {
      id: `node-${Date.now()}`,
      type: "workflow",
      position: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
      data: { label: values.name, type: values.type, config: {} },
    };
    setNodes((nds) => [...nds, newNode]);
    setAddModalOpen(false);
    form.resetFields();
  };

  const handleDeleteNode = () => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
    setConfigDrawerOpen(false);
    setSelectedNode(null);
  };

  const handleSaveConfig = (values: any) => {
    if (!selectedNode) return;
    const { name, type, ...config } = values;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, label: name, type, config } }
          : n,
      ),
    );
    setConfigDrawerOpen(false);
    message.success("配置已保存");
  };

  // 生成 YAML
  const generateYAML = useCallback(() => {
    if (nodes.length === 0) {
      message.warning("请先添加步骤");
      return;
    }

    // 根据边的连接顺序排列节点
    const adjacency: Record<string, string[]> = {};
    edges.forEach((e) => {
      if (!adjacency[e.source]) adjacency[e.source] = [];
      adjacency[e.source].push(e.target);
    });

    // 拓扑排序
    const visited = new Set<string>();
    const sorted: string[] = [];
    const visit = (id: string) => {
      if (visited.has(id)) return;
      visited.add(id);
      (adjacency[id] || []).forEach(visit);
      sorted.push(id);
    };
    nodes.forEach((n) => visit(n.id));
    sorted.reverse();

    const steps = sorted.map((id) => {
      const node = nodes.find((n) => n.id === id);
      if (!node) return null;
      const { label, type, config } = node.data;
      return { name: label, type, ...(config || {}) };
    }).filter(Boolean);

    const yaml = {
      name: "my_workflow",
      description: "可视化编辑器生成的工作流",
      steps,
    };

    // 简单 YAML 生成
    let yamlStr = `name: ${yaml.name}\ndescription: ${yaml.description}\n\nsteps:\n`;
    steps.forEach((step: any) => {
      yamlStr += `  - name: ${step.name}\n`;
      yamlStr += `    type: ${step.type}\n`;
      Object.entries(step).forEach(([key, value]) => {
        if (key !== "name" && key !== "type" && value) {
          yamlStr += `    ${key}: ${JSON.stringify(value)}\n`;
        }
      });
    });

    Modal.info({
      title: "生成的 YAML",
      width: 600,
      content: (
        <pre style={{
          background: "#f5f5f5",
          padding: 16,
          borderRadius: 8,
          maxHeight: 400,
          overflow: "auto",
          fontSize: 13,
        }}>
          {yamlStr}
        </pre>
      ),
    });
  }, [nodes, edges]);

  return (
    <div style={{ height: "calc(100vh - 180px)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>可视化工作流编辑器</Title>
        <Space>
          <Button icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>
            添加步骤
          </Button>
          <Button icon={<SaveOutlined />} onClick={generateYAML}>
            生成 YAML
          </Button>
        </Space>
      </div>

      <Card style={{ height: "100%", padding: 0 }} bodyStyle={{ padding: 0, height: "100%" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          style={{ background: "#fafafa" }}
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </Card>

      {/* 添加步骤 Modal */}
      <Modal
        title="添加步骤"
        open={addModalOpen}
        onCancel={() => setAddModalOpen(false)}
        footer={null}
      >
        <Form form={form} onFinish={handleAddNode} layout="vertical">
          <Form.Item name="name" label="步骤名称" rules={[{ required: true }]}>
            <Input placeholder="例如: 分析代码" />
          </Form.Item>
          <Form.Item name="type" label="步骤类型" rules={[{ required: true }]}>
            <Select options={STEP_TYPES} placeholder="选择类型" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>添加</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 配置 Drawer */}
      <Drawer
        title="步骤配置"
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
        width={400}
        extra={
          <Button danger icon={<DeleteOutlined />} onClick={handleDeleteNode}>
            删除步骤
          </Button>
        }
      >
        {selectedNode && (
          <Form form={configForm} onFinish={handleSaveConfig} layout="vertical">
            <Form.Item name="name" label="步骤名称" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="type" label="步骤类型">
              <Select options={STEP_TYPES} disabled />
            </Form.Item>
            <Form.Item name="timeout" label="超时（秒）">
              <Input type="number" placeholder="300" />
            </Form.Item>
            <Form.Item name="provider" label="AI 提供商">
              <Select
                placeholder="选择提供商"
                options={[
                  { value: "deepseek", label: "DeepSeek" },
                  { value: "openai", label: "OpenAI" },
                  { value: "claude", label: "Claude" },
                ]}
              />
            </Form.Item>
            <Form.Item name="prompt_template" label="提示词模板">
              <Input.TextArea rows={4} placeholder="自定义提示词..." />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block>保存配置</Button>
            </Form.Item>
          </Form>
        )}
      </Drawer>
    </div>
  );
}
