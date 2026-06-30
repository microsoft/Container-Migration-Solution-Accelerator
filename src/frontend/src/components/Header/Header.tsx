import React from "react";
import { Subtitle2 } from "@fluentui/react-components";
/**
 * @component
 * @name Header
 * @description A header component for displaying a logo, title, and optional subtitle.
 * 
 * @prop {React.ReactNode} [logo] - Custom logo (defaults to Microsoft icon).
 * @prop {string} [title="Microsoft"] - Main title text.
 * @prop {string} [subtitle] - Optional subtitle displayed next to the title.
 * @prop {React.ReactNode} [children] - Optional header toolbar (e.g., buttons, menus).
 * @prop {() => void} [onTitleClick] - Optional click handler for title/logo area.
 */
type HeaderProps = {
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
  onTitleClick?: () => void;
};

const Header: React.FC<HeaderProps> = ({ title = "Contoso", subtitle, children, onTitleClick }) => {
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        width: "100%",
        backgroundColor: "#fafafa",
        borderBottom: "1px solid var(--colorNeutralStroke2)",
        padding: "16px",
        height: "64px",
        boxSizing: "border-box",
        gap: "12px",
        position: 'fixed',
        zIndex: 1000,
      }}
      data-figma-component="Header"
    >
      <div
        onClick={onTitleClick}
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "8px",
          cursor: onTitleClick ? "pointer" : "default",
        }}
      >
        {/* Render custom logo or default MsftColor logo */}
        {/* <Avatar shape="square" color={null} icon={logo || <MsftColor />} /> */}
        <img src="/images/Contoso.png" alt="Contoso" style={{ width: "25px", height: "25px" }} />

        {/* Render title and optional subtitle */}
        <Subtitle2 style={{ whiteSpace: "nowrap", marginTop: "-2px" }}>
          {title}
          {subtitle && (
            <span style={{ fontWeight: "400" }}> | {subtitle}</span>
          )}
        </Subtitle2>
      </div>

      {/* HEADER TOOLBAR (rendered only if passed as a child) */}
      {children}
    </header>
  );
};

export default Header;
