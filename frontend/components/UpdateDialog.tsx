import React from "react";
import { Modal, Typography, Progress, Space, Tag } from "antd";
import { CloudDownloadOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { useI18n } from "@/lib/i18n";
import type { UpdateInfo } from "@/lib/useUpdater";

const { Title, Text, Paragraph } = Typography;

interface UpdateDialogProps {
  open: boolean;
  onClose: () => void;
  update: UpdateInfo | null;
  downloading: boolean;
  downloadProgress: number;
  onInstall: () => void;
}

export default function UpdateDialog({
  open,
  onClose,
  update,
  downloading,
  downloadProgress,
  onInstall,
}: UpdateDialogProps) {
  const { t } = useI18n();

  if (!update) return null;

  const isComplete = downloadProgress >= 100;

  return (
    <Modal
      title={
        <Space>
          <CloudDownloadOutlined style={{ color: "#1677ff" }} />
          <span>{t("updater.new_version")}</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      maskClosable={!downloading}
      closable={!downloading}
      footer={
        downloading
          ? null
          : [
              <button
                key="later"
                onClick={onClose}
                style={{
                  padding: "6px 16px",
                  border: "1px solid #d9d9d9",
                  borderRadius: 6,
                  background: "#fff",
                  cursor: "pointer",
                }}
              >
                {t("updater.later")}
              </button>,
              <button
                key="install"
                onClick={onInstall}
                style={{
                  padding: "6px 16px",
                  border: "none",
                  borderRadius: 6,
                  background: "#1677ff",
                  color: "#fff",
                  cursor: "pointer",
                }}
              >
                {t("updater.install_now")}
              </button>,
            ]
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Text type="secondary">{t("updater.current_version")}:</Text>
          <Tag>v{typeof window !== "undefined" && "__TAURI_INTERNALS__" in window ? "1.3.0" : "—"}</Tag>
          <Text type="secondary">→</Text>
          <Tag color="blue">v{update.version}</Tag>
        </Space>
      </div>

      {update.date && (
        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          发布时间: {new Date(update.date).toLocaleDateString("zh-CN")}
        </Text>
      )}

      <Title level={5} style={{ marginBottom: 8 }}>
        更新日志
      </Title>
      <Paragraph
        style={{
          background: "#f5f5f5",
          padding: 12,
          borderRadius: 8,
          maxHeight: 200,
          overflow: "auto",
          whiteSpace: "pre-wrap",
        }}
      >
        {update.body}
      </Paragraph>

      {downloading && (
        <div style={{ marginTop: 16 }}>
          <Space style={{ marginBottom: 8 }}>
            {isComplete ? (
              <>
                <CheckCircleOutlined style={{ color: "#52c41a" }} />
                <Text type="success">安装完成，即将重启...</Text>
              </>
            ) : (
              <Text>{t("updater.downloading")}</Text>
            )}
          </Space>
          <Progress
            percent={downloadProgress}
            status={isComplete ? "success" : "active"}
            strokeColor={isComplete ? "#52c41a" : "#1677ff"}
          />
        </div>
      )}
    </Modal>
  );
}
