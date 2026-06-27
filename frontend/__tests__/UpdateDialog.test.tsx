/**
 * Tests for UpdateDialog component.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import UpdateDialog from "@/components/UpdateDialog";

// Mock the i18n module
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "updater.new_version": "发现新版本",
        "updater.current_version": "当前版本",
        "updater.downloading": "下载中...",
        "updater.install_now": "立即更新",
        "updater.later": "稍后提醒",
      };
      return map[key] || key;
    },
  }),
}));

describe("UpdateDialog", () => {
  const mockUpdate = {
    version: "2.0.0",
    body: "Bug fixes and performance improvements",
    date: "2026-06-01T00:00:00Z",
  };

  it("renders nothing when update prop is null", () => {
    const { container } = render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={null}
        downloading={false}
        downloadProgress={0}
        onInstall={jest.fn()}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders update info when open and update is provided", () => {
    render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={mockUpdate}
        downloading={false}
        downloadProgress={0}
        onInstall={jest.fn()}
      />
    );

    expect(screen.getByText("发现新版本")).toBeInTheDocument();
    expect(screen.getByText(/v2\.0\.0/)).toBeInTheDocument();
  });

  it("shows download progress when downloading", () => {
    render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={mockUpdate}
        downloading={true}
        downloadProgress={50}
        onInstall={jest.fn()}
      />
    );

    expect(screen.getByText("下载中...")).toBeInTheDocument();
  });

  it("shows success state when download is complete", () => {
    render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={mockUpdate}
        downloading={true}
        downloadProgress={100}
        onInstall={jest.fn()}
      />
    );

    expect(screen.getByText("安装完成，即将重启...")).toBeInTheDocument();
  });

  it("calls onClose when '稍后提醒' is clicked", () => {
    const onClose = jest.fn();
    render(
      <UpdateDialog
        open={true}
        onClose={onClose}
        update={mockUpdate}
        downloading={false}
        downloadProgress={0}
        onInstall={jest.fn()}
      />
    );

    fireEvent.click(screen.getByText("稍后提醒"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onInstall when '立即更新' is clicked", () => {
    const onInstall = jest.fn();
    render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={mockUpdate}
        downloading={false}
        downloadProgress={0}
        onInstall={onInstall}
      />
    );

    fireEvent.click(screen.getByText("立即更新"));
    expect(onInstall).toHaveBeenCalled();
  });

  it("displays the update body (changelog)", () => {
    render(
      <UpdateDialog
        open={true}
        onClose={jest.fn()}
        update={mockUpdate}
        downloading={false}
        downloadProgress={0}
        onInstall={jest.fn()}
      />
    );

    expect(screen.getByText("Bug fixes and performance improvements")).toBeInTheDocument();
  });
});
