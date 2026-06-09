import React, { useEffect, useState } from "react";
import {
  Typography, Card, Tag, Collapse, Row, Col, Spin, Empty, message, Descriptions, Space,
} from "antd";
import { ApiOutlined } from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

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

function PluginCard({ plugin }: { plugin: PluginItem }) {
  const hasSchema = plugin.schema?.properties && Object.keys(plugin.schema.properties).length > 0;
  const fieldCount = hasSchema ? Object.keys(plugin.schema.properties!).length : 0;

  return (
    <Card
      hoverable
      style={{ height: "100%" }}
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

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchPlugins();
        setPlugins(data);
      } catch {
        message.error("加载插件列表失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={3}>
          <ApiOutlined style={{ marginRight: 8 }} />
          插件管理
        </Title>
        <Text type="secondary">
          查看所有可用的步骤插件及其配置信息，这些插件可在工作流 YAML 中作为 step 使用。
        </Text>
      </div>

      {plugins.length === 0 ? (
        <Card>
          <Empty description="暂无已注册的插件" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {plugins.map((plugin) => (
            <Col key={plugin.name} xs={24} sm={12} lg={8}>
              <PluginCard plugin={plugin} />
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
