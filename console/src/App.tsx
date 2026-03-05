import { NavLink, Route, Routes } from "react-router-dom";
import {
  MessageSquare,
  FileText,
  Radio,
  MessageCircle,
  Timer,
  Heart,
  Activity,
  FolderOpen,
  Puzzle,
  Cable,
  Settings,
  Cpu,
  KeyRound,
  Beaker,
} from "lucide-react";
import ChatPage from "./pages/ChatPage";
import PapersPage from "./pages/PapersPage";
import StatusPage from "./pages/StatusPage";
import ChannelsPage from "./pages/ChannelsPage";
import SessionsPage from "./pages/SessionsPage";
import CronJobsPage from "./pages/CronJobsPage";
import HeartbeatPage from "./pages/HeartbeatPage";
import EnvironmentsPage from "./pages/EnvironmentsPage";
import SkillsPage from "./pages/SkillsPage";
import McpPage from "./pages/McpPage";
import WorkspacePage from "./pages/WorkspacePage";
import AgentConfigPage from "./pages/AgentConfigPage";
import ModelsPage from "./pages/ModelsPage";
import ConsoleCronBubble from "./components/ConsoleCronBubble";

type NavItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    title: "研究",
    items: [
      { to: "/chat", label: "AI 对话", icon: <MessageSquare size={17} /> },
      { to: "/papers", label: "论文检索", icon: <FileText size={17} /> },
    ],
  },
  {
    title: "控制",
    items: [
      { to: "/channels", label: "频道", icon: <Radio size={17} /> },
      { to: "/sessions", label: "会话", icon: <MessageCircle size={17} /> },
      { to: "/cron-jobs", label: "定时任务", icon: <Timer size={17} /> },
      { to: "/heartbeat", label: "心跳", icon: <Heart size={17} /> },
      { to: "/status", label: "系统状态", icon: <Activity size={17} /> },
    ],
  },
  {
    title: "智能体",
    items: [
      { to: "/workspace", label: "工作区", icon: <FolderOpen size={17} /> },
      { to: "/skills", label: "技能", icon: <Puzzle size={17} /> },
      { to: "/mcp", label: "MCP", icon: <Cable size={17} /> },
      {
        to: "/agent-config",
        label: "Agent 配置",
        icon: <Settings size={17} />,
      },
    ],
  },
  {
    title: "设置",
    items: [
      { to: "/models", label: "模型", icon: <Cpu size={17} /> },
      {
        to: "/environments",
        label: "环境变量",
        icon: <KeyRound size={17} />,
      },
    ],
  },
];

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-title">
            <div className="brand-logo">
              <Beaker size={20} />
            </div>
            <div>
              <h1>ResearchClaw</h1>
              <p>Scholar Console</p>
            </div>
          </div>
        </div>

        <nav className="menu">
          {navSections.map((section) => (
            <div key={section.title} className="nav-section">
              <div className="nav-section-label">{section.title}</div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `nav-link${isActive ? " active" : ""}`
                  }
                >
                  <span className="nav-icon">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-footer-badge">
            <span className="sidebar-footer-dot" />
            ResearchClaw 运行中
          </div>
        </div>
      </aside>

      <main className="content">
        <ConsoleCronBubble />
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/papers" element={<PapersPage />} />
          <Route path="/channels" element={<ChannelsPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/cron-jobs" element={<CronJobsPage />} />
          <Route path="/heartbeat" element={<HeartbeatPage />} />
          <Route path="/status" element={<StatusPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/agent-config" element={<AgentConfigPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/environments" element={<EnvironmentsPage />} />
          <Route path="/mcp" element={<McpPage />} />
        </Routes>
      </main>
    </div>
  );
}
