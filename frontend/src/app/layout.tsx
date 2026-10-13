import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CommitFlow — AI-Powered GitHub Activity Automation",
  description: "Maintain authentic developer habits with verified code, documentation, and unit tests pushed to GitHub.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0b0f19] text-slate-100 antialiased selection:bg-blue-500/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
