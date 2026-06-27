import React, { useEffect, useState } from "react";
import {
  Typography, Card, Tag, Collapse, Row, Col, Spin, Empty, message, Descriptions, Space,
  Button, Modal, Form, Input, Alert, Popconfirm,
} from "antd";
import { ApiOutlined, PlayCircleOutlined, ThunderboltOutlined, PlusOutlined, DeleteOutlined, DownloadOutlined } from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ==================== 类型定义 ====================

interface PluginField {
  type?: string;
  description?: string;
  default?: unknown;
  enum?: string[];
  properties?: Record<string, PluginField>;
}

interface PluginSchema {
  type?: string;
  required?: string[];
  properties?: Record<string, PluginField>;
}

interface PluginItem {
  name: string;
  description: string;
  schema: PluginSchema;
}

// ==================== API ====================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchPlugins(): Promise<PluginItem[]> {
  const res = await fetch(`${API_BASE}/api/plugins`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `请求失败: ${res.status}`);
  }
  return res.json();
}

async function installPlugin(source: string): Promise<{ status: string; name: string }> {
  const res = await fetch(`${API_BASE}/api/plugin-marketplace/install`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: source }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `安装失败: ${res.status}`);
  }
  return res.json();
}

async function uninstallPlugin(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/plugin-marketplace/uninstall/${name}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `卸载失败: ${res.status}`);
  }
}

// ==================== Schema 字段渲染 ====================

function SchemaFieldTable({ properties, required }: { properties: Record<string, PluginField>; required?: string[] }) {
  if (!properties || Object.keys(properties).length === 0) {
    return <Text type="secondary">无配置字段</Text>;
  }

  return (
    <Descriptions
      bordered
      size="small"
      column={1}
      style={{ marginTop: 8 }}
    >
      {Object.entries(properties).map(([key, field]) => (
        <Descriptions.Item
          key={key}
          label={
            <span>
              <Text code>{key}</Text>
              {required?.includes(key) && (
                <Tag color="red" style={{ marginLeft: 4 }}>必填</Tag>
              )}
            </span>
          }
        >
          <Space direction="vertical" size={2}>
            {field.type && <Tag color="blue">{field.type}</Tag>}
            {field.description && <Text type="secondary">{field.description}</Text>}
            {field.default !== undefined && (
              <Text>默认值: <Text code>{JSON.stringify(field.default)}</Text></Text>
            )}
            {field.enum && (
              <span>
                可选值: {field.enum.map((v) => <Tag key={v} style={{ marginLeft: 2 }}>{v}</Tag>)}
              </span>
            )}
          </Space>
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

// ==================== 插件卡片 ====================

interface PluginCardProps {
  plugin: PluginItem;
  onTest: (plugin: PluginItem) => void;
  onUninstall?: (name: string) => void;
}

function PluginCard({ plugin, onTest, onUninstall }: PluginCardProps) {
  const hasSchema = plugin.schema?.properties && Object.keys(plugin.schema.properties).length > 0;
  const fieldCount = hasSchema ? Object.keys(plugin.schema.properties!).length : 0;
  const isExternal = (plugin as any).source === "external";

  return (
    <Card
      hoverable
      style={{ height: "100%" }}
      actions={[
        <Button
          key="test"
          type="link"
          icon={<PlayCircleOutlined />}
          onClick={() => onTest(plugin)}
        >
          测试
        </Button>,
        ...(isExternal && onUninstall ? [
          <Popconfirm
            key="uninstall"
            title={`确认卸载插件 ${plugin.name}？`}
            onConfirm={() => onUninstall(plugin.name)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              卸载
            </Button>
          </Popconfirm>,
        ] : []),
      ]}
    >
      <Card.Meta
        title={
          <Space>
            <ApiOutlined />
            <Text strong>{plugin.name}</Text>
          </Space>
        }
        description={
          <Paragraph
            type="secondary"
            ellipsis={{ rows: 2 }}
            style={{ marginBottom: 0 }}
          >
            {plugin.description || "暂无描述"}
          </Paragraph>
        }
      />

      <div style={{ marginTop: 16 }}>
        <Space>
          <Tag color={hasSchema ? "blue" : "default"}>
            {fieldCount} 个配置字段
          </Tag>
          {plugin.schema?.required && plugin.schema.required.length > 0 && (
            <Tag color="orange">
              {plugin.schema.required.length} 个必填项
            </Tag>
          )}
        </Space>
      </div>

      {hasSchema && (
        <Collapse
          ghost
          style={{ marginTop: 16 }}
          items={[{
            key: "schema",
            label: "查看配置 Schema",
            children: (
              <SchemaFieldTable
                properties={plugin.schema.properties!}
                required={plugin.schema.required}
              />
            ),
          }]}
        />
      )}
    </Card>
  );
}

// ==================== 主页面 ====================

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [installModalOpen, setInstallModalOpen] = useState(false);
  const [selectedPlugin, setSelectedPlugin] = useState<PluginItem | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; result?: unknown; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [form] = Form.useForm();
  const [installForm] = Form.useForm();

  const loadPlugins = async () => {
    try {
      const data = await fetchPlugins();
      setPlugins(data);
    } catch {
      message.error("加载插件列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, []);

  const handleTest = (plugin: PluginItem) => {
    setSelectedPlugin(plugin);
    setTestModalOpen(true);
    setTestResult(null);
    form.resetFields();
  };

  const handleInstall = async (values: { source: string }) => {
    setInstalling(true);
    try {
      const result = await installPlugin(values.source);
      message.success(`插件 ${result.name} 安装成功`);
      setInstallModalOpen(false);
      installForm.resetFields();
      loadPlugins();
    } catch (err) {
      message.error((err as Error).message || "安装失败");
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstall = async (name: string) => {
    try {
      await uninstallPlugin(name);
      message.success(`插件 ${name} 已卸载`);
      loadPlugins();
    } catch (err) {
      message.error((err as Error).message || "卸载失败");
    }
  };

  const handleRunTest = async (values: Record<string, unknown>) => {
    if (!selectedPlugin) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/plugins/${selectedPlugin.name}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: values }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err) {
      setTestResult({ success: false, error: (err as Error).message });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <Title level={3}>
            <ApiOutlined style={{ marginRight: 8 }} />
            插件管理
          </Title>
          <Text type="secondary">
            查看所有可用的步骤插件及其配置信息，这些插件可在工作流 YAML 中作为 step 使用。
          </Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setInstallModalOpen(true)}
        >
          安装插件
        </Button>
      </div>

      {plugins.length === 0 ? (
        <Card>
          <Empty description="暂无已注册的插件" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {plugins.map((plugin) => (
            <Col key={plugin.name} xs={24} sm={12} lg={8}>
              <PluginCard plugin={plugin} onTest={handleTest} onUninstall={handleUninstall} />
            </Col>
          ))}
        </Row>
      )}

      {/* 安装插件 Modal */}
      <Modal
        title="安装插件"
        open={installModalOpen}
        onCancel={() => setInstallModalOpen(false)}
        footer={null}
        width={500}
      >
        <Alert
          type="info"
          message="支持本地 .py 文件路径或 HTTP(S) URL"
          style={{ marginBottom: 16 }}
        />
        <Form form={installForm} onFinish={handleInstall} layout="vertical">
          <Form.Item
            name="source"
            label="插件来源"
            rules={[{ required: true, message: "请输入插件路径或 URL" }]}
          >
            <Input placeholder="/path/to/plugin.py 或 https://example.com/plugin.py" />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={installing}
              icon={<DownloadOutlined />}
              block
            >
              安装
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 插件测试 Modal */}
      <Modal
        title={`测试插件: ${selectedPlugin?.name}`}
        open={testModalOpen}
        onCancel={() => setTestModalOpen(false)}
        footer={null}
        width={600}
      >
        {selectedPlugin && (
          <>
            <Paragraph type="secondary">{selectedPlugin.description}</Paragraph>

            {selectedPlugin.schema?.properties && Object.keys(selectedPlugin.schema.properties).length > 0 ? (
              <Form form={form} onFinish={handleRunTest} layout="vertical">
                {Object.entries(selectedPlugin.schema.properties).map(([key, field]) => (
                  <Form.Item
                    key={key}
                    name={key}
                    label={
                      <Space>
                        <Text code>{key}</Text>
                        {field.type && <Tag color="blue">{field.type}</Tag>}
                        {selectedPlugin.schema?.required?.includes(key) && (
                          <Tag color="red">必填</Tag>
                        )}
                      </Space>
                    }
                    rules={
                      selectedPlugin.schema?.required?.includes(key)
                        ? [{ required: true, message: `请输入 ${key}` }]
                        : undefined
                    }
                    tooltip={field.description}
                  >
                    <Input placeholder={field.description || `输入 ${key}`} />
                  </Form.Item>
                ))}
                <Form.Item>
                  <Button type="primary" htmlType="submit" loading={testing} icon={<ThunderboltOutlined />} block>
                    运行测试
                  </Button>
                </Form.Item>
              </Form>
            ) : (
              <Button
                type="primary"
                loading={testing}
                onClick={() => handleRunTest({})}
                icon={<ThunderboltOutlined />}
                block
              >
                运行测试（无配置）
              </Button>
            )}

            {testResult && (
              <Alert
                type={testResult.success ? "success" : "error"}
                message={testResult.success ? "测试成功" : "测试失败"}
                description={
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                    {JSON.stringify(testResult.success ? testResult.result : testResult.error, null, 2)}
                  </pre>
                }
                style={{ marginTop: 16 }}
              />
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
