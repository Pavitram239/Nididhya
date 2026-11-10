import React from "react";
import { BookOpen, Flame, Sparkles, Moon, Sun, Type, Compass, ScrollText } from "lucide-react";

export default function Navbar({
  currentTab,
  setCurrentTab,
  theme,
  setTheme,
  lang,
  setLang,
  fontSize,
  setFontSize
}) {
  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("app_theme", next);
  };

  const cycleFontSize = () => {
    const sizes = [14, 16, 18, 20];
    const idx = sizes.indexOf(fontSize);
    const next = sizes[(idx + 1) % sizes.length];
    setFontSize(next);
    document.documentElement.style.setProperty("--reader-font-size", `${next}px`);
  };

  const navItems = [
    { id: "home", labelEn: "Home", labelGu: "પ્રારંભ", icon: Compass },
    { id: "vachanamrut", labelEn: "Vachanamrut", labelGu: "વચનામૃત", icon: BookOpen },
    { id: "swaminivato", labelEn: "Swamini Vato", labelGu: "સ્વામીની વાતો", icon: ScrollText },
    { id: "ai", labelEn: "AI Guide", labelGu: "AI સહાયક", icon: Sparkles },
    { id: "topics", labelEn: "Topics", labelGu: "વિષયવાર", icon: Flame },
    { id: "shikshapatri", labelEn: "Shikshapatri", labelGu: "શિક્ષાપત્રી", icon: ScrollText }
  ];

  return (
    <>
      <header className="nididhya-header">
        {/* Column 1: Brand (Left) */}
        <div className="header-brand-col">
          <div
            className="brand-link"
            onClick={() => setCurrentTab("home")}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setCurrentTab("home");
              }
            }}
            aria-label="Nididhiyas Home"
          >
            <div className="brand-logo-badge">
              <Flame size={20} color="#ffffff" strokeWidth={2.2} />
            </div>
            <div className="brand-text-block">
              <span className="brand-title">
                {lang === "gu" ? "નિદિધ્યાસ" : "Nididhiyas"}
              </span>
              <span className="brand-subtitle">
                {lang === "gu" ? "શાસ્ત્ર ચિંતન અને આધ્યાત્મિક સંવાદ" : "Sacred Scriptures & AI Companion"}
              </span>
            </div>
          </div>
        </div>

        {/* Column 2: Navigation Capsule (Center) */}
        <div className="header-nav-col">
          <nav className="nav-capsule" aria-label="Main Navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentTab(item.id)}
                  className={`nav-item-btn ${isActive ? "active" : ""}`}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon size={16} strokeWidth={isActive ? 2.2 : 1.9} />
                  <span>{lang === "gu" ? item.labelGu : item.labelEn}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Column 3: Utility Controls (Right) */}
        <div className="header-controls-col">
          {/* Language Selector */}
          <div className="header-segmented-lang" role="group" aria-label="Language Selector">
            <button
              onClick={() => setLang("en")}
              className={`header-lang-btn ${lang === "en" ? "active" : ""}`}
              aria-pressed={lang === "en"}
              title="English"
            >
              EN
            </button>
            <button
              onClick={() => setLang("gu")}
              className={`header-lang-btn ${lang === "gu" ? "active" : ""}`}
              aria-pressed={lang === "gu"}
              title="ગુજરાતી"
            >
              ગુ
            </button>
          </div>

          {/* Text Size Control */}
          <button
            onClick={cycleFontSize}
            className="header-icon-btn"
            title={`Font size: ${fontSize}px (Click to adjust)`}
            aria-label={`Adjust font size, current ${fontSize}px`}
          >
            <Type size={16} strokeWidth={2} />
            <span style={{ fontSize: "12px", fontWeight: "600" }}>{fontSize}</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="header-icon-btn"
            title={theme === "light" ? "Switch to Dark theme" : "Switch to Light theme"}
            aria-label={theme === "light" ? "Switch to Dark theme" : "Switch to Light theme"}
          >
            {theme === "light" ? (
              <Moon size={17} strokeWidth={2} />
            ) : (
              <Sun size={17} strokeWidth={2} />
            )}
          </button>
        </div>
      </header>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="app-bottom-nav" aria-label="Mobile Navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`bottom-nav-btn ${isActive ? "active" : ""}`}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={isActive ? 2.4 : 1.8} />
              <span className="bottom-nav-label">
                {lang === "gu" ? item.labelGu : item.labelEn}
              </span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
