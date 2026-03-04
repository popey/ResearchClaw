import { t, type Lang } from "../i18n";

export function Footer({ lang }: { lang: Lang }) {
  return (
    <footer
      style={{
        marginTop: "auto",
        padding: "var(--space-4) var(--space-4)",
        borderTop: "1px solid var(--border)",
        textAlign: "center",
        fontSize: "0.875rem",
        color: "var(--text-muted)",
      }}
    >
      <div style={{ marginBottom: "var(--space-2)" }}>{t(lang, "footer")}</div>
      <div style={{ fontSize: "0.8125rem", opacity: 0.9 }}>
        {t(lang, "footer.builtWith")}
      </div>
    </footer>
  );
}
