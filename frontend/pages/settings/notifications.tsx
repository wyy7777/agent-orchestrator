import React, { useEffect, useState } from "react";
import {
  Typography,
  Card,
  Form,
  Input,
  Switch,
  Button,
  Table,
  Tag,
  Space,
  message,
  Spin,
  Divider,
} from "antd";
import {
  SaveOutlined,
  SendOutlined,
  ReloadOutlined,
  BellOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import { notificationApi } from "@/lib/api";
import type { NotificationConfig, NotificationHistoryItem } from "@/lib/api";

const { Title, Text } = Typography;

const CHANNEL_LABELS: Record<string, string> = {
  slack: "Slack",
  dingtalk: "钉钉",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  task_completed: "任务完成",
  task_failed: "任务失败",
  approval_needed: "需要审批",
};

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  success: { color: "green", label: "成功" },
  failed: { color: "red", label: "失败" },
  pending: { color: "orange", label: "等待中" },
};

export default function NotificationsPage() {
  const [form] = Form.useForm<NotificationConfig>();
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingSlack, setTestingSlack] = useState(false);
  const [testingDingtalk, setTestingDingtalk] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [config, historyRes] = await Promise.all([
        notificationApi.getConfig(),
        notificationApi.history(50),
      ]);
      form.setFieldsValue(config);
      setHistory(historyRes.items);
    } catch {
      message.error("加载通知配置失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSave = async (values: NotificationConfig) => {
    setSaving(true);
    try {
      await notificationApi.updateConfig(values);
      message.success("配置已保存");
    } catch {
      message.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleTestSlack = async () => {
    setTestingSlack(true);
    try {
      const res = await notificationApi.testSlack();
      if (res.success) {
        message.success(res.message || "Slack 测试发送成功");
      } else {
        message.warning(res.message || "Slack 测试发送失败");
      }
    } catch {
      message.error("Slack 测试请求失败");
    } finally {
      setTestingSlack(false);
    }
  };

  const handleTestDingtalk = async () => {
    setTestingDingtalk(true);
    try {
      const res = await notificationApi.testDingtalk();
      if (res.success) {
        message.success(res.message || "钉钉测试发送成功");
      } else {
        message.warning(res.message || "钉钉测试发送失败");
      }
    } catch {
      message.error("钉钉测试请求失败");
    } finally {
      setTestingDingtalk(false);
    }
  };

  return (
    <div>
      <Title level={3}>
        <BellOutlined style={{ marginRight: 8 }} />
        通知设置
      </Title>

      <Spin spinning={loading}>
        {/* 通知渠道配置 */}
        <Card title="通知渠道" style={{ marginBottom: 24 }}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            initialValues={{
              slack_webhook_url: "",
              dingtalk_webhook_url: "",
              notify_on_task_complete: true,
              notify_on_task_fail: true,
              notify_on_approval_needed: true,
            }}
          >
            {/* Slack 配置 */}
            <Form.Item label="Slack Webhook URL" name="slack_webhook_url">
              <Input
                placeholder="https://hooks.slack.com/services/..."
                allowClear
              />
            </Form.Item>
            <Form.Item>
              <Button
                icon={<SendOutlined />}
                loading={testingSlack}
                onClick={handleTestSlack}
              >
                测试 Slack
              </Button>
            </Form.Item>

            <Divider />

            {/* 钉钉配置 */}
            <Form.Item label="钉钉 Webhook URL" name="dingtalk_webhook_url">
              <Input
                placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
                allowClear
              />
            </Form.Item>
            <Form.Item>
              <Button
                icon={<SendOutlined />}
                loading={testingDingtalk}
                onClick={handleTestDingtalk}
              >
                测试钉钉
              </Button>
            </Form.Item>

            <Divider />

            {/* 通知规则 */}
            <Title level={5}>通知规则</Title>

            <Form.Item
              label="任务完成时通知"
              name="notify_on_task_complete"
              valuePropName="checked"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>

            <Form.Item
              label="任务失败时通知"
              name="notify_on_task_fail"
              valuePropName="checked"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>

            <Form.Item
              label="需要审批时通知"
              name="notify_on_approval_needed"
              valuePropName="checked"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                htmlType="submit"
                loading={saving}
              >
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </Card>

        {/* 通知历史 */}
        <Card
          title="通知历史（最近 50 条）"
          extra={
            <Button
              icon={<ReloadOutlined />}
              onClick={loadData}
            >
              刷新
            </Button>
          }
        >
          <Table
            dataSource={history}
            rowKey="id"
            pagination={false}
            size="small"
            locale={{ emptyText: "暂无通知记录" }}
            columns={[
              {
                title: "时间",
                dataIndex: "created_at",
                width: 180,
                render: (v: string) => new Date(v).toLocaleString("zh-CN"),
              },
              {
                title: "渠道",
                dataIndex: "channel",
                width: 100,
                render: (v: string) => CHANNEL_LABELS[v] || v,
              },
              {
                title: "事件",
                dataIndex: "event_type",
                width: 120,
                render: (v: string) => EVENT_TYPE_LABELS[v] || v,
              },
              {
                title: "标题",
                dataIndex: "title",
                ellipsis: true,
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 100,
                render: (v: string) => {
                  const s = STATUS_TAG[v] || { color: "default", label: v };
                  return <Tag color={s.color}>{s.label}</Tag>;
                },
              },
              {
                title: "错误信息",
                dataIndex: "error_message",
                ellipsis: true,
                render: (v: string | null) =>
                  v ? (
                    <Text type="danger">{v}</Text>
                  ) : (
                    <CheckCircleOutlined style={{ color: "#52c41a" }} />
                  ),
              },
            ]}
          />
        </Card>
      </Spin>
    </div>
  );
}
